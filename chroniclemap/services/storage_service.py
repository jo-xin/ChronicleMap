# chroniclemap/services/storage_service.py
from __future__ import annotations

from pathlib import Path
from typing import Iterable, Optional

from chroniclemap.core.models import Campaign, Snapshot
from chroniclemap.storage.manager import StorageManager


class StorageService:
    """
    Thin service wrapper around StorageManager for UI consumption.
    Keeps a base_dir (where campaigns live).
    """

    def __init__(self, base_dir: Path | None = None):
        if base_dir is None:
            base_dir = Path.home() / ".chroniclemap_data"
        self.base_dir = Path(base_dir)
        self._mgr = StorageManager(self.base_dir)

    def list_campaigns(self) -> Iterable[str]:
        return list(self._mgr.list_campaigns())

    def create_campaign(self, name: str) -> Campaign:
        return self._mgr.create_campaign(name)

    def load_campaign(self, name_or_path: str | Path) -> Campaign:
        return self._mgr.load_campaign(name_or_path)

    def delete_campaign(self, name: str) -> None:
        """
        Delete a campaign folder. (Simple implementation: remove dir tree.)
        UI should ask confirmation before calling this.
        """
        p = self.base_dir / name
        if not p.exists():
            raise FileNotFoundError(f"{p} not found")
        # careful: using shutil.rmtree
        import shutil

        shutil.rmtree(p)

    def import_image(
        self,
        campaign: Campaign,
        src_path: Path,
        filter_name: str | None = None,
        date_str: Optional[str] = None,
        *,
        ocr_provider: Optional[object] = None,
        ocr_roi_spec: Optional[object] = None,
        ocr_template_key: Optional[str] = None,
    ) -> Snapshot:
        """
        Wrapper around StorageManager.import_image to expose a cleaner API to UI.
        - campaign: Campaign object (must have .path set)
        - src_path: Path to source image
        - filter_name: string matching FilterType or custom
        - date_str: optional explicit date (YYYY-MM-DD)
        - ocr_*: optional parameters (not used by default)
        Returns the Snapshot object created.
        """
        # Delegate to underlying StorageManager method.
        return self._mgr.import_image(
            campaign=campaign,
            src_path=Path(src_path),
            filter_type=filter_name or "custom",
            date_str=date_str,
            create_dirs_if_missing=True,
            ocr_provider=ocr_provider,
            ocr_roi_spec=ocr_roi_spec,
            ocr_template_key=ocr_template_key,
        )
