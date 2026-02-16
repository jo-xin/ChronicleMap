# chroniclemap/vision/ocr.py
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

try:
    from PIL import Image, ImageFilter, ImageOps, UnidentifiedImageError
except Exception:
    Image = None

try:
    import pytesseract  # type: ignore
except Exception:
    pytesseract = None

# regex to find date-like patterns in OCR output
DATE_REGEX = re.compile(r"(?P<y>\d{3,4})[.\-/年](?P<m>\d{1,2})[.\-/月](?P<d>\d{1,2})")

# default ROI templates keyed by game id; values map "WIDTHxHEIGHT" -> (left, top, right, bottom)
# and may also include a 'relative' fallback (fractions)
DEFAULT_ROI_TEMPLATES: Dict[str, Dict[str, Any]] = {
    "ck3": {
        "1920x1080": (1460, 1040, 1720, 1080),
        # relative fallback: left_frac, top_frac, right_frac, bottom_frac
        "relative": (0.76, 0.96, 1.0, 1.0),
    },
    # more games can be added here
}


def _is_relative_roi(roi: Tuple[float, float, float, float]) -> bool:
    return all(0.0 <= v <= 1.0 for v in roi)


def compute_roi(
    image_size: Tuple[int, int],
    roi_spec: Optional[Any] = None,
    template_key: Optional[str] = None,
) -> Tuple[int, int, int, int]:
    """
    Compute pixel ROI (left, top, right, bottom) for image of size (width, height).
    roi_spec may be:
      - None: use template_key if provided, else fallback to bottom-right quarter
      - tuple of ints (absolute pixels): treated as (left, top, right, bottom)
      - tuple of floats (relative fractions): treated as fractions of width/height
      - dict template (like DEFAULT_ROI_TEMPLATES[game])
    If template_key provided, try to lookup in DEFAULT_ROI_TEMPLATES.
    """
    w, h = image_size

    # 1) explicit roi_spec
    if roi_spec:
        # if dict with keys 'abs'/'rel' or exact mapping
        if isinstance(roi_spec, dict):
            # try exact match by resolution
            key = f"{w}x{h}"
            if key in roi_spec:
                spec = roi_spec[key]
                if isinstance(spec, (tuple, list)):
                    if all(isinstance(x, int) for x in spec):
                        return tuple(int(x) for x in spec)
                    if all(isinstance(x, float) for x in spec):
                        left = int(spec[0] * w)
                        top = int(spec[1] * h)
                        right = int(spec[2] * w)
                        bottom = int(spec[3] * h)
                        return (left, top, right, bottom)
            # try 'relative' key
            if "relative" in roi_spec:
                rel = roi_spec["relative"]
                left = int(rel[0] * w)
                top = int(rel[1] * h)
                right = int(rel[2] * w)
                bottom = int(rel[3] * h)
                return (left, top, right, bottom)
        # tuple/list
        if isinstance(roi_spec, (tuple, list)) and len(roi_spec) == 4:
            if all(isinstance(x, int) for x in roi_spec):
                return tuple(int(x) for x in roi_spec)
            if all(isinstance(x, float) for x in roi_spec):
                left = int(roi_spec[0] * w)
                top = int(roi_spec[1] * h)
                right = int(roi_spec[2] * w)
                bottom = int(roi_spec[3] * h)
                return (left, top, right, bottom)

    # 2) template_key lookup
    if template_key and template_key in DEFAULT_ROI_TEMPLATES:
        tpl = DEFAULT_ROI_TEMPLATES[template_key]
        key = f"{w}x{h}"
        if key in tpl:
            spec = tpl[key]
            return tuple(int(x) for x in spec)
        # try relative
        if "relative" in tpl:
            rel = tpl["relative"]
            left = int(rel[0] * w)
            top = int(rel[1] * h)
            right = int(rel[2] * w)
            bottom = int(rel[3] * h)
            return (left, top, right, bottom)

    # 3) fallback: bottom-right quarter
    left = int(w * 0.75)
    top = int(h * 0.75)
    right = w
    bottom = h
    return (left, top, right, bottom)


class OCRProvider:
    def extract_date(
        self,
        image_path: Path,
        roi_spec: Optional[Any] = None,
        template_key: Optional[str] = None,
    ) -> Optional[str]:
        """
        Extract a date string from image_path.
        roi_spec is passed to compute_roi (see docs there).
        template_key may select a game-specific template from DEFAULT_ROI_TEMPLATES.
        Returns a date string (like '1444-11-11') or None.
        """
        raise NotImplementedError


class MockOCRProvider(OCRProvider):
    """
    Mock OCR: first look for a date-like pattern in the filename;
    otherwise try naive OCR using pytesseract if available.
    """

    def extract_date(
        self,
        image_path: Path,
        roi_spec: Optional[Tuple[int, int, int, int]] = None,
        template_key: Optional[str] = None,
    ) -> Optional[str]:
        # filename pattern
        m = DATE_REGEX.search(image_path.name)
        if m:
            return f"{m.group('y')}-{int(m.group('m')):02d}-{int(m.group('d')):02d}"

        # fallback: if pytesseract available, attempt to run on ROI (useful for integration tests)
        if pytesseract and Image:
            try:
                img = Image.open(image_path)
            except UnidentifiedImageError:
                return None
            except Exception:
                return None
            try:
                from PIL import ImageOps

                roi = compute_roi(
                    img.size, roi_spec=roi_spec, template_key=template_key
                )
                cropped = img.crop(roi)
                gray = ImageOps.grayscale(cropped)
                txt = pytesseract.image_to_string(gray)
                m2 = DATE_REGEX.search(txt)
                if m2:
                    return f"{m2.group('y')}-{int(m2.group('m')):02d}-{int(m2.group('d')):02d}"
            except Exception:
                return None
        return None


class TesseractOCRProvider(OCRProvider):
    """
    Uses pytesseract. Requires pytesseract and system tesseract binary.
    """

    def __init__(
        self,
        lang: str = "eng",
        tesseract_cmd: Optional[str] = None,
        preprocess_threshold: bool = True,
    ):
        if pytesseract is None:
            raise RuntimeError("pytesseract not installed")
        if tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
        self.lang = lang
        self.preprocess_threshold = preprocess_threshold

    def extract_date(
        self,
        image_path: Path,
        roi_spec: Optional[Any] = None,
        template_key: Optional[str] = None,
    ) -> Optional[str]:
        if Image is None:
            raise RuntimeError("Pillow not installed")
        img = Image.open(image_path)
        roi = compute_roi(img.size, roi_spec=roi_spec, template_key=template_key)
        cropped = img.crop(roi)
        # preprocess
        gray = ImageOps.grayscale(cropped)
        w, h = gray.size
        # enlarge small crops for better OCR
        scale = 1
        if max(w, h) < 800:
            scale = 2
            gray = gray.resize((int(w * scale), int(h * scale)))
        if self.preprocess_threshold:
            gray = gray.filter(ImageFilter.MedianFilter())
        # OCR
        txt = pytesseract.image_to_string(gray, lang=self.lang)
        m = DATE_REGEX.search(txt)
        if m:
            return f"{m.group('y')}-{int(m.group('m')):02d}-{int(m.group('d')):02d}"
        return None
