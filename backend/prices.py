"""
https://www.iso-ne.com/isoexpress/web/reports/pricing/-/tree/lmps-da-hourly-rt-prelim
Price fetching for ISO New England day-ahead LMP data.
Supports all 8 ISO-NE load zones.

File format (data/{node}/prices_{date}.json):
  {
    "date": "2026-05-05",
    "node": ".Z.NEMASSBOST",
    "source": "iso_ne_csv",
    "day_ahead": [24 floats],
    "real_time": [24 floats or nulls] | null,
    "real_time_complete": bool
  }
"""

import datetime
import urllib.request
import csv
import json
from pathlib import Path

ISO_NE_ZONES = {
    ".Z.MAINE":        "Maine",
    ".Z.NEWHAMPSHIRE": "New Hampshire",
    ".Z.VERMONT":      "Vermont",
    ".Z.CONNECTICUT":  "Connecticut",
    ".Z.RHODEISLAND":  "Rhode Island",
    ".Z.SEMASS":       "Southeast Mass",
    ".Z.WCMASS":       "West/Central Mass",
    ".Z.NEMASSBOST":   "Northeast Mass / Boston",
}

DEFAULT_NODE = ".Z.NEMASSBOST"
DATA_DIR = Path(__file__).parent.parent / "data"

MOCK_PRICES: list[float] = [
    6.2,  6.0,  5.8,  5.7,  5.9,  6.5,
    8.1,  9.4, 10.2, 10.8, 10.5, 10.1,
    9.8,  9.5,  9.3,  9.6, 10.9, 12.4,
   13.1, 13.8, 12.7, 11.2,  9.0,  7.3,
]


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------

def _node_dir(node: str) -> Path:
    safe = node.replace(".", "").replace(" ", "_").upper()
    return DATA_DIR / safe


def _cache_path(date: datetime.date, node: str) -> Path:
    return _node_dir(node) / f"prices_{date.isoformat()}.json"


def _read_cache(date: datetime.date, node: str) -> dict | None:
    path = _cache_path(date, node)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
        if "day_ahead" in data and len(data["day_ahead"]) == 24:
            return data
    except Exception as e:
        print(f"[prices] Cache read error {path.name}: {e}")
    return None


def _write_cache(data: dict):
    """Write a full cache entry. data must have date and node keys."""
    date = datetime.date.fromisoformat(data["date"])
    node = data["node"]
    node_dir = _node_dir(node)
    node_dir.mkdir(parents=True, exist_ok=True)
    path = _cache_path(date, node)
    path.write_text(json.dumps(data, indent=2))
    print(f"[prices] Cached: {path.relative_to(DATA_DIR)}")


def _list_cached_dates(node: str) -> list[datetime.date]:
    d = _node_dir(node)
    if not d.exists():
        return []
    dates = []
    for path in d.glob("prices_*.json"):
        try:
            dates.append(datetime.date.fromisoformat(path.stem.replace("prices_", "")))
        except ValueError:
            continue
    return sorted(dates)

def fetch_dart(date: datetime.date, node: str) -> dict:
    """
    Fetch DA+RT LMP report for a given date and node.
    Returns dict with day_ahead and real_time price lists.
    Real-time list may have fewer than 24 values if day is in progress.
    """
    url = (
        f"https://www.iso-ne.com/static-transform/csv/histRpts/rolling-dart/"
        f"da_rt_lmp_{date.strftime('%Y%m%d')}.csv"
    )
    print(f"[fetch_rt] Fetching: {url}")

    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        raw = resp.read().decode("utf-8", errors="ignore")

    # Parse the dual-header CSV
    # The file has 3 H rows: category names, column names, column types
    # We want the second H row (column names)
    lines = raw.splitlines()
    header = None
    da_by_hour: dict[int, float] = {}
    rt_by_hour: dict[int, float] = {}
    data_date = None

    for line in lines:
        row = next(csv.reader([line]))
        if not row:
            continue

        record_type = row[0].strip().strip('"')

        if record_type == "H":
            # The useful header has "Date" as second field
            stripped = [c.strip().strip('"') for c in row]
            if "Date" in stripped and "Hour Ending" in stripped:
                header = stripped[1:]  # skip leading H
            continue

        if record_type == "D" and header:
            values = [c.strip().strip('"') for c in row[1:]]
            row_dict = dict(zip(header, values))

            loc = row_dict.get("Location Name", "").strip().upper()
            if loc != node.upper():
                continue

            if data_date is None:
                data_date = datetime.datetime.strptime(
                    row_dict["Date"], "%m/%d/%Y"
                ).date()

            hour = int(row_dict["Hour Ending"]) - 1  # 0-indexed

            # Day-ahead LMP
            da_raw = row_dict.get("Day Ahead_Locational Marginal Price", "") or \
                     row_dict.get("Locational Marginal Price", "")
            # Real-time LMP — second "Locational Marginal Price" column
            # Headers have duplicate names so we need positional fallback
            da_idx = None
            rt_idx = None
            headers_list = list(header)
            lmp_positions = [i for i, h in enumerate(headers_list)
                             if h == "Locational Marginal Price"]

            if len(lmp_positions) >= 2:
                da_idx = lmp_positions[0]
                rt_idx = lmp_positions[1]
            elif len(lmp_positions) == 1:
                da_idx = lmp_positions[0]

            if da_idx is not None and da_idx < len(values):
                try:
                    da_by_hour[hour] = round(float(values[da_idx]) / 10, 4)
                except ValueError:
                    pass

            if rt_idx is not None and rt_idx < len(values):
                rt_val = values[rt_idx]
                if rt_val not in ("", "N/A", "null"):
                    try:
                        rt_by_hour[hour] = round(float(rt_val) / 10, 4)
                    except ValueError:
                        pass

    if not da_by_hour:
        raise ValueError(f"No DA data found for node {node} on {date}")

    da_prices = [da_by_hour.get(h) for h in range(24)]
    rt_prices = [rt_by_hour.get(h) for h in range(24)]

    rt_complete = all(v is not None for v in rt_prices)
    rt_available = any(v is not None for v in rt_prices)

    return {
        "date": date.isoformat(),
        "node": node,
        "day_ahead": [p if p is not None else 0.0 for p in da_prices],
        "real_time": rt_prices if rt_available else None,
        "real_time_complete": rt_complete,
    }

