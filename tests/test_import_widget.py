import shutil
from pathlib import Path

import pytest
from PySide6.QtWidgets import QDialog

from chroniclemap.core.models import FilterType, GameDate
from chroniclemap.gui.campaign_store import CampaignStore
from chroniclemap.gui.import_widget import ImportWidget
from chroniclemap.storage.manager import StorageManager
from chroniclemap.vision.ocr import TesseractOCRProvider

# ---- skip if tesseract unavailable ----
try:
    import pytesseract  # noqa
except Exception:
    pytesseract = None

skip_condition = (pytesseract is None) or (shutil.which("tesseract") is None)


@pytest.mark.skipif(skip_condition, reason="tesseract not available")
@pytest.mark.gui
def test_import_widget_with_real_tesseract_ocr(qtbot, tmp_path, monkeypatch):
    """
    Integration test:
    ImportWidget + TesseractOCRProvider + real image + GameDate
    """

    # ---------- real image ----------
    repo_root = Path(__file__).parent.parent.resolve()
    img_path = repo_root / "tests" / "map_1066-09-15_realms.png"
    assert img_path.exists()

    # ---------- campaign / storage ----------
    data_root = tmp_path / "data"
    store = CampaignStore(data_root)
    store.create_campaign("ocr_campaign")

    storage = StorageManager(data_root)

    # ---------- OCR ----------
    ocr = TesseractOCRProvider(lang="chi_sim+eng")

    # ---------- widget ----------
    w = ImportWidget(
        campaign_name="ocr_campaign",
        campaign_store=store,
        storage_manager=storage,
        ocr_provider=ocr,
    )
    qtbot.addWidget(w)

    # 修正后的 mock 代码：拦截整个对话框的构建过程
    class MockSnapshotDialog:
        def __init__(self, parent, path, campaign_name, filters, detected_date_iso):
            self.detected_date = detected_date_iso  # 确保传递正确的日期

        def exec(self):
            return QDialog.Accepted  # 确保返回Accepted

        def get_result(self):
            return {
                "filter": FilterType.REALMS.value,  # 必须使用字符串值（如"realms"）
                "date": "1066-09-15",  # 确保日期格式正确
                "note": "",
            }

    monkeypatch.setattr(
        "chroniclemap.gui.import_widget.SnapshotConfirmDialog", MockSnapshotDialog
    )

    # ---------- act ----------
    w._handle_input_path(img_path)

    # ---------- assert ----------
    meta = store.load_metadata("ocr_campaign")
    snaps = meta.get("snapshots", [])
    assert len(snaps) == 1

    date_iso = snaps[0]["date"]
    gd = GameDate.fromiso(date_iso)

    assert gd.to_iso() == "1066-09-15"
