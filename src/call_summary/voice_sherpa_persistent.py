"""
Транскрибация голосового сообщения (.ogg из Telegram) с диаризацией спикеров.

Отличие от исходной версии: diarize() теперь работает не через pyannote.audio
(тяжёлый PyTorch-пайплайн), а через sherpa-onnx (ONNX Runtime) — те же по сути
модели (pyannote/segmentation-3.0 для VAD/сегментации + wespeaker для
speaker-эмбеддингов), но без PyTorch и без gated-доступа на HuggingFace.
На CPU это ощутимо быстрее (в тестах на схожих пайплайнах — в разы).

Зависимости (добавить через uv):
    uv add faster-whisper
    uv add sherpa-onnx
    uv add soundfile numpy

Плюс системно нужен ffmpeg (для конвертации ogg -> wav):
    sudo apt install ffmpeg

Модели для sherpa-onnx скачиваются автоматически при первом запуске
(см. download_diarization_models) в ./models — как одноразовый кэш,
аналогично тому, как HuggingFace кэшировал веса pyannote.
"""

import os
import shutil
import subprocess
import tarfile
import tempfile
import urllib.request
from call_summary.enums.provider import Provider 
from decorators import timeit
from call_summary.asr import Diarizer, Transcriber
from call_summary.settings import (
    DEEPGRAM_API_KEY,
    EMBEDDING_MODEL,
    EMBEDDING_URL,
    MODELS_DIR,
    SEGMENTATION_MODEL,
    SEGMENTATION_URL,
)


def download_diarization_models():
    """Скачивает модели для sherpa-onnx один раз, если их ещё нет на диске."""
    os.makedirs(MODELS_DIR, exist_ok=True)

    if not os.path.exists(SEGMENTATION_MODEL):
        print("Скачиваю модель сегментации (pyannote-segmentation-3.0, ONNX)...")
        archive_path = os.path.join(MODELS_DIR, "segmentation.tar.bz2")
        urllib.request.urlretrieve(SEGMENTATION_URL, archive_path)
        with tarfile.open(archive_path, "r:bz2") as tar:
            tar.extractall(MODELS_DIR)
        os.remove(archive_path)

    if not os.path.exists(EMBEDDING_MODEL):
        print("Скачиваю embedding-модель (wespeaker voxceleb resnet34 LM, ONNX)...")
        urllib.request.urlretrieve(EMBEDDING_URL, EMBEDDING_MODEL)


