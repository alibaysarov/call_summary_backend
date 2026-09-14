FILE ?= files/test.ogg
DEVICE ?= cpu
COMPUTE_TYPE ?= int8
STATS ?=
PORT ?= 8010

CUDA_LIBS := $(CURDIR)/.venv/lib/python3.14/site-packages/nvidia/cublas/lib:$(CURDIR)/.venv/lib/python3.14/site-packages/nvidia/cudnn/lib

.PHONY: dev server server-cpu server-gpu

dev:
	LD_LIBRARY_PATH="$(CUDA_LIBS):$${LD_LIBRARY_PATH}" uv run call-summary "$(FILE)" --device "$(DEVICE)" --compute-type "$(COMPUTE_TYPE)" $(if $(STATS),--stats,)

# Универсальная команда: DEVICE/COMPUTE_TYPE берутся из переменных окружения
# внутри server.py (lifespan), поэтому сам код менять не нужно —
# переключение CPU <-> GPU целиком через Makefile.
server:
	LD_LIBRARY_PATH="$(CUDA_LIBS):$${LD_LIBRARY_PATH}" DEVICE="$(DEVICE)" COMPUTE_TYPE="$(COMPUTE_TYPE)" uv run uvicorn server:app --host 0.0.0.0 --port $(PORT)
# Явные шорткаты — чтобы не вспоминать нужные флаги руками
server-cpu:
	$(MAKE) server DEVICE=cpu COMPUTE_TYPE=int8

server-gpu:
	$(MAKE) server DEVICE=cuda COMPUTE_TYPE=float16