"""Model registry. Swap real weights here when DentVFM / DentalGPT release."""
from pathlib import Path

BASE = Path(__file__).parent
CACHE_DIR = BASE / "models_cache"
TEST_IMAGES = BASE / "test_images"
OUTPUTS = BASE / "outputs"
for p in (CACHE_DIR, TEST_IMAGES, OUTPUTS):
    p.mkdir(parents=True, exist_ok=True)


def pick_device():
    import torch
    if torch.backends.mps.is_available():
        return "mps"
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


MODELS = {
    "detector": {
        "role": "Bounding-box detection (caries, periapical, etc.)",
        "model_id": "lio311/dental-caries-yolov8",
        "weight_filename": "best.pt",
        "display_name": "YOLOv8-dental (caries)",
        "stands_in_for": None,
    },
    "vfm": {
        "role": "Vision Foundation Model — dense image features",
        "model_id": "facebook/dinov2-base",
        "display_name": "DINOv2-base",
        "stands_in_for": "DentVFM (not on HF as of April 2026)",
    },
    "reasoner": {
        "role": "Multimodal reasoning — natural-language findings",
        "model_id": "OralGPT/OralGPT-Captioning-4B-Base",
        "display_name": "OralGPT-Captioning-4B",
        "stands_in_for": "DentalGPT (paper cited, not on HF)",
    },
}

# Toggle heavy models off to speed up iteration.
ENABLED = {
    "detector": True,
    "vfm": True,
    "reasoner": False,  # 4B model = ~8GB download; flip on when ready
}

DEVICE = None  # resolved at runtime
MAX_IMAGE_MB = 20
MAX_IMAGE_DIM = 2048
