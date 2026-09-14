from ..asr import Diarizer, Transcriber
import soundfile as sf
import sherpa_onnx
from call_summary.settings import EMBEDDING_MODEL, MODELS_DIR, SEGMENTATION_MODEL


class LocalDiarizer(Diarizer):
    def __init__(self,num_threads,onnx_provider,num_speakers,cluster_threshold):
        config = sherpa_onnx.OfflineSpeakerDiarizationConfig(
            segmentation=sherpa_onnx.OfflineSpeakerSegmentationModelConfig(
                pyannote=sherpa_onnx.OfflineSpeakerSegmentationPyannoteModelConfig(
                    model=SEGMENTATION_MODEL,
                ),
                num_threads=num_threads,
                provider=onnx_provider,
            ),
            embedding=sherpa_onnx.SpeakerEmbeddingExtractorConfig(
                model=EMBEDDING_MODEL,
                num_threads=num_threads,
                provider=onnx_provider,
            ),
            clustering=sherpa_onnx.FastClusteringConfig(
                num_clusters=num_speakers, threshold=cluster_threshold,
            ),
            min_duration_on=0.3,
            min_duration_off=0.5,
        )
        if not config.validate():
            raise RuntimeError(
                "Некорректный конфиг sherpa-onnx — проверьте, что модели "
                f"скачались в {MODELS_DIR}"
            )
                # ВАЖНО: num_speakers "зашит" в конфиг на момент создания sd.
                # Если для разных файлов нужно разное число спикеров, либо создавайте
                # отдельный VoiceProcessor на каждый профиль (кластеризация — лёгкая
                # часть, а вот сами ONNX-модели грузить второй раз не придётся, если
                # вынести их пути в общие константы, как сейчас), либо оставляйте -1
                # (автоопределение) как безопасный дефолт.
        self.diar_pipeline = sherpa_onnx.OfflineSpeakerDiarization(config)
        super().__init__()
    def diarize(self,wav_path: str)->list[dict]:
        audio, sample_rate = sf.read(wav_path, dtype="float32", always_2d=True)
        audio = audio[:, 0]

        if sample_rate != self.diar_pipeline.sample_rate:
            raise RuntimeError(
                f"Ожидался sample rate {self.diar_pipeline.sample_rate}, "
                f"получен {sample_rate}. Проверьте convert_ogg_to_wav."
            )

        diar_result = self.diar_pipeline.process(audio).sort_by_start_time()
        return [
            {"start": float(r.start), "end": float(r.end), "speaker": f"SPEAKER_{r.speaker:02d}"}
            for r in diar_result
        ]
