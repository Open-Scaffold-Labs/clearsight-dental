"""Direct smoke test: load detector and VFM, run against one DENTEX image."""
import sys, json, time
sys.path.insert(0, ".")
import config
config.DEVICE = config.pick_device()
print(f"Device: {config.DEVICE}")

from PIL import Image
img = Image.open("test_images/dentex.jpg")
print(f"Image: {img.size} mode={img.mode}")

print("\n=== Loading detector ===")
t0 = time.time()
from models.detector import DentalDetector
det = DentalDetector()
det.load()
print(f"loaded in {time.time()-t0:.1f}s  fallback={det.using_fallback}  path={det.model_path}")

print("\n=== Running detector ===")
result = det.run(img)
summary = {k: v for k, v in result.items() if k != "detections"}
print(json.dumps(summary, indent=2))
n = len(result["detections"])
print(f"detections: {n}")
for d in result["detections"][:5]:
    print(f"  {d}")

print("\n=== Loading VFM (DINOv2-base, ~350MB download on first run) ===")
t0 = time.time()
from models.vfm import VisionFoundationModel
vfm = VisionFoundationModel()
vfm.load()
print(f"loaded in {time.time()-t0:.1f}s")

print("\n=== Running VFM ===")
v = vfm.run(img)
print(json.dumps(v, indent=2))
