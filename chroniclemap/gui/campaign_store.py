# chroniclemap/storage/campaign_store.py
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

# import your project's core models and storage helpers
try:
    from chroniclemap.core.models import Campaign, CampaignConfig, new_campaign
except Exception as e:
    raise ImportError(
        "Failed to import chroniclemap.core.models — ensure core/models.py is available and importable."
    ) from e

try:
    from chroniclemap.storage.manager import (
        create_campaign_on_disk,
        import_image_into_campaign,
        load_campaign_from_disk,
        save_campaign_to_disk,
    )
except Exception:
    # fallback: try import the module as storage.manager
    try:
        from chroniclemap.storage import manager as _manager

        create_campaign_on_disk = _manager.create_campaign_on_disk
        load_campaign_from_disk = _manager.load_campaign_from_disk
        save_campaign_to_disk = _manager.save_campaign_to_disk
        import_image_into_campaign = _manager.import_image_into_campaign
    except Exception as e:
        raise ImportError(
            "Failed to import chroniclemap.storage.manager helpers (create/load/save/import)."
        ) from e


class CampaignStore:
    GLOBAL_META_FILENAME = "global_metadata.json"

    def __init__(self, root: Path):
        self.root = Path(root)
        # ensure both root and root/Campaigns exist for compatibility
        (self.root).mkdir(parents=True, exist_ok=True)
        (self.root / "Campaigns").mkdir(parents=True, exist_ok=True)

    def list_campaigns(self) -> List[Dict[str, Any]]:
        found = []
        candidates = []
        # prefer root/Campaigns/* but also include root/* that look like campaigns
        c1 = self.root / "Campaigns"
        if c1.exists() and c1.is_dir():
            candidates.extend([p for p in c1.iterdir() if p.is_dir()])
        # include legacy layout: root/<campaign> (if it has metadata.json)
        candidates.extend(
            [
                p
                for p in self.root.iterdir()
                if p.is_dir() and (p / "metadata.json").exists()
            ]
        )

        seen = set()
        for p in sorted(candidates):
            if str(p) in seen:
                continue
            seen.add(str(p))
            try:
                camp = load_campaign_from_disk(p)
                found.append(
                    {"name": camp.name, "path": str(p), "metadata": camp.to_dict()}
                )
            except Exception:
                # skip invalid entries silently
                continue
        return found

    def create_campaign(self, name: str) -> Campaign:
        # create under root/Campaigns for consistency with load_campaign
        target_root = self.root / "Campaigns"
        target_root.mkdir(parents=True, exist_ok=True)
        camp = new_campaign(name=name, path=None)
        campaign_root = create_campaign_on_disk(target_root, camp)
        return load_campaign_from_disk(campaign_root)

    def delete_campaign(self, name: str) -> None:
        p1 = self.root / "Campaigns" / name
        p2 = self.root / name
        target = None
        if p1.exists() and p1.is_dir():
            target = p1
        elif p2.exists() and p2.is_dir():
            target = p2
        else:
            raise FileNotFoundError(f"Campaign '{name}' not found")
        shutil.rmtree(target)

    def rename_campaign(self, old: str, new: str) -> Path:
        p_old = self._resolve_campaign_dir(old)
        if not p_old:
            raise FileNotFoundError(old)
        p_new = p_old.parent / new
        if p_new.exists():
            raise FileExistsError(new)
        p_old.rename(p_new)
        camp = load_campaign_from_disk(p_new)
        camp.name = new
        save_campaign_to_disk(camp)
        return p_new

    def load_metadata(self, name: str) -> Dict:
        p = self._resolve_campaign_dir(name)
        if not p:
            raise FileNotFoundError(name)
        camp = load_campaign_from_disk(p)
        d = camp.to_dict()
        # provide backwards-compatible alias: ensure 'note' exists if older code expects it
        if "notes" in d and "note" not in d:
            d["note"] = d["notes"]
        return d

    def save_metadata(self, name: str, metadata: Dict) -> None:
        p = self._resolve_campaign_dir(name)
        if not p:
            raise FileNotFoundError(name)
        camp = load_campaign_from_disk(p)

        # update fields safely; do type conversions when needed
        # name
        if "name" in metadata:
            camp.name = metadata["name"]

        # notes / note compatibility
        if "notes" in metadata:
            camp.notes = metadata["notes"]
        elif "note" in metadata:
            camp.notes = metadata["note"]

        # config: if given as dict, convert back to CampaignConfig
        if "config" in metadata:
            cfg = metadata["config"]
            if isinstance(cfg, dict):
                try:
                    camp.config = CampaignConfig.from_dict(cfg)
                except Exception:
                    # fall back: keep existing config if conversion fails
                    pass
            else:
                # if it's already a CampaignConfig instance, accept it
                camp.config = cfg

        # meta: only shallow replace
        if "meta" in metadata and isinstance(metadata["meta"], dict):
            camp.meta = metadata["meta"]

        # preserve created_at if present
        if "created_at" in metadata:
            camp.created_at = metadata["created_at"]
        if "modified_at" in metadata:
            camp.modified_at = metadata["modified_at"]

        # Note: snapshots & rulers are expected to be manipulated via domain APIs (import_image, add_ruler, etc.)
        save_campaign_to_disk(camp)

    def import_image(
        self,
        name: str,
        src_path: Path,
        filter_type,
        date_str: Optional[str] = None,
        **kwargs,
    ):
        p = self._resolve_campaign_dir(name)
        if not p:
            raise FileNotFoundError(name)
        camp = load_campaign_from_disk(p)
        snap = import_image_into_campaign(
            campaign=camp,
            src_path=Path(src_path),
            filter_type=filter_type,
            date_str=date_str,
            **kwargs,
        )
        return snap

    def find_snapshot_by_id(self, name: str, snapshot_id: str):
        p = self._resolve_campaign_dir(name)
        if not p:
            return None
        camp = load_campaign_from_disk(p)
        for s in camp.snapshots:
            if s.id == snapshot_id:
                return s
        return None

    def _resolve_campaign_dir(self, name: str) -> Optional[Path]:
        p1 = self.root / "Campaigns" / name
        p2 = self.root / name
        if p1.exists() and p1.is_dir():
            return p1
        if p2.exists() and p2.is_dir():
            return p2
        return None

    def load_global_metadata(self) -> Dict[str, Any]:
        path = self.root / self.GLOBAL_META_FILENAME
        if not path.exists():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def save_global_metadata(self, metadata: Dict[str, Any]) -> None:
        path = self.root / self.GLOBAL_META_FILENAME
        payload = metadata if isinstance(metadata, dict) else {}
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def get_global_language(self, default: str = "en") -> str:
        meta = self.load_global_metadata()
        value = meta.get("language")
        return str(value) if value else default

    def set_global_language(self, locale: str) -> None:
        meta = self.load_global_metadata()
        meta["language"] = locale
        self.save_global_metadata(meta)
