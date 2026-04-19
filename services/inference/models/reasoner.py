"""Multimodal reasoning adapter (stands in for DentalGPT).

Loads OralGPT-Captioning-4B. Disabled by default in config.ENABLED
because the 4B model is ~8GB. Flip on once downloaded.
"""
from __future__ import annotations

import logging
import time

from PIL import Image

import config

log = logging.getLogger("reasoner")


class Reasoner:
    def __init__(self):
        self.model = None
        self.processor = None
        self.device = None

    def load(self):
        from transformers import AutoProcessor, AutoModelForCausalLM
        import torch

        spec = config.MODELS["reasoner"]
        model_id = spec["model_id"]
        self.device = config.DEVICE or ("mps" if torch.backends.mps.is_available() else "cpu")
        dtype = torch.float16 if self.device != "cpu" else torch.float32

        self.processor = AutoProcessor.from_pretrained(
            model_id, cache_dir=str(config.CACHE_DIR), trust_remote_code=True
        )
        self.model = AutoModelForCausalLM.from_pretrained(
            model_id,
            cache_dir=str(config.CACHE_DIR),
            torch_dtype=dtype,
            trust_remote_code=True,
        ).to(self.device).eval()
        log.info("Loaded reasoner: %s on %s", model_id, self.device)

    def run(self, image: Image.Image, detector_summary: str = "") -> dict:
        import torch

        if self.model is None:
            self.load()

        prompt = (
            "You are a dental radiology assistant. Describe clinically relevant "
            "findings visible in this X-ray (caries, periapical lesions, bone loss, "
            "impacted teeth, restorations). Be concise. Do not diagnose."
        )
        if detector_summary:
            prompt += f"\n\nDetector output (for context): {detector_summary}"

        start = time.perf_counter()
        try:
            inputs = self.processor(images=image.convert("RGB"), text=prompt, return_tensors="pt")
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
            with torch.no_grad():
                out = self.model.generate(**inputs, max_new_tokens=200, do_sample=False)
            text = self.processor.batch_decode(out, skip_special_tokens=True)[0]
        except Exception as e:
            log.exception("Reasoner generate failed")
            return {
                "role": "reasoner",
                "model": config.MODELS["reasoner"]["display_name"],
                "error": f"{type(e).__name__}: {e}",
                "elapsed_ms": int((time.perf_counter() - start) * 1000),
            }

        elapsed_ms = int((time.perf_counter() - start) * 1000)
        spec = config.MODELS["reasoner"]
        return {
            "role": "reasoner",
            "model": spec["display_name"],
            "stands_in_for": spec.get("stands_in_for"),
            "elapsed_ms": elapsed_ms,
            "prompt": prompt,
            "response": text,
        }