def get_prices(live: bool = True, node: str = DEFAULT_NODE) -> dict:
    """
    Returns day-ahead prices for today (used by optimizer).
    Cache → fetch → mock fallback.
    """
    if node not in ISO_NE_ZONES:
        raise ValueError(f"Unknown node '{node}'")

    today = datetime.date.today()

    if live:
        target_date = today + datetime.timedelta(days=1) #try cache for tomorrow
        cached = _read_cache(target_date, node)
        if cached:
            return {
                "source": "file_cache",
                "node": node,
                "zone_name": ISO_NE_ZONES[node],
                "date": cached["date"],
                "unit": "cents_per_kwh",
                "hours": list(range(24)),
                "prices": cached["day_ahead"],
                "fallback": False,
            }
        try:
            fetched = fetch_dart(target_date, node) #try fetching tomorrow's data
            _write_cache(fetched)
            return {
                "source": "iso_ne_live",
                "node": node,
                "zone_name": ISO_NE_ZONES[node],
                "date": fetched["date"],
                "unit": "cents_per_kwh",
                "hours": list(range(24)),
                "prices": fetched["day_ahead"],
                "fallback": False,
            }
        except Exception as exc:
            print(f"[prices] DA fetch failed for {target_date}: {exc}")

        cached_today = _read_cache(today, node) #try today's cached data
        if cached_today:
            return {
                "source": "file_cache",
                "node": node,
                "zone_name": ISO_NE_ZONES[node],
                "date": cached_today["date"],
                "unit": "cents_per_kwh",
                "hours": list(range(24)),
                "prices": cached_today["day_ahead"],
                "fallback": False,
            }
        try:
            fetched = fetch_dart(today, node) #finally fetch today's data
            _write_cache(fetched)
            return {
                "source": "iso_ne_live",
                "node": node,
                "zone_name": ISO_NE_ZONES[node],
                "date": fetched["date"],
                "unit": "cents_per_kwh",
                "hours": list(range(24)),
                "prices": fetched["day_ahead"],
                "fallback": False,
            }
        except Exception as exc:
            print(f"[prices] Today fallback failed: {exc} — using mock")

    return {
        "source": "mock",
        "node": node,
        "zone_name": ISO_NE_ZONES.get(node, "Unknown"),
        "date": today.isoformat(),
        "unit": "cents_per_kwh",
        "hours": list(range(24)),
        "prices": MOCK_PRICES,
        "fallback": True,
    }

def get_dart_history(days: int = 7, node: str = DEFAULT_NODE) -> list[dict]:
    today = datetime.date.today()
    results = []

    for i in range(1, days + 1):
        date = today - datetime.timedelta(days=i)

        cached = _read_cache(date, node)

        if not cached or not cached.get("real_time_complete"):
            try:
                fetched = fetch_dart(date, node)
                _write_cache(fetched)
                cached = fetched
                print(f"[prices] Fetched DART for {date}")
            except Exception as e:
                print(f"[prices] Fetch failed for {date}: {e}")
                continue

        results.append({
            "date": cached["date"],
            "day_ahead": cached["day_ahead"],
            "real_time": cached.get("real_time"),
            "real_time_complete": cached.get("real_time_complete", False),
        })

    return sorted(results, key=lambda x: x["date"])


def get_zones() -> dict:
    return ISO_NE_ZONES


if __name__ == "__main__":
    import json
    result = get_prices(live=True, node=DEFAULT_NODE)
    print(json.dumps(result, indent=2))