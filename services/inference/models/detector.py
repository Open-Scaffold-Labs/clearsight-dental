"""YOLOv8 detection adapter.

Loads a pre-fine-tuned dental YOLO from HuggingFace. Falls back to stock
YOLOv8n (COCO) if dental weights aren't downloadable, with outputs marked
[fallback:...] so the UI can surface the fallback clearly.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Optional

from PIL import Image

import config

log = logging.getLogger("detector")

# Test-system default: low threshold so we surface lower-confidence hits
# for review. Production would raise this to ~0.25 after validation.
DEFAULT_CONF_THRESHOLD = 0.05
DEFAULT_IOU_THRESHOLD = 0.5


@dataclass
class Detection:
    class_name: str
    confidence: float
    bbox: List[float]  # [x1, y1, x2, y2] in pixels

    def to_dict(self):
        return asdict(self)


class DentalDetector:
    def __init__(self, conf: float = DEFAULT_CONF_THRESHOLD, iou: float = DEFAULT_IOU_THRESHOLD):
        self.model = None
        self.using_fallback = False
        self.model_path: Optional[str] = None
        self.conf = conf
        self.iou = iou

    def load(self):
        from ultralytics import YOLO
        from huggingface_hub import hf_hub_download

        spec = config.MODELS["detector"]
        repo = spec["model_id"]
        filename = spec.get("weight_filename", "best.pt")

        candidates = [filename, "best.pt", "model.pt", "yolov8n.pt"]
        tried = []
        for fname in candidates:
            try:
                path = hf_hub_download(
                    repo_id=repo, filename=fname, cache_dir=str(config.CACHE_DIR)
                )
                self.model = YOLO(path)
                self.model_path = path
                log.info("Loaded dental detector: %s/%s", repo, fname)
                return
            except Exception as e:
                tried.append(f"{fname}: {type(e).__name__}")

        log.warning("Dental weights not found (%s). Falling back to yolov8n.pt", tried)
        self.model = YOLO("yolov8n.pt")
        self.using_fallback = True
        self.model_path = "yolov8n.pt"

    def run(self, image: Image.Image) -> dict:
        if self.model is None:
            self.load()
        start = time.perf_counter()
        results = self.model.predict(
            source=image, verbose=False, conf=self.conf, iou=self.iou,
        )
        elapsed_ms = int((time.perf_counter() - start) * 1000)

        detections: List[Detection] = []
        if results:
            r = results[0]
            names = r.names or {}
            if r.boxes is not None:
                for box in r.boxes:
                    cls_idx = int(box.cls[0]) if box.cls is not None else -1
                    conf = float(box.conf[0]) if box.conf is not None else 0.0
                    xyxy = box.xyxy[0].tolist() if box.xyxy is not None else [0, 0, 0, 0]
                    label = names.get(cls_idx, f"class_{cls_idx}")
                    if self.using_fallback:
                        label = f"[fallback:{label}]"
                    detections.append(Detection(class_name=label, confidence=conf, bbox=xyxy))

        return {
            "role": "detector",
            "model": Path(self.model_path).name if self.model_path else "unknown",
            "using_fallback": self.using_fallback,
            "conf_threshold": self.conf,
            "elapsed_ms": elapsed_ms,
            "detections": [d.to_dict() for d in detections],
        }
