from ..asr import Transcriber
from deepgram import DeepgramClient, PrerecordedOptions, FileSource
from call_summary.settings import DEEPGRAM_API_KEY

class DeepgramTranscriber(Transcriber):
    def __init__(self, model: str = "nova-2", api_key: str | None = None):
        api_key = api_key or DEEPGRAM_API_KEY
        if api_key is None:
            raise ValueError("NO DEEPGRAM KEY PROVIDED!")
        self.client = DeepgramClient(api_key=api_key)
        self.model = model
        super().__init__()

    def transcribe(self, wav_path: str, language: str = "ru"):
        """Транскрибация файла целиком через Deepgram prerecorded API."""
        with open(wav_path, "rb") as f:
            buffer_data = f.read()

        payload: FileSource = {"buffer": buffer_data}

        options = PrerecordedOptions(
            model=self.model,
            language=language,
            smart_format=True,
            punctuate=True,
            utterances=True,
        )

        response = self.client.listen.rest.v("1").transcribe_file(
            payload, options
        )

        utterances = response.results.utterances or []

        return [
            {
                "start": u.start,
                "end": u.end,
                "text": u.transcript.strip(),
            }
            for u in utterances
        ]