def convert_ogg_to_wav(ogg_path: str) -> str:
    """Конвертирует .ogg в .wav 16kHz mono (нужно и whisper, и sherpa-onnx)."""
    if shutil.which("ffmpeg") is None:
        raise RuntimeError(
            "Не найден ffmpeg. Установите его командой: sudo apt install ffmpeg"
        )

    wav_path = tempfile.mktemp(suffix=".wav")
    subprocess.run(
        [
            "ffmpeg", "-y", "-i", ogg_path,
            "-ar", "16000", "-ac", "1",
            wav_path,
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return wav_path


class VoiceProcessor:
    """
    Держит whisper и sherpa-onnx diarization pipeline в памяти — оба грузятся
    ОДИН РАЗ в __init__. Дальше process_ogg()/transcribe()/diarize() можно
    вызывать сколько угодно раз подряд БЕЗ повторной загрузки моделей.

    ВАЖНО: "один раз" здесь означает "один раз за время жизни ЭТОГО объекта",
    то есть внутри одного Python-процесса. Если вы вызываете `make dev`
    (а значит `uv run ...`) отдельно на каждый файл — каждый такой запуск это
    новый процесс с нуля, и модели неизбежно загрузятся заново, сколько бы вы
    ни переносили код в класс. Чтобы реально грузить один раз, обрабатывать
    нужно НЕСКОЛЬКО файлов в рамках одного запуска (см. main() внизу файла —
    там VoiceProcessor создаётся один раз и потом крутится в цикле).
    """

    def __init__(
        self,
        model_size: str = "small",
        device: str = "cpu",
        compute_type: str = "int8",
        num_speakers: int = -1,
        cluster_threshold: float = 0.5,
        num_threads: int = 4,
        transcriber: Transcriber | None = None,
        diarizer: Diarizer | None = None,
        transcriber_provider: str = "local",
        diarizer_provider: str = "local",
        deepgram_api_key: str | None = None,
        deepgram_transcriber_model: str = "nova-2",
        deepgram_diarizer_model: str = "nova-2",
    ):
        # Если оба провайдера — deepgram, транскрипт и диаризация приходят
        # в одном ответе API: делаем ОДИН запрос вместо двух. Если явно
        # передали готовые transcriber/diarizer или провайдеры разные —
        # эта ветка не срабатывает, всё идёт как раньше, раздельно.
        if (
            transcriber is None
            and diarizer is None
            and transcriber_provider == "deepgram"
            and diarizer_provider == "deepgram"
        ):
            from call_summary.providers.deepgram_combined import DeepgramCombinedProvider

            api_key = deepgram_api_key or DEEPGRAM_API_KEY
            if api_key is None:
                raise ValueError("NO DEEPGRAM KEY PROVIDED!")

            if deepgram_transcriber_model != deepgram_diarizer_model:
                raise ValueError(
                    "При provider=deepgram для транскрайбера и диаризатора "
                    "модель должна совпадать (используется один запрос): "
                    f"{deepgram_transcriber_model!r} != {deepgram_diarizer_model!r}"
                )

            print("Использую единый Deepgram-провайдер (1 запрос на файл вместо 2)...")
            combined = DeepgramCombinedProvider(
                api_key=api_key, model=deepgram_transcriber_model
            )
            transcriber = combined
            diarizer = combined

        if transcriber is None:
            transcriber = self._create_transcriber(
                model_size=model_size,
                device=device,
                compute_type=compute_type,
                provider=transcriber_provider,
                deepgram_api_key=deepgram_api_key,
                deepgram_model=deepgram_transcriber_model,
            )
        if diarizer is None:
            diarizer = self._create_diarizer(
                device=device,
                num_speakers=num_speakers,
                cluster_threshold=cluster_threshold,
                num_threads=num_threads,
                provider=diarizer_provider,
                deepgram_api_key=deepgram_api_key,
                deepgram_model=deepgram_diarizer_model,
            )
        self.transcriber = transcriber
        self.diarizer = diarizer

    @staticmethod
    def _create_transcriber(
        model_size: str,
        device: str,
        compute_type: str,
        provider: str,
        deepgram_api_key: str | None,
        deepgram_model: str,
    ) -> Transcriber:
        if provider == "local":
            from call_summary.transcribers.local import LocalTranscriber

            print(f"Загружаю whisper (один раз, device={device})...")
            return LocalTranscriber(
                model_size=model_size,
                device=device,
                compute_type=compute_type,
            )
        if provider == "deepgram":
            from call_summary.transcribers.deepgram import DeepgramTranscriber

            return DeepgramTranscriber(
                model=deepgram_model,
                api_key=deepgram_api_key,
            )
        raise ValueError(f"Неизвестный transcriber provider: {provider}")

    @staticmethod
    def _create_diarizer(
        device: str,
        num_speakers: int,
        cluster_threshold: float,
        num_threads: int,
        provider: str,
        deepgram_api_key: str | None,
        deepgram_model: str,
    ) -> Diarizer:
        if provider == "local":
            from call_summary.dializers.local import LocalDiarizer

            onnx_provider = "cuda" if device == "cuda" else "cpu"
            print(
                "Загружаю sherpa-onnx diarization pipeline "
                f"(один раз, provider={onnx_provider})..."
            )
            download_diarization_models()
            return LocalDiarizer(
                num_threads=num_threads,
                onnx_provider=onnx_provider,
                num_speakers=num_speakers,
                cluster_threshold=cluster_threshold,
            )
        if provider == "deepgram":
            from call_summary.dializers.deepgram import DeepgramDiarizer

            api_key = deepgram_api_key or DEEPGRAM_API_KEY
            if api_key is None:
                raise ValueError("NO DEEPGRAM KEY PROVIDED!")
            return DeepgramDiarizer(api_key=api_key, model=deepgram_model)
        raise ValueError(f"Неизвестный diarizer provider: {provider}")

    @timeit
    def transcribe(self, wav_path: str, language: str = "ru"):
        """Делегирует транскрибацию внедрённому Transcriber."""
        return self.transcriber.transcribe(wav_path, language=language)

    @timeit
    def diarize(self, wav_path: str):
        """Делегирует диаризацию внедрённому Diarizer."""
        return self.diarizer.diarize(wav_path)

    @timeit
    def process_ogg(self, ogg_path: str) -> str:
        """path к .ogg -> готовый текст с разбивкой по спикерам.

        transcribe() и diarize() независимы (оба читают один и тот же wav,
        но не используют результат друг друга) — поэтому гоняем их
        параллельно в двух потоках. GIL здесь не мешает: обе библиотеки
        (CTranslate2 внутри faster-whisper, ONNX Runtime внутри sherpa-onnx)
        выполняют тяжёлые вычисления в C++ и отпускают GIL на время работы.
        """
        from concurrent.futures import ThreadPoolExecutor

        wav_path = convert_ogg_to_wav(ogg_path)
        try:
            with ThreadPoolExecutor(max_workers=2) as pool:
                future_transcript = pool.submit(self.transcribe, wav_path)
                future_speakers = pool.submit(self.diarize, wav_path)
                transcript_segments = future_transcript.result()
                speaker_segments = future_speakers.result()
            return merge_transcript_with_speakers(transcript_segments, speaker_segments)
        finally:
            os.remove(wav_path)


@timeit
def merge_transcript_with_speakers(transcript_segments, speaker_segments) -> str:
    """
    Сопоставляет текстовые сегменты whisper с отрезками спикеров
    по времени (кто говорил в момент, когда была сказана фраза),
    и склеивает подряд идущие реплики одного спикера в один блок.
    """

    def find_speaker(start: float, end: float) -> str:
        mid = (start + end) / 2
        for s in speaker_segments:
            if s["start"] <= mid <= s["end"]:
                return s["speaker"]
        # если не попали ни в один отрезок - берём ближайший
        closest = min(speaker_segments, key=lambda s: abs(s["start"] - mid))
        return closest["speaker"]

    lines = []
    current_speaker = None
    current_text = []

    for seg in transcript_segments:
        speaker = find_speaker(seg["start"], seg["end"])
        if speaker != current_speaker:
            if current_text:
                lines.append(f"{current_speaker}: {' '.join(current_text)}")
            current_speaker = speaker
            current_text = [seg["text"]]
        else:
            current_text.append(seg["text"])

    if current_text:
        lines.append(f"{current_speaker}: {' '.join(current_text)}")

    return "\n".join(lines)


def transcribe_and_diarize_ogg(
    ogg_path: str,
    model_size: str = "small",
    device: str = "cpu",
    compute_type: str = "int8",
    num_speakers: int = -1,
) -> str:
    """
    Обёртка для обратной совместимости — старый интерфейс "один файл на вызов".
    Внутри всё равно создаёт VoiceProcessor и грузит модели — если вызываете
    эту функцию по одной на файл (как раньше), повторной загрузки избежать
    НЕ получится (см. main() ниже, как обрабатывать несколько файлов сразу
    с одной загрузкой моделей).
    """
    processor = VoiceProcessor(
        model_size=model_size, device=device, compute_type=compute_type,
        num_speakers=num_speakers,
    )
    return processor.process_ogg(ogg_path)


def main():
    """
    Пример реального "загрузили один раз — обработали много файлов":
    VoiceProcessor создаётся один-единственный раз, дальше в цикле
    прогоняются все .ogg файлы из папки files/ БЕЗ повторной загрузки модели.

    Запуск:  python voice_sherpa_persistent.py files/*.ogg
    """
    import sys
    import glob

    patterns = sys.argv[1:] or ["files/*.ogg"]
    paths = [p for pattern in patterns for p in glob.glob(pattern)]
    if not paths:
        print("Не найдено ни одного .ogg файла")
        return

    # <-- вот здесь модели грузятся ОДИН раз на весь список файлов
    processor = VoiceProcessor(model_size="small", device="cpu", compute_type="int8")

    for path in paths:
        print(f"\n=== {path} ===")
        result = processor.process_ogg(path)
        print(result)


if __name__ == "__main__":
    main()