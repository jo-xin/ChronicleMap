# chroniclemap/core/models.py
from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Any, Dict, List, Optional


# -----------------------
# Helper utilities
# -----------------------
def now_iso() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _ensure_date(d: Optional[str | date]) -> Optional[date]:
    """Parse various date formats into datetime.date or return None."""
    if d is None:
        return None
    if isinstance(d, date):
        return d
    s = str(d).strip()
    # Try ISO first
    try:
        return date.fromisoformat(s)
    except Exception:
        pass
    # common alternate formats: YYYY.MM.DD, YYYY/MM/DD, YYYY.MM, YYYY
    for fmt in ("%Y.%m.%d", "%Y/%m/%d", "%Y.%m", "%Y/%m", "%Y-%m-%d", "%Y%m%d"):
        try:
            dt = datetime.strptime(s, fmt)
            # if only year or year+month provided, default day to 1
            return dt.date()
        except Exception:
            pass
    # fallback: try extracting digits
    parts = [p for p in s.replace("/", ".").replace("-", ".").split(".") if p]
    if len(parts) >= 1:
        try:
            y = int(parts[0])
            m = int(parts[1]) if len(parts) >= 2 else 1
            d_ = int(parts[2]) if len(parts) >= 3 else 1
            return date(y, m, d_)
        except Exception:
            pass
    raise ValueError(f"Unrecognized date format: {s}")


def _date_to_iso(d: Optional[date]) -> Optional[str]:
    return d.isoformat() if d is not None else None


# -----------------------
# Enums
# -----------------------
class FilterType(str, Enum):
    REALMS = "realms"
    FAITH = "faith"
    CULTURE = "culture"
    CUSTOM = "custom"


class Rank(str, Enum):
    HEGEMONY = "hegemony"
    EMPIRE = "empire"
    KINGDOM = "kingdom"
    DUCHY = "duchy"
    COUNTY = "county"
    ADVENTURE = "adventurer"
    NONE = "none"


# -----------------------
# Data classes
# -----------------------
@dataclass
class AlignInfo:
    dx: float = 0.0
    dy: float = 0.0
    scale: float = 1.0
    method: str = "translation"  # "translation", "affine", "homography"
    confidence: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AlignInfo":
        return cls(
            dx=float(data.get("dx", 0.0)),
            dy=float(data.get("dy", 0.0)),
            scale=float(data.get("scale", 1.0)),
            method=data.get("method", "translation"),
            confidence=float(data.get("confidence", 1.0)),
        )


@dataclass
class Snapshot:
    id: str
    date: date
    filter_type: FilterType
    path: str  # relative or absolute path to image file
    thumbnail: Optional[str] = None
    align: AlignInfo = field(default_factory=AlignInfo)
    ocr_extracted: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "date": _date_to_iso(self.date),
            "filter_type": self.filter_type.value,
            "path": self.path,
            "thumbnail": self.thumbnail,
            "align": self.align.to_dict() if self.align else None,
            "ocr_extracted": self.ocr_extracted,
            "extra": self.extra,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Snapshot":
        return cls(
            id=str(data["id"]),
            date=_ensure_date(data["date"]),
            filter_type=(
                FilterType(data["filter_type"])
                if data.get("filter_type")
                else FilterType.CUSTOM
            ),
            path=str(data["path"]),
            thumbnail=data.get("thumbnail"),
            align=(
                AlignInfo.from_dict(data["align"]) if data.get("align") else AlignInfo()
            ),
            ocr_extracted=data.get("ocr_extracted"),
            extra=data.get("extra", {}),
        )


@dataclass
class RankPeriod:
    from_date: date
    to_date: Optional[date]  # None means ongoing
    rank: Rank
    note: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "from_date": _date_to_iso(self.from_date),
            "to_date": _date_to_iso(self.to_date),
            "rank": self.rank.value,
            "note": self.note,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RankPeriod":
        return cls(
            from_date=_ensure_date(data["from_date"]),
            to_date=_ensure_date(data.get("to_date")),
            rank=Rank(data.get("rank", Rank.NONE.value)),
            note=data.get("note"),
        )


@dataclass
class Ruler:
    id: str
    full_name: Optional[str] = None
    display_name: Optional[str] = None
    epithet: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    rank_periods: List[RankPeriod] = field(default_factory=list)
    notes: Optional[str] = None
    meta: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "full_name": self.full_name,
            "display_name": self.display_name,
            "epithet": self.epithet,
            "start_date": _date_to_iso(self.start_date),
            "end_date": _date_to_iso(self.end_date),
            "rank_periods": [rp.to_dict() for rp in self.rank_periods],
            "notes": self.notes,
            "meta": self.meta,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Ruler":
        return cls(
            id=str(data["id"]),
            full_name=data.get("full_name"),
            display_name=data.get("display_name"),
            epithet=data.get("epithet"),
            start_date=_ensure_date(data.get("start_date")),
            end_date=_ensure_date(data.get("end_date")),
            rank_periods=[
                RankPeriod.from_dict(x) for x in data.get("rank_periods", [])
            ],
            notes=data.get("notes"),
            meta=data.get("meta", {}),
        )


