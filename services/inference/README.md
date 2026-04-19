# ClearSight Dental — Inference Service

Local multi-model dental X-ray analysis service. Runs three model families side-by-side:

| Role | Model (actual) | Stands in for | Source |
|---|---|---|---|
| Detection (bounding boxes) | `lio311/dental-caries-yolov8` | YOLOv8 caries detector | HuggingFace |
| Vision Foundation Model | `facebook/dinov2-base` | DentVFM (not on HF yet) | HuggingFace |
| Multimodal reasoning | `OralGPT/OralGPT-Captioning-4B-Base` | DentalGPT (paper only, not on HF) | HuggingFace |

As of April 2026, `DentVFM` and `DentalGPT` are cited in papers but their weights are not on HuggingFace Hub. The two substitutes above preserve each role's architecture so swapping to real weights later is a config change in `config.py`, not a rewrite.

## Run

```bash
source .venv/bin/activate
uvicorn app:app --reload --host 127.0.0.1 --port 8000
```

Endpoints:
- `POST /analyze` — multipart upload of one X-ray image, runs enabled models, returns merged JSON
- `GET  /health` — liveness + model load status
- `GET  /models` — which model each role is currently using

First call downloads weights (~1–3GB total) into `models_cache/`. Subsequent calls are cached.
