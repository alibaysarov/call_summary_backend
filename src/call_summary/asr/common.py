
import os
import tarfile
import urllib.request

from call_summary.settings import (
    EMBEDDING_MODEL,
    EMBEDDING_URL,
    MODELS_DIR,
    SEGMENTATION_MODEL,
    SEGMENTATION_URL,
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
