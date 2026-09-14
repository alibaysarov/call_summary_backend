import argparse
import os

from dotenv import load_dotenv

from .gpu_stats import GpuStats
from .voice import transcribe_and_diarize_ogg
from .voice_local import transcribe_and_diarize_ogg_local
load_dotenv()


def main():
    parser = argparse.ArgumentParser(description="Транскрибация голосового сообщения с диаризацией")
    parser.add_argument("file", help="Путь к .ogg-файлу")
    parser.add_argument("--model", default="small", help="Размер модели Whisper")
    parser.add_argument("--device", default="cpu", choices=("cpu", "cuda"))
    parser.add_argument("--compute-type", default="int8")
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Собрать статистику GPU, VRAM, CPU, RAM и ядер в gpu.csv и gpu.png",
    )
    args = parser.parse_args()

    token = os.environ.get("HF_TOKEN")
    if not token:
        raise RuntimeError(
            "Не найден HF_TOKEN. Выполните: export HF_TOKEN=\"ваш_токен\""
        )

    stats = GpuStats() if args.stats else None
    if stats:
        stats.start()
    try:
        result_text = transcribe_and_diarize_ogg_local(
            ogg_path=args.file,
            hf_token=token,
            model_size=args.model,
            device=args.device,
            compute_type=args.compute_type,
        )
    finally:
        if stats:
            stats.stop()
    print(result_text)

if __name__ == "__main__":
    main()