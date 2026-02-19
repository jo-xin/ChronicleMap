# tests/test_ocr_tesseract_integration.py
import shutil

import pytest
from PIL import Image, ImageDraw

# safe import
try:
    import pytesseract  # noqa: F401
except Exception:
    pytesseract = None

from chroniclemap.vision.ocr import TesseractOCRProvider, compute_roi

skip_condition = (pytesseract is None) or (shutil.which("tesseract") is None)


@pytest.mark.skipif(
    skip_condition, reason="pytesseract or tesseract binary not available"
)
def test_tesseract_extracts_date_from_synthetic(tmp_path):
    # create synthetic image 1920x1080 with "1066-09-15" at ck3 ROI
    w, h = 1920, 1080
    img = Image.new("RGB", (w, h), color=(30, 30, 30))
    draw = ImageDraw.Draw(img)
    text = "1066-09-15"
    # place text inside ck3 default roi center
    roi = compute_roi((w, h), None, template_key="ck3")
    left, top, right, bottom = roi
    x = left + 5
    y = top + 2
    draw.text((x, y), text, fill=(255, 255, 255))
    p = tmp_path / "ck3_test.png"
    img.save(p)
    # run tesseract provider
    prov = TesseractOCRProvider(lang="chi_sim+eng")
    out = prov.extract_date(p, roi_spec=None, template_key="ck3")
    assert out is not None
    assert out.startswith("1066")
