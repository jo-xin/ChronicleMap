# chroniclemap/core/models.py
"""
Core data models for ChronicleMap.

Major change: replace usage of `datetime.date` with `GameDate`, which supports:
 - arbitrary integer years (including BCE/negative years),
 - conversion to/from ISO-like strings,
 - arithmetic (add days / difference) for both "real" (proleptic Gregorian) calendar
   and "no-leap" calendar (every year = 365 days).
This file contains:
 - GameDate class and utils
 - Enums (FilterType, Rank)
 - AlignInfo, Snapshot, RankPeriod, Ruler, CampaignConfig, Campaign
 - Factory helpers (new_snapshot, new_ruler, new_campaign)
"""
from __future__ import annotations

import json
import re
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

# -----------------------------------------------------------------------------
# GameDate: robust date for game timelines (supports arbitrary year integers)
# -----------------------------------------------------------------------------
# We'll implement a robust conversion between (year,month,day) and an integer
# "ordinal" using the well-known civil_from_days / days_from_civil algorithms
# (Howard Hinnant). That algorithm uses proleptic Gregorian calendar and works
# for wide integer year ranges. We also implement a "no-leap-year" ordinal
# mapping for game worlds like CK3 where every year has 365 days.
#
# API:
#   GameDate(year, month, day)
#   GameDate.fromiso("YYYY-MM-DD")  # supports various separators and partial dates
#   gd.to_iso() -> "YYYY-MM-DD"
#   gd.to_ordinal(ignore_leap=False) -> int  (proleptic ordinal)
#   GameDate.from_ordinal(n, ignore_leap=False) -> GameDate
#   gd + days: use gd.add_days(days, ignore_leap=...)
#   gd1 - gd2 -> int days difference (gd1.to_ordinal - gd2.to_ordinal)
# -----------------------------------------------------------------------------

# regex for parsing date-like strings
DATE_PARSE_REGEX = re.compile(
    r"^\s*([+-]?\d{1,5})(?:[.\-/年](\d{1,2})(?:[.\-/月](\d{1,2}))?)?\s*$"
)


def _normalize_int(s: Union[str, int]) -> int:
    if isinstance(s, int):
        return s
    return int(str(s).strip())


# Hinnant's algorithms for date -> days and days -> date (proleptic Gregorian)
# Ported for Python, returns days relative to UNIX epoch (1970-01-01), but we can
# use the returned value as a stable ordinal for comparison.
def days_from_civil(y: int, m: int, d: int) -> int:
    """
    Convert civil date (y,m,d) to days since 1970-01-01 (can be negative). Works
    for large integer years. See Howard Hinnant algorithm.
    """
    # 历史年份转天文年份（BCE 1 = -1 -> 0）
    if y < 0:
        y = y + 1

    y0 = y - (1 if m <= 2 else 0)
    era = y0 // 400
    yoe = y0 - era * 400
    mp = m - 3 if m > 2 else m + 9
    doy = (153 * mp + 2) // 5 + d - 1
    doe = yoe * 365 + yoe // 4 - yoe // 100 + doy
    return era * 146097 + doe - 719468  # 719468 = days_from_civil(1970,1,1) offset


