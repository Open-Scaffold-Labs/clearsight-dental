# ClearSight Dental — hosted pilot backend
#
# Base image: PyTorch with CUDA 12.1, matches Fly.io A100 GPU machines.
# See: https://fly.io/docs/gpus/
FROM pytorch/pytorch:2.3.1-cuda12.1-cudnn8-runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/app/hf-cache \
    TRANSFORMERS_CACHE=/app/hf-cache \
    MODEL_DIR=/app/models/oralgpt-omni-7b

WORKDIR /app

# System deps (DICOM reading, image processing, healthcheck curl)
RUN apt-get update && apt-get install -y --no-install-recommends \
    git curl ca-certificates libgl1 libglib2.0-0 libgomp1 \
 && rm -rf /var/lib/apt/lists/*

# Python deps
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Vendored OralAgent (cloned per runbook Step 4)
COPY vendor/OralAgent /app/vendor/OralAgent
RUN pip install --no-cache-dir -e /app/vendor/OralAgent || true

# Application
COPY app /app/app
COPY fixtures /app/fixtures
COPY ORALAGENT_PINNED_COMMIT.txt /app/

# Bake model into image (big; keeps cold start fast)
#
# NOTE: You ran `huggingface-cli download` per runbook Step 3; the model lives
# at /Users/daleraaen/Projects/clearsight-dental/backend/models/oralgpt-omni-7b
# and gets COPYd in here. If you prefer a slimmer image that pulls from HF on
# first boot, comment out the COPY and rely on HF_TOKEN at runtime.
COPY models/oralgpt-omni-7b /app/models/oralgpt-omni-7b

EXPOSE 8000

# Healthcheck: Fly uses this to mark the machine healthy
HEALTHCHECK --interval=30s --timeout=10s --start-period=180s --retries=3 \
  CMD curl -f http://localhost:8000/healthz || exit 1

# One uvicorn worker; the GPU is the serialization point anyway
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--log-level", "info"]
