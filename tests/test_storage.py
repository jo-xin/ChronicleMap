# tests/test_storage.py
from pathlib import Path

from PIL import Image

from chroniclemap.core.models import FilterType, new_campaign
from chroniclemap.storage.manager import (
    create_campaign_on_disk,
    import_image_into_campaign,
    load_campaign_from_disk,
    save_campaign_to_disk,
)


def test_create_save_load_campaign(tmp_path):
    base = tmp_path
    camp = new_campaign("camp-a", path=None)
    root = create_campaign_on_disk(base, camp)
    assert (root / "metadata.json").exists()
    loaded = load_campaign_from_disk(root)
    assert loaded.name == camp.name
    # update and save
    loaded.notes = "hello"
    save_campaign_to_disk(loaded)
    reloaded = load_campaign_from_disk(root)
    assert reloaded.notes == "hello"


def test_import_image_creates_files_and_metadata(tmp_path):
    base = tmp_path
    camp = new_campaign("camp-b", path=None)
    _root = create_campaign_on_disk(base, camp)

    # create a simple image file to import
    src = base / "tmp_img.png"
    im = Image.new("RGBA", (800, 600), color=(123, 222, 111, 255))
    im.save(src)

    snap = import_image_into_campaign(
        campaign=camp,
        src_path=src,
        filter_type=FilterType.REALMS,
        date_str="1444-11-11",
    )
    # check files exist
    dest = Path(snap.path)
    assert dest.exists()
    # thumbnail exists
    thumb = Path(snap.thumbnail)
    assert thumb.exists()
    # metadata contains snapshot
    loaded = load_campaign_from_disk(Path(camp.path))
    assert any(
        s["date"].startswith("1444-11-11") for s in loaded.to_dict()["snapshots"]
    )
