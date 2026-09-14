"""Call processing package. Legacy audio exports are loaded only when requested."""


def __getattr__(name):
    if name == "convert_ogg_to_wav":
        from .voice import convert_ogg_to_wav

        return convert_ogg_to_wav
    if name == "transcribe_and_diarize_ogg_local":
        from .voice_local import transcribe_and_diarize_ogg_local

        return transcribe_and_diarize_ogg_local
    raise AttributeError(name)
