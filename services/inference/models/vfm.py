"""Vision Foundation Model adapter (stands in for DentVFM).

Uses DINOv2-base. Returns a global image embedding and a patch-variance
proxy score until DentVFM releases real weights + downstream heads.
"""
from __future__ import annotations

import logging
import time

import numpy as np
from PIL import Image

import config

log = logging.getLogger("vfm")


class VisionFoundationModel:
    def __init__(self):
        self.model = None
        self.processor = None
        self.device = None

    def load(self):
        from transformers import AutoImageProcessor, AutoModel
        import torch

        spec = config.MODELS["vfm"]
        model_id = spec["model_id"]
        self.device = config.DEVICE or ("mps" if torch.backends.mps.is_available() else "cpu")

        self.processor = AutoImageProcessor.from_pretrained(
            model_id, cache_dir=str(config.CACHE_DIR)
        )
        self.model = AutoModel.from_pretrained(
            model_id, cache_dir=str(config.CACHE_DIR)
        ).to(self.device).eval()
        log.info("Loaded VFM: %s on %s", model_id, self.device)

    def run(self, image: Image.Image) -> dict:
        import torch

        if self.model is None:
            self.load()

        start = time.perf_counter()
        rgb = image.convert("RGB")
        with torch.no_grad():
            inputs = self.processor(images=rgb, return_tensors="pt")
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
            out = self.model(**inputs)

        last = out.last_hidden_state
        cls_emb = last[:, 0, :].squeeze(0).cpu().numpy()
        patch_emb = last[:, 1:, :].squeeze(0).cpu().numpy()
        patch_variance = float(np.mean(np.var(patch_emb, axis=0)))

        elapsed_ms = int((time.perf_counter() - start) * 1000)
        spec = config.MODELS["vfm"]
        return {
            "role": "vfm",
            "model": spec["display_name"],
            "stands_in_for": spec.get("stands_in_for"),
            "elapsed_ms": elapsed_ms,
            "embedding_dim": int(cls_emb.shape[0]),
            "embedding_preview": [round(float(x), 4) for x in cls_emb[:8].tolist()],
            "patch_variance": round(patch_variance, 4),
            "note": "Patch variance is a proxy until DentVFM releases; real VFM would route this embedding to a fine-tuned classification/segmentation head.",
        }
