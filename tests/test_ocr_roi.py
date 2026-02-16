# tests/test_ocr_roi.py

from chroniclemap.vision.ocr import DEFAULT_ROI_TEMPLATES, compute_roi


def test_compute_roi_absolute():
    w, h = 1920, 1080
    roi = (1460, 1040, 1720, 1080)
    out = compute_roi((w, h), roi_spec=roi)
    assert out == roi


def test_compute_roi_relative():
    w, h = 1280, 720
    rel = (0.75, 0.9, 1.0, 1.0)
    out = compute_roi((w, h), roi_spec=rel)
    assert out == (int(0.75 * w), int(0.9 * h), w, h)


def test_template_match_and_fallback():
    w, h = 1920, 1080
    out = compute_roi((w, h), roi_spec=None, template_key="ck3")
    # should match the template provided earlier
    assert out == DEFAULT_ROI_TEMPLATES["ck3"]["1920x1080"]
