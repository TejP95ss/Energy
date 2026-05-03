"""
Price fetching for ISO New England day-ahead LMP data.
Supports all 8 ISO-NE load zones.
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


def _cache_path(date: datetime.date, node: str) -> Path:
    safe_node = node.replace(".", "").replace(" ", "_").upper()
    node_dir = DATA_DIR / safe_node
    node_dir.mkdir(parents=True, exist_ok=True)
    return node_dir / f"prices_{date.isoformat()}.json"


def _read_from_cache(date: datetime.date, node: str) -> dict | None:
    path = _cache_path(date, node)
    if path.exists():
        try:
            data = json.loads(path.read_text())
            if len(data.get("prices", [])) == 24:
                print(f"[prices] Cache hit: {path.name}")
                return data
        except Exception as e:
            print(f"[prices] Cache read failed for {path.name}: {e}")
    return None


def _write_to_cache(date: datetime.date, node: str, prices: list[float], source: str):
    path = _cache_path(date, node)
    try:
        path.write_text(json.dumps({
            "date": date.isoformat(),
            "node": node,
            "source": source,
            "prices": prices,
        }, indent=2))
        print(f"[prices] Saved to cache: {path}")
    except Exception as e:
        print(f"[prices] Cache write failed: {e}")


def _list_cached_dates(node: str) -> list[datetime.date]:
    safe_node = node.replace(".", "").replace(" ", "_").upper()
    node_dir = DATA_DIR / safe_node

    if not node_dir.exists():
        return []

    dates = []
    for path in node_dir.glob("prices_*.json"):
        try:
            date_str = path.stem.split("_")[1]
            dates.append(datetime.date.fromisoformat(date_str))
        except (ValueError, IndexError):
            continue

    return sorted(dates)


def _fetch_iso_ne(date: datetime.date, node: str) -> dict:
    dates_to_try = [date + datetime.timedelta(days=1), date]

    for d in dates_to_try:
        try:
            url = (
                f"https://www.iso-ne.com/static-transform/csv/histRpts/da-lmp/"
                f"WW_DALMP_ISO_{d.strftime('%Y%m%d')}.csv"
            )
            print(f"[prices] Fetching: {url} for node {node}")
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})

            with urllib.request.urlopen(req, timeout=10) as resp:
                raw = resp.read().decode("utf-8", errors="ignore")

            header = None
            prices = []
            data_date = None

            for line in raw.splitlines():
                row = next(csv.reader([line]))
                if not row:
                    continue
                record_type = row[0]
                if record_type == "H" and "Location Name" in row:
                    header = row[1:]
                    continue
                if record_type == "D" and header:
                    row_dict = dict(zip(header, row[1:]))
                    if row_dict.get("Location Name", "").strip().upper() != node.upper():
                        continue
                    if data_date is None:
                        data_date = datetime.datetime.strptime(row_dict["Date"], "%m/%d/%Y").date()
                    hour = int(row_dict["Hour Ending"]) - 1
                    lmp = float(row_dict["Locational Marginal Price"])
                    prices.append((hour, round(lmp / 10, 4)))

            if not prices:
                raise ValueError(f"No data found for node {node}")

            prices.sort(key=lambda x: x[0])
            hourly = [p for _, p in prices]

            if len(hourly) != 24:
                raise ValueError(f"Expected 24 prices, got {len(hourly)}")

            return {"date": data_date.isoformat(), "prices": hourly}

        except Exception as e:
            print(f"[prices] Fetch failed for {d}: {type(e).__name__}: {e}")

    raise ValueError(f"All ISO-NE fetch attempts failed for node {node}")


def get_prices(live: bool = True, node: str = DEFAULT_NODE) -> dict:
    if node not in ISO_NE_ZONES:
        raise ValueError(f"Unknown node '{node}'. Valid nodes: {list(ISO_NE_ZONES.keys())}")

    today = datetime.date.today()

    if live:
        cached = _read_from_cache(today + datetime.timedelta(days=1), node)
        if cached:
            return {
                "source": "file_cache",
                "node": node,
                "zone_name": ISO_NE_ZONES[node],
                "date": cached["date"],
                "unit": "cents_per_kwh",
                "hours": list(range(24)),
                "prices": cached["prices"],
                "fallback": False,
            }

        try:
            fetched = _fetch_iso_ne(today, node)
            price_date = datetime.date.fromisoformat(fetched["date"])
            _write_to_cache(price_date, node, fetched["prices"], source="iso_ne_csv")
            return {
                "source": "iso_ne_live",
                "node": node,
                "zone_name": ISO_NE_ZONES[node],
                "date": fetched["date"],
                "unit": "cents_per_kwh",
                "hours": list(range(24)),
                "prices": fetched["prices"],
                "fallback": False,
            }
        except Exception as exc:
            print(f"[prices] Live fetch failed: {exc} — falling back to mock")

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


def get_price_history(days: int = 7, node: str = DEFAULT_NODE) -> dict[str, list[float]]:
    cutoff = datetime.date.today() - datetime.timedelta(days=days)
    result = {}
    for date in _list_cached_dates(node):
        if date >= cutoff:
            cached = _read_from_cache(date, node)
            if cached:
                result[cached["date"]] = cached["prices"]
    return result


def get_zones() -> dict:
    """Return all valid zone identifiers and their display names."""
    return ISO_NE_ZONES


if __name__ == "__main__":
    result = get_prices(live=True, node=DEFAULT_NODE)
    print(json.dumps(result, indent=2))