def civil_from_days(z: int) -> Tuple[int, int, int]:
    """
    Convert days since 1970-01-01 to (year, month, day) in proleptic Gregorian.
    Inverse of days_from_civil.
    """
    z = int(z)
    z += 719468
    era = z // 146097
    doe = z - era * 146097
    yoe = (doe - doe // 1460 + doe // 36524 - doe // 146096) // 365
    y = int(yoe) + era * 400
    doy = doe - (365 * yoe + yoe // 4 - yoe // 100)
    mp = (5 * doy + 2) // 153
    d = int(doy - (153 * mp + 2) // 5 + 1)
    m = int(mp + 3 if mp < 10 else mp - 9)
    y = int(y + (1 if m <= 2 else 0))

    # 天文年份转回历史年份（0 -> -1）
    if y < 1:
        y = y - 1

    return y, m, d


# month lengths in Gregorian
_GREGORIAN_MONTH_LENGTHS = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]


def is_gregorian_leap(year: int) -> bool:
    """Return True if year is leap in proleptic Gregorian calendar."""
    # 历史年份转天文年份（-1 -> 0，-2 -> -1）
    if year < 0:
        year = year + 1

    if year % 4 != 0:
        return False
    if year % 100 != 0:
        return True
    if year % 400 == 0:
        return True
    return False


def day_of_year_no_leap(year: int, month: int, day: int) -> int:
    """Compute day-of-year (1-based) treating Feb as 28 always."""
    cum = [0]
    for ml in _GREGORIAN_MONTH_LENGTHS:
        cum.append(cum[-1] + ml)
    return cum[month - 1] + day


def day_of_year_real(year: int, month: int, day: int) -> int:
    """Compute day-of-year considering real leap years (1-based)."""
    cum = [0]
    for i, ml in enumerate(_GREGORIAN_MONTH_LENGTHS):
        if i == 1 and is_gregorian_leap(year):
            cum.append(cum[-1] + 29)
        else:
            cum.append(cum[-1] + ml)
    # careful: cum has length 13; cum[month-1] gives days before month
    return cum[month - 1] + day


@dataclass(order=True, frozen=True)
class GameDate:
    """
    Lightweight date class supporting arbitrary integer years.

    - year: int (can be negative for BCE)
    - month: 1..12
    - day: 1..31 (validation minimal here)
    """

    year: int
    month: int
    day: int

    def __post_init__(self):
        # 增强验证
        if not (1 <= self.month <= 12):
            raise ValueError(f"month must be 1..12, got {self.month}")

        max_day = _GREGORIAN_MONTH_LENGTHS[self.month - 1]
        if self.month == 2 and is_gregorian_leap(self.year):
            max_day = 29
        if not (1 <= self.day <= max_day):
            raise ValueError(
                f"day must be 1..{max_day} for {self.year}-{self.month}, got {self.day}"
            )

    # -------------------------
    # Factories & parsing
    # -------------------------
    @classmethod
    def from_tuple(cls, t: Tuple[int, int, int]) -> "GameDate":
        return cls(year=int(t[0]), month=int(t[1]), day=int(t[2]))

    @classmethod
    def fromiso(
        cls, s: Union[str, "GameDate", Tuple[int, int, int], int]
    ) -> "GameDate":
        """
        Parse common formats into GameDate:
          - GameDate instance -> return copy
          - "YYYY-MM-DD" or "YYYY.MM.DD" or "YYYY/MM/DD" or "YYYYMMDD"
          - "YYYY" or "YYYY.MM" -> default missing parts to 1
          - int -> treat as year, Jan 1
        """
        if isinstance(s, GameDate):
            return s
        if isinstance(s, int):
            return cls(year=s, month=1, day=1)
        text = str(s).strip()
        if not text:
            raise ValueError("empty date string")
        # direct ISO-like
        m = DATE_PARSE_REGEX.match(text)
        if not m:
            # Try simple YYYYMMDD
            digits = re.fullmatch(r"([+-]?\d{1,5})(\d{2})(\d{2})$", text)
            if digits:
                y = int(digits.group(1))
                mo = int(digits.group(2))
                da = int(digits.group(3))
                return cls(year=y, month=mo, day=da)
            raise ValueError(f"Unrecognized date string: {text}")
        year_s = m.group(1)
        mo_s = m.group(2)
        da_s = m.group(3)
        y = int(year_s)
        mo = int(mo_s) if mo_s else 1
        da = int(da_s) if da_s else 1
        return cls(year=y, month=mo, day=da)

    def to_iso(self) -> str:
        """Return ISO-like YYYY-MM-DD, with sign for negative years if needed."""
        # zero pad year to 4 digits if abs(year) <= 9999, else use full width
        y = self.year
        sign = "-" if y < 0 else ""
        yy = abs(y)
        # use at least 4 digits for year formatting for readability
        if yy <= 9999:
            ystr = f"{sign}{yy:04d}"
        else:
            ystr = f"{sign}{yy}"
        return f"{ystr}-{self.month:02d}-{self.day:02d}"

    # -------------------------
    # Ordinal conversions
    # -------------------------
    def to_ordinal(self, ignore_leap: bool = False) -> int:
        if not ignore_leap:
            return days_from_civil(self.year, self.month, self.day)
        # 修复：正确处理负数年份的 ordinal 计算
        doy = day_of_year_no_leap(self.year, self.month, self.day)
        y = self.year
        if y > 0:
            return (y - 1) * 365 + (doy - 1)
        else:
            return y * 365 + (doy - 1)

    @classmethod
    def from_ordinal(cls, ordinal: int, ignore_leap: bool = False) -> "GameDate":
        if not ignore_leap:
            y, m, d = civil_from_days(int(ordinal))
            return cls(year=y, month=m, day=d)
        # 修复：正确处理负数 ordinal 对应的年份和年内天数
        if ordinal >= 0:
            year = ordinal // 365 + 1
            doy = ordinal % 365 + 1
        else:
            year = -((-ordinal - 1) // 365 + 1)
            doy = 365 - ((-ordinal - 1) % 365)
        # 从 doy 反推 month 和 day
        cum = [0]
        for ml in _GREGORIAN_MONTH_LENGTHS:
            cum.append(cum[-1] + ml)
        month = 1
        for i in range(1, 13):
            if doy <= cum[i]:
                month = i
                break
        day = doy - cum[month - 1]
        return cls(year=year, month=month, day=day)

    # -------------------------
    # Arithmetic
    # -------------------------
    def add_days(self, days: int, ignore_leap: bool = False) -> "GameDate":
        """Return new GameDate that is this date plus `days` days (days can be negative)."""
        ord0 = self.to_ordinal(ignore_leap=ignore_leap)
        new_ord = ord0 + int(days)
        return GameDate.from_ordinal(new_ord, ignore_leap=ignore_leap)

    def days_until(self, other: "GameDate", ignore_leap: bool = False) -> int:
        """
        Return number of days from self to other (other - self) using selected calendar semantics.
        """
        return other.to_ordinal(ignore_leap=ignore_leap) - self.to_ordinal(
            ignore_leap=ignore_leap
        )

    # convenience
    def __add__(self, days: int) -> "GameDate":
        return self.add_days(int(days))

    def __sub__(self, other: Union["GameDate", int]) -> int:
        if isinstance(other, GameDate):
            # difference in days (real calendar by default)
            return self.to_ordinal(ignore_leap=False) - other.to_ordinal(
                ignore_leap=False
            )
        else:
            # subtracting integer days -> return new GameDate
            return self.add_days(-int(other))  # type: ignore[return-value]


# -----------------------------------------------------------------------------
# Enums, dataclasses (unchanged interface but use GameDate)
# -----------------------------------------------------------------------------


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


@dataclass
class AlignInfo:
    dx: float = 0.0
    dy: float = 0.0
    scale: float = 1.0
    method: str = "translation"
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
    date: GameDate
    filter_type: FilterType
    path: str
    thumbnail: Optional[str] = None
    align: AlignInfo = field(default_factory=AlignInfo)
    ocr_extracted: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "date": self.date.to_iso() if self.date else None,
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
            date=(
                GameDate.fromiso(data["date"])
                if data.get("date")
                else GameDate.fromiso(1)
            ),
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
    from_date: GameDate
    to_date: Optional[GameDate]
    rank: Rank
    note: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "from_date": self.from_date.to_iso() if self.from_date else None,
            "to_date": self.to_date.to_iso() if self.to_date else None,
            "rank": self.rank.value,
            "note": self.note,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RankPeriod":
        return cls(
            from_date=GameDate.fromiso(data["from_date"]),
            to_date=(
                GameDate.fromiso(data.get("to_date")) if data.get("to_date") else None
            ),
            rank=Rank(data.get("rank", Rank.NONE.value)),
            note=data.get("note"),
        )


@dataclass
class Ruler:
    id: str
    full_name: Optional[str] = None
    display_name: Optional[str] = None
    epithet: Optional[str] = None
    start_date: Optional[GameDate] = None
    end_date: Optional[GameDate] = None
    rank_periods: List[RankPeriod] = field(default_factory=list)
    notes: Optional[str] = None
    meta: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "full_name": self.full_name,
            "display_name": self.display_name,
            "epithet": self.epithet,
            "start_date": self.start_date.to_iso() if self.start_date else None,
            "end_date": self.end_date.to_iso() if self.end_date else None,
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
            start_date=(
                GameDate.fromiso(data.get("start_date"))
                if data.get("start_date")
                else None
            ),
            end_date=(
                GameDate.fromiso(data.get("end_date")) if data.get("end_date") else None
            ),
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
        return {
            "playback_speed": self.playback_speed,
            "default_filter": self.default_filter.value,
            "upload_period_days": self.upload_period_days,
            "rank_theme": self.rank_theme,
        }

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
    path: Optional[str] = None
    config: CampaignConfig = field(default_factory=CampaignConfig)
    snapshots: List[Snapshot] = field(default_factory=list)
    rulers: List[Ruler] = field(default_factory=list)
    notes: Optional[str] = None
    created_at: Optional[str] = None
    modified_at: Optional[str] = None
    meta: Dict[str, Any] = field(default_factory=dict)

    def add_snapshot(self, snapshot: Snapshot) -> None:
        if any(s.id == snapshot.id for s in self.snapshots):
            raise ValueError(f"Snapshot with id {snapshot.id} already exists")
        self.snapshots.append(snapshot)
        # sort by ordinal (use real calendar by default; engine may use no-leap override)
        self.snapshots.sort(key=lambda s: s.date.to_ordinal(ignore_leap=False))

    def find_snapshot(
        self, date_obj: Union[str, GameDate], filter_type: Optional[FilterType] = None
    ) -> Optional[Snapshot]:
        target = (
            date_obj if isinstance(date_obj, GameDate) else GameDate.fromiso(date_obj)
        )
        for s in self.snapshots:
            if s.date == target and (
                filter_type is None or s.filter_type == filter_type
            ):
                return s
        return None

    def get_latest_before(
        self, date_obj: Union[str, GameDate], filter_type: Optional[FilterType] = None
    ) -> Optional[Snapshot]:
        target = (
            date_obj if isinstance(date_obj, GameDate) else GameDate.fromiso(date_obj)
        )
        candidates = [
            s
            for s in self.snapshots
            if s.date.to_ordinal(ignore_leap=False)
            <= target.to_ordinal(ignore_leap=False)
            and (filter_type is None or s.filter_type == filter_type)
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda s: s.date.to_ordinal(ignore_leap=False))

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
            created_at=data.get("created_at"),
            modified_at=data.get("modified_at"),
            meta=data.get("meta", {}),
        )
        camp.snapshots.sort(key=lambda s: s.date.to_ordinal(ignore_leap=False))
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
    date_str: Union[str, GameDate],
    filter_type: FilterType,
    path: str,
    thumbnail: Optional[str] = None,
    ocr: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Snapshot:
    gd = date_str if isinstance(date_str, GameDate) else GameDate.fromiso(date_str)
    return Snapshot(
        id=str(uuid.uuid4()),
        date=gd,
        filter_type=filter_type,
        path=path,
        thumbnail=thumbnail,
        align=AlignInfo(),
        ocr_extracted=ocr,
        extra=extra or {},
    )


def new_ruler(
    *,
    full_name: Optional[str] = None,
    display_name: Optional[str] = None,
    start_date: Optional[Union[str, GameDate]] = None,
    end_date: Optional[Union[str, GameDate]] = None,
    epithet: Optional[str] = None,
) -> Ruler:
    sd = GameDate.fromiso(start_date) if start_date else None
    ed = GameDate.fromiso(end_date) if end_date else None
    return Ruler(
        id=str(uuid.uuid4()),
        full_name=full_name,
        display_name=display_name,
        epithet=epithet,
        start_date=sd,
        end_date=ed,
        rank_periods=[],
    )


def new_campaign(name: str, path: Optional[str] = None) -> Campaign:
    return Campaign(
        id=str(uuid.uuid4()),
        name=name,
        path=path,
        config=CampaignConfig(),
    )
