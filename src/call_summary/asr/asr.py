from abc import ABC, abstractmethod
from typing import Iterable,Tuple





class Diarizer(ABC):
    @abstractmethod
    def diarize(self,wav_path: str)->list[dict]:
        ...

class Transcriber(ABC):
    @abstractmethod
    def transcribe(self, wav_path: str, language: str = "ru")->list[dict]:
        ...