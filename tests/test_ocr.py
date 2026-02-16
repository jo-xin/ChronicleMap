# tests/test_ocr.py

from chroniclemap.vision.ocr import MockOCRProvider


def test_mock_ocr_from_filename(tmp_path):
    p = tmp_path / "map_1444-11-11_realms.png"
    p.write_text("dummy")
    prov = MockOCRProvider()
    out = prov.extract_date(p)
    assert out == "1444-11-11"


def test_mock_ocr_no_date(tmp_path):
    p = tmp_path / "map_nodate.png"
    p.write_text("x")
    prov = MockOCRProvider()
    out = prov.extract_date(p)
    assert out is None
