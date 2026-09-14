from ..asr import Diarizer
from deepgram import DeepgramClient, PrerecordedOptions, FileSource


class DeepgramDiarizer(Diarizer):
    def __init__(self, api_key: str, model: str = "nova-2"):
        self.client = DeepgramClient(api_key=api_key)
        self.model = model
        super().__init__()

    def diarize(self, wav_path: str) -> list[dict]:
        with open(wav_path, "rb") as f:
            buffer_data = f.read()

        payload: FileSource = {"buffer": buffer_data}

        options = PrerecordedOptions(
            model=self.model,
            diarize=True,
            punctuate=True,
        )

        response = self.client.listen.rest.v("1").transcribe_file(
            payload, options
        )

        words = response.results.channels[0].alternatives[0].words or []

        # Схлопываем последовательные слова одного спикера в непрерывные сегменты
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