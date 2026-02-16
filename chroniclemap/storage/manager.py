# chroniclemap/storage/manager.py
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Optional, Tuple

from PIL import Image

from chroniclemap.core.models import (
    Campaign,
    FilterType,
    Snapshot,
    _ensure_date,
    new_snapshot,
)

# constants
META_FILENAME = "metadata.json"
MAPS_DIRNAME = "maps"
THUMBS_DIRNAME = "thumbnails"


def _atomic_write(path: Path, data: str) -> None:
    """
    Atomically write text data to path. Write to temporary then replace.
    """
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(data, encoding="utf-8")
    tmp.replace(path)


def _ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def create_campaign_on_disk(base_dir: Path, campaign: Campaign) -> Path:
    """
    Create directory structure on disk for a campaign and write initial metadata.
    Returns the campaign root path (Path).
    """
    campaign_root = base_dir / campaign.name
    _ensure_dir(campaign_root)
    # maps and thumbnails dirs
    _ensure_dir(campaign_root / MAPS_DIRNAME)
    _ensure_dir(campaign_root / THUMBS_DIRNAME)
    # ensure filter subfolders won't be created until images are imported
    campaign.path = str(campaign_root)
    campaign.created_at = campaign.created_at or ""
    campaign.modified_at = campaign.modified_at or ""
    # write metadata
    meta_path = campaign_root / META_FILENAME
    _atomic_write(meta_path, campaign.to_json())
    return campaign_root


def load_campaign_from_disk(campaign_root: Path) -> Campaign:
    """
    Load Campaign from campaign_root/metadata.json.
    """
    meta_path = campaign_root / META_FILENAME
    if not meta_path.exists():
        raise FileNotFoundError(f"{meta_path} not found")
    data = meta_path.read_text(encoding="utf-8")
    camp = Campaign.from_json(data)
    camp.path = str(campaign_root)
    return camp


def save_campaign_to_disk(campaign: Campaign) -> None:
    """
    Save campaign metadata to campaign.path/metadata.json atomically.
    """
    if not campaign.path:
        raise ValueError("campaign.path must be set to save to disk")
    campaign.modified_at = campaign.modified_at  # let caller update if desired
    campaign_root = Path(campaign.path)
    _ensure_dir(campaign_root)
    meta_path = campaign_root / META_FILENAME
    _atomic_write(meta_path, campaign.to_json())


def _make_image_filename(
    date_iso: str, ext: str = ".png", suffix: Optional[int] = None
) -> str:
    base = date_iso
    if suffix is not None:
        return f"{base}-{suffix}{ext}"
    return f"{base}{ext}"


def _safe_copy_image_to_target(src: Path, target_dir: Path, date_iso: str) -> Path:
    """
    Copy src into target_dir using name date_iso + extension.
    If file exists, append -N suffix.
    Returns the new Path.
    """
    _ensure_dir(target_dir)
    ext = src.suffix or ".png"
    candidate = target_dir / _make_image_filename(date_iso, ext=ext, suffix=None)
    suffix = 1
    while candidate.exists():
        candidate = target_dir / _make_image_filename(date_iso, ext=ext, suffix=suffix)
        suffix += 1
    shutil.copy2(src, candidate)
    return candidate


def _make_thumbnail(
    image_path: Path, thumbs_dir: Path, size: Tuple[int, int] = (400, 400)
) -> Path:
    """
    Create thumbnail for image_path under thumbs_dir. Returns thumbnail path (relative to campaign root).
    """
    _ensure_dir(thumbs_dir)
    thumb_name = image_path.stem + ".jpg"
    thumb_path = thumbs_dir / thumb_name
    try:
        with Image.open(image_path) as im:
            im.thumbnail(size)
            # save as JPEG for smaller size
            im.convert("RGB").save(thumb_path, format="JPEG", quality=85)
    except Exception:
        # if PIL fails, fallback to copying original (not ideal)
        shutil.copy2(image_path, thumb_path)
    return thumb_path


def import_image_into_campaign(
    campaign: Campaign,
    src_path: Path,
    filter_type: FilterType | str,
    date_str: Optional[str] = None,
    *,
    create_dirs_if_missing: bool = True,
) -> Snapshot:
    """
    Import an image file into campaign:
      - copy image into campaign/maps/<filter>/<YYYY-MM-DD>.ext (avoid overwrite)
      - generate thumbnail into campaign/thumbnails/
      - create Snapshot object and append to campaign.snapshots, then save metadata to disk
    Returns the Snapshot instance.
    """
    if not campaign.path:
        raise ValueError("campaign.path must be set before importing images")
    campaign_root = Path(campaign.path)
    maps_root = campaign_root / MAPS_DIRNAME
    thumbs_root = campaign_root / THUMBS_DIRNAME
    # normalize filter_type
    if isinstance(filter_type, str):
        try:
            filter_type = FilterType(filter_type)
        except Exception:
            filter_type = FilterType.CUSTOM
    # parse date
    if date_str is None:
        # attempt to use src file's last modified time as fallback
        stat = src_path.stat()
        dt = stat.st_mtime
        # convert to ISO date
        from datetime import datetime

        date_obj = datetime.utcfromtimestamp(dt).date()
    else:
        date_obj = _ensure_date(date_str)
    date_iso = date_obj.isoformat()

    target_filter_dir = maps_root / (
        filter_type.value if isinstance(filter_type, FilterType) else str(filter_type)
    )
    if create_dirs_if_missing:
        _ensure_dir(target_filter_dir)

    # copy file safely
    dest_path = _safe_copy_image_to_target(src_path, target_filter_dir, date_iso)

    # thumbnail
    thumb_path = _make_thumbnail(dest_path, thumbs_root)

    # create Snapshot
    snap = new_snapshot(
        date_str=date_obj,
        filter_type=filter_type,
        path=str(dest_path),
        thumbnail=str(thumb_path),
    )
    campaign.add_snapshot(snap)

    # update metadata on disk
    save_campaign_to_disk(campaign)

    return snap
