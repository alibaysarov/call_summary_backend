"""
Комбинированный Deepgram-провайдер: используется, когда И transcriber,
И diarizer настроены на provider="deepgram". В этом случае транскрипт
и диаризация приходят в ОДНОМ ответе Deepgram (diarize=True в том же
запросе), поэтому вместо двух HTTP-запросов делаем один.

Если провайдеры смешанные (deepgram+local или local+deepgram) — этот
класс не используется вообще, каждый провайдер работает отдельно и
независимо, каждый со своим запросом/пайплайном.
"""

import threading

from ..asr import Diarizer, Transcriber
from deepgram import DeepgramClient, PrerecordedOptions, FileSource


class DeepgramCombinedProvider(Transcriber, Diarizer):
    def __init__(self, api_key: str, model: str = "nova-2"):
        self.client = DeepgramClient(api_key=api_key)
        self.model = model
        self._lock = threading.Lock()
        # кэш на текущий wav_path — process_ogg вызывает transcribe() и
        # diarize() параллельно на один и тот же файл, поэтому первый
        # вызов реально идёт в API, второй просто ждёт лока и берёт кэш
        self._cached_wav_path: str | None = None
        self._cached_language: str | None = None
        self._cached_response = None
        super().__init__()

    def _get_response(self, wav_path: str, language: str):
        with self._lock:
            if (
                self._cached_response is not None
                and self._cached_wav_path == wav_path
                and self._cached_language == language
            ):
                return self._cached_response

            with open(wav_path, "rb") as f:
                buffer_data = f.read()

            payload: FileSource = {"buffer": buffer_data}
            options = PrerecordedOptions(
                model=self.model,
                language=language,
                smart_format=True,
                punctuate=True,
                utterances=True,
                diarize=True,
            )
            response = self.client.listen.rest.v("1").transcribe_file(
                payload, options
            )

            self._cached_wav_path = wav_path
            self._cached_language = language
            self._cached_response = response
            return response

    def transcribe(self, wav_path: str, language: str = "ru"):
        response = self._get_response(wav_path, language)
        utterances = response.results.utterances or []
        return [
            {
                "start": u.start,
                "end": u.end,
                "text": u.transcript.strip(),
            }
            for u in utterances
        ]

    def diarize(self, wav_path: str) -> list[dict]:
        # diarize() по интерфейсу не принимает language — используем тот же
        # дефолт "ru", что и Transcriber.transcribe(). Если позже нужно
        # будет передавать другой язык, интерфейс Diarizer придётся расширить.
        response = self._get_response(wav_path, "ru")
        words = response.results.channels[0].alternatives[0].words or []

        segments: list[dict] = []
        for w in words:
            speaker = f"SPEAKER_{w.speaker:02d}"
            if segments and segments[-1]["speaker"] == speaker:
                segments[-1]["end"] = float(w.end)
            else:
                segments.append(
                    {
                        "start": float(w.start),
                        "end": float(w.end),
                        "speaker": speaker,
                    }
                )
        return segments