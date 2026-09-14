from ..asr import Transcriber
from faster_whisper import WhisperModel

class LocalTranscriber(Transcriber):
    def __init__(self,model_size,device,compute_type):
        self.whisper = WhisperModel(model_size, device=device, compute_type=compute_type)
        
        super().__init__()
    
    def transcribe(self, wav_path: str, language: str = "ru"):
        """Просто транскрибация без диаризации. Модель уже загружена в self.whisper."""
        segments, info = self.whisper.transcribe(
            wav_path, language=language, word_timestamps=True,
        )
        return [
            {"start": s.start, "end": s.end, "text": s.text.strip()}
            for s in segments
        ]