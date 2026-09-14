import os

from dotenv import load_dotenv

# Load variables from the .env file
load_dotenv()

PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))
MODELS_DIR = os.path.join(PACKAGE_DIR, "models")

SEGMENTATION_URL = (
    "https://github.com/k2-fsa/sherpa-onnx/releases/download/"
    "speaker-segmentation-models/sherpa-onnx-pyannote-segmentation-3-0.tar.bz2"
)
SEGMENTATION_DIR = os.path.join(
    MODELS_DIR, "sherpa-onnx-pyannote-segmentation-3-0"
)
SEGMENTATION_MODEL = os.path.join(SEGMENTATION_DIR, "model.onnx")

EMBEDDING_URL = (
    "https://github.com/k2-fsa/sherpa-onnx/releases/download/"
    "speaker-recongition-models/wespeaker_en_voxceleb_resnet34_LM.onnx"
)
EMBEDDING_MODEL = os.path.join(
    MODELS_DIR, "wespeaker_en_voxceleb_resnet34_LM.onnx"
)

DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_TOKEN")
