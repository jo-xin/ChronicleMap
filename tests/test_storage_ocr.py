# tests/test_storage_ocr.py

from PIL import Image

from chroniclemap.core.models import FilterType, new_campaign
from chroniclemap.storage.manager import (
    create_campaign_on_disk,
    import_image_into_campaign,
)
from chroniclemap.vision.ocr import MockOCRProvider


def test_import_with_mock_ocr(tmp_path):
    base = tmp_path
    camp = new_campaign("camp-ocr", path=None)
    _root = create_campaign_on_disk(base, camp)
    # create image named with date in filename
    src = base / "map_1066-09-15_realms.png"
    img = Image.new("RGBA", (1920, 1080), color=(100, 100, 100, 255))
    img.save(src)
    prov = MockOCRProvider()
    snap = import_image_into_campaign(
        campaign=camp,
        src_path=src,
        filter_type=FilterType.REALMS,
        date_str=None,
        ocr_provider=prov,
        ocr_roi_spec=None,
        ocr_template_key="ck3",
    )
    assert snap is not None
    assert snap.date.year == 1066
