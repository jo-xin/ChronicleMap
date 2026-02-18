# chroniclemap/gui/campaign_store.py
from __future__ import annotations

import json
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

DEFAULT_METADATA = {
    "name": None,
    "created": None,
    "modified": None,
    "note": "",
    "filters": ["Political", "Religious", "Culture"],
    "snapshots": [],  # list of snapshot entries
}


class CampaignStore:
    """
    Simple filesystem-backed Campaign store.

    Root layout:
      /root/
        /Campaigns/
          /<campaign_name>/
            metadata.json
            maps/...
            thumbnails/...
    """

    def __init__(self, root: Path):
        self.root = Path(root)
        self.campaigns_dir = self.root / "Campaigns"
        self.campaigns_dir.mkdir(parents=True, exist_ok=True)

    def list_campaigns(self) -> List[Dict]:
        result = []
        for p in sorted(self.campaigns_dir.iterdir()):
            if p.is_dir():
                meta = self._read_metadata(p)
                result.append({"name": p.name, "path": str(p), "metadata": meta})
        return result

    def create_campaign(self, name: str) -> Path:
        safe_name = self._sanitize_name(name)
        path = self.campaigns_dir / safe_name
        if path.exists():
            raise FileExistsError(f"Campaign '{safe_name}' already exists")
        path.mkdir(parents=True)
        (path / "maps").mkdir(exist_ok=True)
        (path / "thumbnails").mkdir(exist_ok=True)
        metadata = DEFAULT_METADATA.copy()
        metadata["name"] = safe_name
        now = datetime.now(timezone.utc).isoformat()
        metadata["created"] = now
        metadata["modified"] = now
        self._atomic_write_json(path / "metadata.json", metadata)
        return path

    def delete_campaign(self, name: str) -> None:
        path = self.campaigns_dir / name
        if not path.exists():
            raise FileNotFoundError(f"Campaign '{name}' not found")
        # remove directory tree
        shutil.rmtree(path)

    def rename_campaign(self, old: str, new: str) -> Path:
        old_path = self.campaigns_dir / old
        if not old_path.exists():
            raise FileNotFoundError(old)
        new_safe = self._sanitize_name(new)
        new_path = self.campaigns_dir / new_safe
        if new_path.exists():
            raise FileExistsError(new_safe)
        old_path.rename(new_path)
        # update metadata.name
        meta = self._read_metadata(new_path)
        meta["name"] = new_safe
        meta["modified"] = datetime.now(timezone.utc).isoformat()
        self._atomic_write_json(new_path / "metadata.json", meta)
        return new_path

    def load_metadata(self, name: str) -> Dict:
        path = self.campaigns_dir / name
        return self._read_metadata(path)

    def save_metadata(self, name: str, metadata: Dict) -> None:
        path = self.campaigns_dir / name
        if not path.exists():
            raise FileNotFoundError(name)
        metadata["modified"] = datetime.now(timezone.utc).isoformat()
        self._atomic_write_json(path / "metadata.json", metadata)

    # ---- internal helpers ----
    def _read_metadata(self, path: Path) -> Dict:
        meta_file = path / "metadata.json"
        if not meta_file.exists():
            return {}
        try:
            with meta_file.open("r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _atomic_write_json(self, path: Path, data: Dict) -> None:
        # write to temp and replace
        tmp_fd, tmp_path = tempfile.mkstemp(dir=str(path.parent))
        try:
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            os.replace(tmp_path, str(path))
        finally:
            # ensure no leftover
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass

    def _sanitize_name(self, name: str) -> str:
        # basic sanitizer
        return "".join(c for c in name if c.isalnum() or c in " _-").strip()
