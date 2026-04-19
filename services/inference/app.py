"""ClearSight Dental — local inference service.

Runs up to three model families side-by-side on each uploaded X-ray:
  - YOLOv8 dental detector  (bounding boxes)
  - DINOv2   (vision foundation model; stands in for DentVFM)
  - OralGPT  (multimodal reasoner; stands in for DentalGPT)

POST /analyze   multipart: 'xray' (image)
GET  /health
GET  /models
"""
from __future__ import annotations

import io
import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from PIL import Image, UnidentifiedImageError

import config
from models.detector import DentalDetector
from models.vfm import VisionFoundationModel
from models.reasoner import Reasoner

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)-10s %(levelname)-7s %(message)s",
)
log = logging.getLogger("app")

STATE = {"detector": None, "vfm": None, "reasoner": None, "ready": False}


@asynccontextmanager
async def lifespan(app: FastAPI):
    config.DEVICE = config.pick_device()
    log.info("Device: %s", config.DEVICE)
    log.info(
        "Model plan: %s",
        {
            k: v["display_name"] + ("" if config.ENABLED[k] else " (disabled)")
            for k, v in config.MODELS.items()
        },
    )
    STATE["ready"] = True
    yield


app = FastAPI(title="ClearSight Dental Inference", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000", "http://127.0.0.1:3000",
        "http://localhost:5179", "http://127.0.0.1:5179",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _ensure_detector():
    if STATE["detector"] is None and config.ENABLED["detector"]:
        STATE["detector"] = DentalDetector()
        STATE["detector"].load()
    return STATE["detector"]


def _ensure_vfm():
    if STATE["vfm"] is None and config.ENABLED["vfm"]:
        STATE["vfm"] = VisionFoundationModel()
        STATE["vfm"].load()
    return STATE["vfm"]


def _ensure_reasoner():
    if STATE["reasoner"] is None and config.ENABLED["reasoner"]:
        STATE["reasoner"] = Reasoner()
        STATE["reasoner"].load()
    return STATE["reasoner"]


@app.get("/health")
def health():
    return {
        "ready": STATE["ready"],
        "device": config.DEVICE,
        "loaded": {k: STATE[k] is not None for k in ("detector", "vfm", "reasoner")},
    }


@app.get("/models")
def models():
    return {
        "device": config.DEVICE,
        "models": {
            k: {**v, "enabled": config.ENABLED.get(k, False), "loaded": STATE[k] is not None}
            for k, v in config.MODELS.items()
        },
    }


def _load_image(file_bytes: bytes) -> Image.Image:
    if len(file_bytes) > config.MAX_IMAGE_MB * 1024 * 1024:
        raise HTTPException(413, f"Image larger than {config.MAX_IMAGE_MB}MB")
    try:
        img = Image.open(io.BytesIO(file_bytes))
        img.load()
    except UnidentifiedImageError:
        raise HTTPException(400, "Could not decode image. Send PNG/JPEG/TIFF.")
    if max(img.size) > config.MAX_IMAGE_DIM:
        ratio = config.MAX_IMAGE_DIM / max(img.size)
        new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
        img = img.resize(new_size, Image.LANCZOS)
        log.info("Resized image to %s", new_size)
    return img


@app.post("/analyze")
async def analyze(xray: UploadFile = File(...)):
    if not xray.content_type or not xray.content_type.startswith("image/"):
        raise HTTPException(400, f"Expected image/*, got {xray.content_type}")

    data = await xray.read()
    image = _load_image(data)

    wall_start = time.perf_counter()
    results = {}
    detector_summary = ""

    if config.ENABLED["detector"]:
        try:
            det = _ensure_detector().run(image)
            results["detector"] = det
            if det.get("detections"):
                detector_summary = "; ".join(
                    f"{d['class_name']} ({d['confidence']:.2f})"
                    for d in det["detections"][:8]
                )
        except Exception as e:
            log.exception("Detector failed")
            results["detector"] = {"role": "detector", "error": str(e)}
    else:
        results["detector"] = {"role": "detector", "disabled": True}

    if config.ENABLED["vfm"]:
        try:
            results["vfm"] = _ensure_vfm().run(image)
        except Exception as e:
            log.exception("VFM failed")
            results["vfm"] = {"role": "vfm", "error": str(e)}
    else:
        results["vfm"] = {"role": "vfm", "disabled": True}

    if config.ENABLED["reasoner"]:
        try:
            results["reasoner"] = _ensure_reasoner().run(image, detector_summary)
        except Exception as e:
            log.exception("Reasoner failed")
            results["reasoner"] = {"role": "reasoner", "error": str(e)}
    else:
        results["reasoner"] = {
            "role": "reasoner",
            "disabled": True,
            "note": "Enable in config.ENABLED['reasoner'] once OralGPT weights are downloaded (~8GB).",
        }

    results["meta"] = {
        "wall_ms": int((time.perf_counter() - wall_start) * 1000),
        "image_size": list(image.size),
        "device": config.DEVICE,
    }
    return JSONResponse(results)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
