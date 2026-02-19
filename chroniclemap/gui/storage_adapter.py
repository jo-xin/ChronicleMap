# # chroniclemap/gui/storage_adapter.py
# from __future__ import annotations
# from pathlib import Path
# import shutil
# from datetime import datetime
# from typing import Dict, Optional
# from chroniclemap.gui.campaign_store import CampaignStore


# class StorageManager:
#     """
#     Simple adapter that knows how to import an image file into a campaign's maps/<filter>/YYYY-MM-DD.ext
#     and update metadata.json (snapshots list).
#     """

#     def __init__(self, campaign_store: CampaignStore):
#         self.store = campaign_store

#     def import_image(
#         self,
#         campaign_name: str,
#         src_path: Path,
#         filter_name: str,
#         date_iso: str,
#         note: Optional[str] = None,
#     ) -> Path:
#         campaign_dir = self.store.campaigns_dir / campaign_name
#         if not campaign_dir.exists():
#             raise FileNotFoundError(f"Campaign {campaign_name} not found")

#         maps_dir = campaign_dir / "maps" / filter_name
#         maps_dir.mkdir(parents=True, exist_ok=True)

#         ext = src_path.suffix or ".png"
#         filename = f"{date_iso}{ext}"
#         dest = maps_dir / filename

#         # avoid overwrite: append suffix if exists
#         suffix = 1
#         while dest.exists():
#             filename = f"{date_iso}-{suffix}{ext}"
#             dest = maps_dir / filename
#             suffix += 1

#         shutil.copy2(src_path, dest)

#         # update metadata (append snapshot)
#         meta = self.store._read_metadata(campaign_dir) or {}
#         snapshots = meta.get("snapshots", [])
#         entry = {
#             "filter": filter_name,
#             "path": str(dest.relative_to(campaign_dir)),
#             "date": date_iso,
#             "imported_at": datetime.utcnow().isoformat(),
#             "note": note or "",
#         }
#         snapshots.append(entry)
#         meta["snapshots"] = snapshots
#         meta["modified"] = datetime.utcnow().isoformat()
#         self.store._atomic_write_json(campaign_dir / "metadata.json", meta)

#         return dest