@dataclass
class CampaignConfig:
    playback_speed: Dict[str, Any] = field(
        default_factory=lambda: {"units": "days_per_second", "value": 365}
    )
    default_filter: FilterType = FilterType.REALMS
    upload_period_days: Optional[int] = None
    rank_theme: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "playback_speed": self.playback_speed,
            "default_filter": self.default_filter.value,
            "upload_period_days": self.upload_period_days,
            "rank_theme": self.rank_theme,
        }
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CampaignConfig":
        return cls(
            playback_speed=data.get(
                "playback_speed", {"units": "days_per_second", "value": 365}
            ),
            default_filter=FilterType(
                data.get("default_filter", FilterType.REALMS.value)
            ),
            upload_period_days=data.get("upload_period_days"),
            rank_theme=data.get("rank_theme", {}),
        )


@dataclass
class Campaign:
    id: str
    name: str
    path: Optional[str] = None  # filesystem path to campaign root
    config: CampaignConfig = field(default_factory=CampaignConfig)
    snapshots: List[Snapshot] = field(default_factory=list)
    rulers: List[Ruler] = field(default_factory=list)
    notes: Optional[str] = None
    created_at: str = field(default_factory=now_iso)
    modified_at: str = field(default_factory=now_iso)
    meta: Dict[str, Any] = field(default_factory=dict)

    # ---- convenience methods ----
    def add_snapshot(self, snapshot: Snapshot) -> None:
        """Add snapshot ensuring no duplicate id; keep snapshots sorted by date."""
        if any(s.id == snapshot.id for s in self.snapshots):
            raise ValueError(f"Snapshot with id {snapshot.id} already exists")
        self.snapshots.append(snapshot)
        self.snapshots.sort(key=lambda s: s.date)

    def find_snapshot(
        self, date_obj: date, filter_type: Optional[FilterType] = None
    ) -> Optional[Snapshot]:
        """Find exact snapshot for date and optional filter; exact match only."""
        for s in self.snapshots:
            if s.date == date_obj and (
                filter_type is None or s.filter_type == filter_type
            ):
                return s
        return None

    def get_latest_before(
        self, date_obj: date, filter_type: Optional[FilterType] = None
    ) -> Optional[Snapshot]:
        """Return the most recent snapshot with date <= date_obj (optionally filtered)."""
        candidates = [
            s
            for s in self.snapshots
            if s.date <= date_obj
            and (filter_type is None or s.filter_type == filter_type)
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda s: s.date)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "path": self.path,
            "config": self.config.to_dict(),
            "snapshots": [s.to_dict() for s in self.snapshots],
            "rulers": [r.to_dict() for r in self.rulers],
            "notes": self.notes,
            "created_at": self.created_at,
            "modified_at": self.modified_at,
            "meta": self.meta,
        }

    def to_json(self, *, indent: Optional[int] = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Campaign":
        camp = cls(
            id=str(data["id"]),
            name=str(data["name"]),
            path=data.get("path"),
            config=CampaignConfig.from_dict(data.get("config", {})),
            snapshots=[Snapshot.from_dict(x) for x in data.get("snapshots", [])],
            rulers=[Ruler.from_dict(x) for x in data.get("rulers", [])],
            notes=data.get("notes"),
            created_at=data.get("created_at", now_iso()),
            modified_at=data.get("modified_at", now_iso()),
            meta=data.get("meta", {}),
        )
        # ensure snapshots are sorted
        camp.snapshots.sort(key=lambda s: s.date)
        return camp

    @classmethod
    def from_json(cls, s: str) -> "Campaign":
        data = json.loads(s)
        return cls.from_dict(data)


# -----------------------
# Factory helpers
# -----------------------
def new_snapshot(
    *,
    date_str: str | date,
    filter_type: FilterType,
    path: str,
    thumbnail: Optional[str] = None,
    ocr: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Snapshot:
    return Snapshot(
        id=str(uuid.uuid4()),
        date=_ensure_date(date_str),
        filter_type=filter_type,
        path=path,
        thumbnail=thumbnail,
        align=AlignInfo(),
        ocr_extracted=ocr,
        extra=extra or {},
    )


def new_ruler(
    *,
    full_name: str | None = None,
    display_name: str | None = None,
    start_date: str | date | None = None,
    end_date: str | date | None = None,
    epithet: str | None = None,
) -> Ruler:
    return Ruler(
        id=str(uuid.uuid4()),
        full_name=full_name,
        display_name=display_name,
        epithet=epithet,
        start_date=_ensure_date(start_date) if start_date else None,
        end_date=_ensure_date(end_date) if end_date else None,
        rank_periods=[],
    )


def new_campaign(name: str, path: Optional[str] = None) -> Campaign:
    return Campaign(
        id=str(uuid.uuid4()),
        name=name,
        path=path,
        config=CampaignConfig(),
    )
