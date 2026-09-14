"""
Сервер: модели грузятся ОДИН раз при старте приложения (в lifespan),
дальше каждый входящий .ogg обрабатывается уже загруженными моделями —
без повторной загрузки на каждый запрос.

Зависимости (добавить через uv):
    uv add fastapi uvicorn python-multipart
    (плюс всё, что уже стоит: faster-whisper, sherpa-onnx, soundfile)

Запуск:
    uv run uvicorn server:app --host 0.0.0.0 --port 8000

Использование (например, из telegram-бота):
    curl -X POST http://localhost:8000/transcribe -F "file=@voice.ogg"
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, UploadFile, File
from fastapi.responses import JSONResponse

# VoiceProcessor из voice_sherpa_persistent.py — тот самый класс,
# где __init__ грузит whisper + sherpa-onnx один раз.
from call_summary.voice_sherpa_persistent import VoiceProcessor

import tempfile
import os

# Сюда положим единственный экземпляр процессора на весь процесс сервера.
state = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- СТАРТ ПРИЛОЖЕНИЯ: модели грузятся здесь, один раз ---
    # device/compute_type берутся из переменных окружения, которые задаёт
    # Makefile (make server-gpu / make server-cpu) — сам код не меняется.
    device = os.environ.get("DEVICE", "cpu")
    compute_type = os.environ.get("COMPUTE_TYPE", "int8")

    print(f"Запуск сервера: загружаю модели (device={device}, compute_type={compute_type})...")
    state["processor"] = VoiceProcessor(
        model_size="small",
        device=device,
        compute_type=compute_type,
        transcriber_provider="deepgram",
        diarizer_provider="deepgram",
        num_speakers=-1,  # или 2, если у вас всегда разговор один на один
    )
    print("Модели загружены, сервер готов принимать запросы.")

    yield  # <-- сервер работает и обслуживает запросы здесь

    # --- ОСТАНОВКА ПРИЛОЖЕНИЯ: тут можно освободить ресурсы, если нужно ---
    print("Останавливаю сервер...")
    state.clear()


app = FastAPI(lifespan=lifespan)


@app.post("/transcribe")
async def transcribe_endpoint(file: UploadFile = File(...)):
    """
    Принимает .ogg файл, возвращает текст с разбивкой по спикерам.
    Модели НЕ грузятся здесь — они уже в памяти (state["processor"]),
    загруженные при старте сервера.
    """
    processor: VoiceProcessor = state["processor"]

    # сохраняем загруженный файл во временный .ogg
    tmp_path = tempfile.mktemp(suffix=".ogg")
    with open(tmp_path, "wb") as f:
        f.write(await file.read())

    try:
        result_text = processor.process_ogg(tmp_path)
        return JSONResponse({"text": result_text})
    finally:
        os.remove(tmp_path)


@app.get("/health")
async def health():
    """Проверка, что модели вообще загружены и сервер живой."""
    return {"status": "ok", "models_loaded": "processor" in state}