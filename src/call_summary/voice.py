"""
Транскрибация голосового сообщения (.ogg из Telegram) с диаризацией спикеров.

Зависимости (добавить через uv):
    uv add faster-whisper
    uv add pyannote.audio
    uv add torch torchaudio   # если ещё не стоит

Плюс системно нужен ffmpeg (для конвертации ogg -> wav):
    sudo apt install ffmpeg

Диаризация использует модель pyannote/speaker-diarization-3.1.
Она "gated" на HuggingFace: нужно
    1) зарегистрироваться на huggingface.co
    2) принять условия на странице модели:
       https://huggingface.co/pyannote/speaker-diarization-3.1
    3) создать токен (Settings -> Access Tokens) и передать его сюда
       или положить в переменную окружения HF_TOKEN.
"""

import os
import shutil
import subprocess
import tempfile

from faster_whisper import WhisperModel
from pyannote.audio import Pipeline
from decorators import timeit

def convert_ogg_to_wav(ogg_path: str) -> str:
    """Конвертирует .ogg в .wav 16kHz mono (нужно и whisper, и pyannote)."""
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
def diarize(wav_path: str, hf_token: str | None = None):
    """
    Разбивка аудио на "кто говорил и когда" (без текста).
    Возвращает список отрезков вида {"start": ..., "end": ..., "speaker": "SPEAKER_00"}.
    """
    token = hf_token or os.environ.get("HF_TOKEN")
    if not token:
        raise RuntimeError(
            "Нужен HuggingFace токен для pyannote. "
            "Передай hf_token= или установи переменную окружения HF_TOKEN."
        )

    pipeline = Pipeline.from_pretrained(
        "pyannote/speaker-diarization-3.1",
        token=token,
    )

    diarization = pipeline(wav_path)
    annotation = getattr(
        diarization, "exclusive_speaker_diarization", diarization
    )

    result = []
    for turn, _, speaker in annotation.itertracks(yield_label=True):
        result.append({"start": turn.start, "end": turn.end, "speaker": speaker})
    return result

@timeit
def merge_transcript_with_speakers(transcript_segments, speaker_segments) -> str:
    """
    Сопоставляет текстовые сегменты whisper с отрезками спикеров pyannote
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
def transcribe_and_diarize_ogg(
    ogg_path: str,
    hf_token: str | None = None,
    model_size: str = "small",
    device: str = "cuda",
    compute_type: str = "float16",
) -> str:
    """
    Главная функция: путь к .ogg -> готовый текст с разбивкой по спикерам.
    """
    wav_path = convert_ogg_to_wav(ogg_path)
    try:
        transcript_segments = transcribe(
            wav_path, model_size=model_size, device=device, compute_type=compute_type
        )
        speaker_segments = diarize(wav_path, hf_token=hf_token)
        return merge_transcript_with_speakers(transcript_segments, speaker_segments)
    finally:
        os.remove(wav_path)