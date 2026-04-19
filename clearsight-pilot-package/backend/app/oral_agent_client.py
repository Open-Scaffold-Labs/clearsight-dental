"""OralAgent + OralGPT-Omni client.

This module isolates all model-specific code behind a stable async interface.
For the pilot we run OralGPT-Omni-7B directly via transformers on a single
A100-40GB GPU, with a semaphore to enforce MAX_CONCURRENT=1 (so we never
OOM the card under burst load).

Design goals:
  - Load once at startup (slow: ~60-120s for a 7B VLM on A100 from cold)
  - Single-flight inference (semaphore) — A100-40GB cannot run two 7B VLMs concurrently
  - Swap-in point for OralAgent's LangGraph orchestrator once we vendor it
  - Clean error surface: ModelNotReady distinguishes boot-in-progress vs hard failure
"""
from __future__ import annotations

import asyncio
import base64
import logging
from typing import Any

log = logging.getLogger("clearsight.agent")


class ModelNotReady(RuntimeError):
    """Raised when /analyze is called before the model has finished loading."""


class OralAgentClient:
    """Thin async wrapper around OralGPT-Omni inference.

    Not thread-safe across event loops, but safe for concurrent asyncio tasks
    (the semaphore serializes GPU work).
    """

    def __init__(self, *, model_dir: str, model_name: str, max_concurrent: int = 1) -> None:
        self.model_dir = model_dir
        self.model_name = model_name
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._ready = False
        self._model = None
        self._processor = None

    async def load(self) -> None:
        """Load the model onto GPU. Called once during FastAPI lifespan startup."""
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._load_sync)
        self._ready = True

    def _load_sync(self) -> None:
        # Imports are deferred so the import graph does not require torch
        # during unit tests of unrelated modules.
        import torch  # noqa: F401 (kept to force CUDA availability check early)
        from transformers import AutoModelForCausalLM, AutoProcessor

        log.info("loading processor from %s", self.model_dir)
        self._processor = AutoProcessor.from_pretrained(
            self.model_dir,
            trust_remote_code=True,
        )
        log.info("loading model from %s (this takes 60-120s on cold start)", self.model_dir)
        self._model = AutoModelForCausalLM.from_pretrained(
            self.model_dir,
            torch_dtype="auto",
            device_map="auto",
            trust_remote_code=True,
        )
        self._model.eval()
        log.info("model loaded; ready for inference")

    def is_ready(self) -> bool:
        return self._ready and self._model is not None

    async def aclose(self) -> None:
        # Nothing to do today — transformers models are GC'd with the process.
        # If we move to vLLM or a separate inference server, wire teardown here.
        self._ready = False

    async def analyze(
        self,
        *,
        image_bytes: bytes,
        content_type: str,
        modality: str,
        prompt: str | None,
    ) -> dict[str, Any]:
        """Run a single-image analysis.

        For the pilot we return a structured dict with a 'findings' list that
        the frontend renders as cards. Production will expand this to the full
        OralAgent multi-step workflow (detection -> reasoning -> report).
        """
        if not self.is_ready():
            raise ModelNotReady("model has not finished loading")

        async with self._semaphore:
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(
                None,
                self._infer_sync,
                image_bytes,
                content_type,
                modality,
                prompt,
            )

    def _infer_sync(
        self,
        image_bytes: bytes,
        content_type: str,
        modality: str,
        prompt: str | None,
    ) -> dict[str, Any]:
        """Synchronous inference path. Runs on the default executor thread."""
        from io import BytesIO
        from PIL import Image
        import torch

        # Convert DICOM on the fly if needed — pilot accepts JPEG/PNG/DICOM
        if content_type == "application/dicom":
            import pydicom
            ds = pydicom.dcmread(BytesIO(image_bytes))
            arr = ds.pixel_array
            # Normalize to 8-bit grayscale for the VLM.
            arr_min, arr_max = arr.min(), arr.max()
            if arr_max > arr_min:
                arr = ((arr - arr_min) / (arr_max - arr_min) * 255).astype("uint8")
            img = Image.fromarray(arr).convert("RGB")
        else:
            img = Image.open(BytesIO(image_bytes)).convert("RGB")

        # Build the clinical prompt. Pilot uses a single modality-aware template;
        # the OralAgent LangGraph will replace this once vendored.
        default_prompts = {
            "opg": (
                "You are an AI assistant reviewing a panoramic dental radiograph (OPG). "
                "Identify visible findings such as caries, periapical lesions, impacted "
                "teeth, alveolar bone loss, and restorations. For each finding, note its "
                "approximate location (e.g., tooth number or quadrant) and a short "
                "explanation. Do not provide a diagnosis or treatment plan. This output "
                "is for clinician review only."
            ),
            "periapical": (
                "You are an AI assistant reviewing a periapical dental radiograph. "
                "Identify visible findings around the root apices including caries, "
                "periapical lesions, and bone loss. Note affected tooth numbers. "
                "For clinician review only."
            ),
            "ceph": (
                "You are an AI assistant reviewing a cephalometric radiograph. "
                "Describe visible skeletal and dental landmarks. For clinician review only."
            ),
            "intraoral": (
                "You are an AI assistant reviewing an intraoral photograph. "
                "Describe visible soft tissue and dental findings. For clinician review only."
            ),
        }
        system_prompt = prompt or default_prompts.get(modality, default_prompts["opg"])

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image"},
                    {"type": "text", "text": system_prompt},
                ],
            }
        ]

        # Qwen2.5-VL / OralGPT-Omni template path. We use the processor's
        # chat template to stay model-agnostic — if the OralGPT-Omni checkpoint
        # ships a different template, trust_remote_code picks it up.
        inputs = self._processor.apply_chat_template(
            messages,
            add_generation_prompt=True,
            tokenize=True,
            return_tensors="pt",
            return_dict=True,
            images=[img],
        )
        inputs = {k: v.to(self._model.device) for k, v in inputs.items()}

        with torch.inference_mode():
            output_ids = self._model.generate(
                **inputs,
                max_new_tokens=512,
                do_sample=False,
                temperature=1.0,
            )
        # Strip the prompt from the output before decoding.
        input_len = inputs["input_ids"].shape[1]
        generated = output_ids[:, input_len:]
        text = self._processor.batch_decode(generated, skip_special_tokens=True)[0].strip()

        return {
            "raw": text,
            "findings": self._parse_findings(text),
        }

    @staticmethod
    def _parse_findings(text: str) -> list[dict[str, str]]:
        """Parse the VLM's free-text output into a list of structured findings.

        The pilot uses a deliberately forgiving parser: any bullet-like line
        becomes a finding. We will replace this with the OralAgent structured
        output schema once the LangGraph is vendored.
        """
        findings: list[dict[str, str]] = []
        for raw_line in text.splitlines():
            line = raw_line.strip().lstrip("-*• ").strip()
            if not line or len(line) < 4:
                continue
            # Heuristic: lines starting with "Finding" or numbered are definitely findings.
            findings.append({"text": line})
        if not findings:
            findings.append({"text": text.strip()})
        return findings
