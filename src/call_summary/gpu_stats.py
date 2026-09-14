from __future__ import annotations

import csv
import shutil
import subprocess
import threading
import time
from pathlib import Path

import psutil


class GpuStats:
    def __init__(self, output_path: str = "gpu.csv", interval: float = 1.0) -> None:
        self.output_path = Path(output_path)
        self.interval = interval
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if shutil.which("nvidia-smi") is None:
            raise RuntimeError(
                "Не найден nvidia-smi. Статистика доступна только при установленном NVIDIA-драйвере."
            )

        self._thread = threading.Thread(target=self._collect, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join()
        if self.output_path.exists():
            self._plot()

    def _collect(self) -> None:
        started_at = time.time()
        cpu_count = psutil.cpu_count(logical=True) or 1
        core_columns = [f"cpu_core_{index + 1}" for index in range(cpu_count)]
        with self.output_path.open("w", newline="") as csv_file:
            writer = csv.writer(csv_file)
            writer.writerow(
                [
                    "timestamp",
                    "gpu_percent",
                    "memory_used",
                    "memory_total",
                    "cpu_percent",
                    "ram_used",
                    "ram_total",
                    "ram_percent",
                    *core_columns,
                ]
            )

            while not self._stop_event.is_set():
                try:
                    output = subprocess.check_output(
                        [
                            "nvidia-smi",
                            "--query-gpu=utilization.gpu,memory.used,memory.total",
                            "--format=csv,noheader,nounits",
                        ],
                        text=True,
                    ).strip()
                    gpu_percent, memory_used, memory_total = [
                        value.strip() for value in output.split(",", maxsplit=2)
                    ]
                    memory = psutil.virtual_memory()
                    core_usage = psutil.cpu_percent(interval=None, percpu=True)
                    writer.writerow(
                        [
                            time.time() - started_at,
                            gpu_percent,
                            memory_used,
                            memory_total,
                            psutil.cpu_percent(interval=None),
                            memory.used // (1024 * 1024),
                            memory.total // (1024 * 1024),
                            memory.percent,
                            *core_usage,
                        ]
                    )
                    csv_file.flush()
                except (subprocess.CalledProcessError, ValueError):
                    pass
                self._stop_event.wait(self.interval)

    def _plot(self) -> None:
        import matplotlib.pyplot as plt
        import pandas as pd

        data = pd.read_csv(self.output_path)
        if data.empty:
            return

        data["seconds"] = data["timestamp"] - data["timestamp"].iloc[0]
        core_columns = [column for column in data if column.startswith("cpu_core_")]
        figure, axes = plt.subplots(4, 1, sharex=True, figsize=(12, 12))
        axes[0].plot(data["seconds"], data["gpu_percent"])
        axes[0].set_ylabel("GPU, %")
        axes[0].grid()
        axes[1].plot(data["seconds"], data["memory_used"])
        axes[1].set_ylabel("VRAM, MiB")
        axes[1].grid()
        axes[2].plot(data["seconds"], data["cpu_percent"], label="CPU")
        axes[2].plot(data["seconds"], data["ram_percent"], label="RAM")
        axes[2].set_ylabel("CPU / RAM, %")
        axes[2].legend()
        axes[2].grid()
        for column in core_columns:
            axes[3].plot(data["seconds"], data[column], linewidth=0.8, label=column)
        axes[3].set_ylabel("Ядра CPU, %")
        axes[3].set_xlabel("Время, сек")
        axes[3].legend(ncol=4, fontsize="x-small")
        axes[3].grid()
        figure.tight_layout()
        figure.savefig(self.output_path.with_suffix(".png"))
        plt.close(figure)
