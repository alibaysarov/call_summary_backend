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

import shutil
import subprocess
import tarfile
import tempfile
import urllib.request

import numpy as np
import sherpa_onnx
import soundfile as sf
from faster_whisper import WhisperModel
from call_summary.timing import timeit
from call_summary.settings import (
    EMBEDDING_MODEL,
    EMBEDDING_URL,
    MODELS_DIR,
    SEGMENTATION_MODEL,
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


@timeit
def transcribe(wav_path: str, model_size: str = "small", device: str = "cuda", compute_type: str = "int8"):
    """
    Просто транскрибация без диаризации.
    Возвращает список сегментов с таймкодами и текстом.

    device="cuda" — если нет GPU, поставь device="cpu", compute_type="int8".
    """
    model = WhisperModel(model_size, device=device, compute_type=compute_type)

    segments, info = model.transcribe(
        wav_path,
        language="ru",
        word_timestamps=True,
    )

    result = []
    for seg in segments:
        result.append({"start": seg.start, "end": seg.end, "text": seg.text.strip()})
    return result


@timeit
def diarize(wav_path: str, num_speakers: int = -1, cluster_threshold: float = 0.5):
    """
    Разбивка аудио на "кто говорил и когда" (без текста), через sherpa-onnx.

    Возвращает список отрезков вида {"start": ..., "end": ..., "speaker": "SPEAKER_00"}.

    num_speakers:
        Если знаете точное число говорящих — укажите (например, 2 для
        разговора один на один). Иначе оставьте -1, тогда число спикеров
        определяется автоматически через cluster_threshold.
    cluster_threshold:
        Используется только если num_speakers == -1. Меньше -> больше
        спикеров находится, больше -> меньше.
    """
    download_diarization_models()

    config = sherpa_onnx.OfflineSpeakerDiarizationConfig(
        segmentation=sherpa_onnx.OfflineSpeakerSegmentationModelConfig(
            pyannote=sherpa_onnx.OfflineSpeakerSegmentationPyannoteModelConfig(
                model=SEGMENTATION_MODEL,
            ),
        ),
        embedding=sherpa_onnx.SpeakerEmbeddingExtractorConfig(
            model=EMBEDDING_MODEL,
        ),
        clustering=sherpa_onnx.FastClusteringConfig(
            num_clusters=num_speakers, threshold=cluster_threshold,
        ),
        min_duration_on=0.3,
        min_duration_off=0.5,
    )
    if not config.validate():
        raise RuntimeError(
            "Некорректный конфиг sherpa-onnx — проверьте, что модели скачались "
            f"в {MODELS_DIR}"
        )

    sd = sherpa_onnx.OfflineSpeakerDiarization(config)

    audio, sample_rate = sf.read(wav_path, dtype="float32", always_2d=True)
    audio = audio[:, 0]  # только первый канал, у нас и так mono

    if sample_rate != sd.sample_rate:
        raise RuntimeError(
            f"Ожидался sample rate {sd.sample_rate}, получен {sample_rate}. "
            "Проверьте, что convert_ogg_to_wav отдаёт 16kHz."
        )

    diar_result = sd.process(audio).sort_by_start_time()

    result = []
    for r in diar_result:
        result.append({
            "start": float(r.start),
            "end": float(r.end),
            "speaker": f"SPEAKER_{r.speaker:02d}",
        })
    return result


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


@timeit
def transcribe_and_diarize_ogg_local(
    ogg_path: str,
    hf_token: str | None = None,   # больше не нужен для diarize (sherpa-onnx
                                    # не требует HF-токена), оставлен для
                                    # обратной совместимости сигнатуры
    model_size: str = "small",
    device: str = "cuda",
    compute_type: str = "float16",
    num_speakers: int = -1,
) -> str:
    """
    Главная функция: путь к .ogg -> готовый текст с разбивкой по спикерам.
    """
    wav_path = convert_ogg_to_wav(ogg_path)
    try:
        transcript_segments = transcribe(
            wav_path, model_size=model_size, device=device, compute_type=compute_type
        )
        speaker_segments = diarize(wav_path, num_speakers=num_speakers)
        return merge_transcript_with_speakers(transcript_segments, speaker_segments)
    finally:
        os.remove(wav_path)