import sys; sys.path.insert(0, ".")
import config; config.DEVICE = config.pick_device()
from PIL import Image
from models.detector import DentalDetector

det = DentalDetector(); det.load()
for name in ["data.png", "output.png"]:
    img = Image.open(f"test_images/{name}")
    print(f"--- {name}  {img.size} ---")
    r = det.run(img)
    ms = r["elapsed_ms"]
    n = len(r["detections"])
    print(f"  {n} detections in {ms}ms")
    for d in r["detections"][:10]:
        cls = d["class_name"]
        conf = d["confidence"]
        bbox = [round(x, 0) for x in d["bbox"]]
        print(f"    {cls}  conf={conf:.2f}  bbox={bbox}")
