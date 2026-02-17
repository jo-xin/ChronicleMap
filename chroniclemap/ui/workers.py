# chroniclemap/ui/workers.py
from __future__ import annotations

import traceback
from pathlib import Path
from typing import Any, Optional

from PySide6.QtCore import QObject, QRunnable, Signal


# Worker signals for generic tasks
class WorkerSignals(QObject):
    """
    Common signals available from worker runnables.
    - finished() always emitted on completion (no args)
    - error(tuple) emitted on exception: (exc, traceback_str)
    - result(object) emitted with task-specific result (e.g. Snapshot)
    - progress(int) optional progress percent
    """

    finished = Signal()
    error = Signal(object)
    result = Signal(object)
    progress = Signal(int)


class ImportRunnable(QRunnable):
    """
    Runnable to perform a StorageService.import_image(...) in a background thread.
    Emits signals on the provided WorkerSignals instance.
    """

    def __init__(
        self,
        storage_service,
        campaign,
        src_path: Path,
        filter_name: Optional[str],
        date_str: Optional[str] = None,
        ocr_provider: Optional[Any] = None,
        ocr_roi_spec: Optional[Any] = None,
        ocr_template_key: Optional[str] = None,
    ):
        super().__init__()
        self.signals = WorkerSignals()
        self.storage = storage_service
        self.campaign = campaign
        self.src_path = Path(src_path)
        self.filter_name = filter_name
        self.date_str = date_str
        self.ocr_provider = ocr_provider
        self.ocr_roi_spec = ocr_roi_spec
        self.ocr_template_key = ocr_template_key

    def run(self):
        try:
            # perform import (this may call OCR/thumbnail generation)
            snap = self.storage.import_image(
                campaign=self.campaign,
                src_path=self.src_path,
                filter_name=self.filter_name,
                date_str=self.date_str,
                ocr_provider=self.ocr_provider,
                ocr_roi_spec=self.ocr_roi_spec,
                ocr_template_key=self.ocr_template_key,
            )
            # emit result
            self.signals.result.emit(snap)
        except Exception as exc:
            tb = traceback.format_exc()
            self.signals.error.emit((exc, tb))
        finally:
            self.signals.finished.emit()


# inside chroniclemap/ui/workers.py (append this after ImportRunnable)


# OCRRunnable: attempt to extract date string using vision.ocr provider
class OCRRunnable(QRunnable):
    def __init__(
        self,
        image_path: Path,
        ocr_provider: Optional[object] = None,
        ocr_roi_spec: Optional[object] = None,
        ocr_template_key: Optional[str] = None,
    ):
        super().__init__()
        self.signals = WorkerSignals()
        self.image_path = Path(image_path)
        self.ocr_provider = ocr_provider
        self.ocr_roi_spec = ocr_roi_spec
        self.ocr_template_key = ocr_template_key

    def run(self):
        try:
            # import provider lazily to avoid heavy imports when not used
            from chroniclemap.vision.ocr import MockOCRProvider, TesseractOCRProvider

            provider = self.ocr_provider
            if provider is None:
                # prefer Tesseract if available
                try:
                    provider = TesseractOCRProvider(lang="chi_sim+eng")
                except Exception:
                    provider = MockOCRProvider()
            date_str = provider.extract_date(
                self.image_path,
                roi_spec=self.ocr_roi_spec,
                template_key=self.ocr_template_key,
            )
            self.signals.result.emit(date_str)
        except Exception as exc:
            import traceback

            tb = traceback.format_exc()
            self.signals.error.emit((exc, tb))
        finally:
            self.signals.finished.emit()
