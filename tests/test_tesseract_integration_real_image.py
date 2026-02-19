# tests/test_tesseract_integration_real_image.py
import shutil
from pathlib import Path

import pytest

# safe import
try:
    import pytesseract  # noqa: F401
except Exception:
    pytesseract = None

from chroniclemap.core.models import GameDate
from chroniclemap.vision.ocr import TesseractOCRProvider

# determine skip condition: either pytesseract not installed or tesseract binary not found
skip_condition = (pytesseract is None) or (shutil.which("tesseract") is None)


@pytest.mark.skipif(
    skip_condition, reason="pytesseract or tesseract binary not available"
)
def test_tesseract_extracts_date_from_real_image(tmp_path):
    """
    Integration test using real TesseractOCRProvider and a provided sample image
    tests/map_1066-09-15_realms.png which should contain '1066-09-15' in the ROI.
    """
    repo_root = Path(__file__).parent.parent.resolve()
    img_path = repo_root / "tests" / "map_1066-09-15_realms.png"
    assert img_path.exists(), f"Test image not found at {img_path}"

    # instantiate provider; ensure language includes english+chi_sim as needed
    prov = TesseractOCRProvider(lang="chi_sim+eng")

    # call extract_date: use template_key if your test image matches a template (e.g., "ck3")
    # If your image has different resolution / ROI, you can pass template_key=None or explicit roi_spec
    found = prov.extract_date(img_path, roi_spec=None, template_key="ck3")
    assert (
        found is not None
    ), "TesseractOCRProvider returned None (no date found in ROI)."

    # parse with GameDate to ensure consistent formatting and support very old years
    gd = GameDate.fromiso(found)
    assert gd.year == 1066
    assert gd.month == 9
    assert gd.day == 15
    # or simply compare to expected GameDate
    assert gd == GameDate.fromiso("1066-09-15")
