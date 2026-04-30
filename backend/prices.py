"""
Price fetching for ISO New England day-ahead LMP data.
Node: .Z.NEMASSBOST (Northeast Mass / Boston load zone)

Caching strategy (no DB):
  1. Check data/ folder for a CSV matching the target date
  2. If not found, fetch from ISO-NE and save it to data/
  3. Fall back to mock prices if everything fails

DB code is preserved in database.py and the commented out code in this file
for future deployment.
"""

import datetime
import urllib.request
import csv
import json
import os
from pathlib import Path

NEMASSBOST_NODE = ".Z.NEMASSBOST"

# data/ lives next to the backend/ folder
DATA_DIR = Path(__file__).parent.parent / "data"

MOCK_PRICES: list[float] = [
    6.2,  6.0,  5.8,  5.7,  5.9,  6.5,
    8.1,  9.4, 10.2, 10.8, 10.5, 10.1,
    9.8,  9.5,  9.3,  9.6, 10.9, 12.4,
   13.1, 13.8, 12.7, 11.2,  9.0,  7.3,
]


# ---------------------------------------------------------------------------
# Local file cache
# ---------------------------------------------------------------------------
def _cache_path(date: datetime.date) -> Path:
    return DATA_DIR / f"prices_{date.isoformat()}.json"


def _read_from_cache(date: datetime.date) -> dict | None:
    """Return cached payload or None if not valid."""
    path = _cache_path(date)
    if path.exists():
        try:
            data = json.loads(path.read_text())
            prices = data.get("prices", [])
            if len(prices) == 24:
                print(f"[prices] Cache hit: {path.name}")
                return data  # ✅ return full object
        except Exception as e:
            print(f"[prices] Cache read failed for {path.name}: {e}")
    return None


def _write_to_cache(date: datetime.date, prices: list[float], source: str):
    """Write 24 hourly prices to a local JSON file."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = _cache_path(date)
    try:
        path.write_text(json.dumps({
            "date": date.isoformat(),
            "node": NEMASSBOST_NODE,
            "source": source,
            "prices": prices,
        }, indent=2))
        print(f"[prices] Saved to cache: {path.name}")
    except Exception as e:
        print(f"[prices] Cache write failed: {e}")


def _list_cached_dates() -> list[datetime.date]:
    """Return all dates that have complete cached price files, sorted ascending."""
    if not DATA_DIR.exists():
        return []
    dates = []
    for path in DATA_DIR.glob("prices_*.json"):
        try:
            date_str = path.stem.replace("prices_", "")
            dates.append(datetime.date.fromisoformat(date_str))
        except ValueError:
            continue
    return sorted(dates)


# ---------------------------------------------------------------------------
# ISO-NE CSV fetch
# ---------------------------------------------------------------------------

def _fetch_iso_ne(date: datetime.date) -> dict:
    """
    Fetch 24 hourly day-ahead LMPs from ISO-NE CSV.
    Tries date+1 first (tomorrow's DA report contains today's prices),
    then falls back to date itself.
    Returns {"date": iso_str, "prices": [24 floats]}
    """
    dates_to_try = [date + datetime.timedelta(days=1), date]
    print(dates_to_try)
    for d in dates_to_try:
        try:
            url = (
                f"https://www.iso-ne.com/static-transform/csv/histRpts/da-lmp/"f"WW_DALMP_ISO_{d.strftime('%Y%m%d')}.csv"
            )
            print(f"[prices] Fetching: {url}")
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
                    if row_dict.get("Location Name", "").strip().upper() != NEMASSBOST_NODE:
                        continue
                    if data_date is None:
                        data_date = datetime.datetime.strptime(row_dict["Date"], "%m/%d/%Y").date()
                    hour = int(row_dict["Hour Ending"]) - 1
                    lmp = float(row_dict["Locational Marginal Price"])
                    prices.append((hour, round(lmp / 10, 4)))

            if not prices:
                raise ValueError("No matching node data found in CSV")

            prices.sort(key=lambda x: x[0])
            hourly = [p for _, p in prices]

            if len(hourly) != 24:
                raise ValueError(f"Expected 24 prices, got {len(hourly)}")

            print(f"[prices] Fetched OK for {data_date} via {url}")
            return {"date": data_date.isoformat(), "prices": hourly}

        except Exception as e:
            print(f"[prices] Fetch failed for {d}: {type(e).__name__}: {e}")

    raise ValueError("All ISO-NE fetch attempts failed")


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

def get_prices(live: bool = True) -> dict:
    """
    Return price data dict with source metadata.
    Order: local file cache → ISO-NE fetch → mock fallback.
    """
    today = datetime.date.today()

    if live:
        # 1. Check local cache for today or tomorrow's prices
        cached = _read_from_cache(today + datetime.timedelta(days=1))
        if cached:
            return {
                "source": "file_cache",
                "node": NEMASSBOST_NODE,
                "date": cached["date"],
                "unit": "cents_per_kwh",
                "hours": list(range(24)),
                "prices": cached["prices"],
                "fallback": False,
            }

        # 2. Fetch from ISO-NE and cache locally
        try:
            fetched = _fetch_iso_ne(today)
            price_date = datetime.date.fromisoformat(fetched["date"])
            _write_to_cache(price_date, fetched["prices"], source="iso_ne_csv")
            return {
                "source": "iso_ne_live",
                "node": NEMASSBOST_NODE,
                "date": fetched["date"],
                "unit": "cents_per_kwh",
                "hours": list(range(24)),
                "prices": fetched["prices"],
                "fallback": False,
            }
        except Exception as exc:
            print(f"[prices] Live fetch failed: {exc} — falling back to mock")

    # 3. Mock fallback
    return {
        "source": "mock",
        "node": "mock_iso_ne_typical_weekday",
        "date": today.isoformat(),
        "unit": "cents_per_kwh",
        "hours": list(range(24)),
        "prices": MOCK_PRICES,
        "fallback": True,
    }


def get_price_history(days: int = 7) -> dict[str, list[float]]:
    """
    Return prices for the past N days from local file cache.
    Keyed by date string, same shape as before so the API response is unchanged.
    """
    cutoff = datetime.date.today() - datetime.timedelta(days=days)
    result = {}
    for date in _list_cached_dates():
        if date >= cutoff:
            cached = _read_from_cache(date)
            if cached:
                result[cached["date"]] = cached["prices"]
    return result


if __name__ == "__main__":
    result = get_prices(live=True)
    print(json.dumps(result, indent=2))


# """
# Price fetching for ISO New England day-ahead LMP data.
# Node: .Z.NEMASSBOST (Northeast Mass / Boston load zone)


# No authentication required for public endpoints.
# Falls back to mock prices on any error.
# """

# import datetime
# import urllib.request
# import json
# import csv
# from database import cursor

# NEMASSBOST_NODE = ".Z.NEMASSBOST"

# MOCK_PRICES: list[float] = [
#     6.2,  6.0,  5.8,  5.7,  5.9,  6.5,
#     8.1,  9.4, 10.2, 10.8, 10.5, 10.1,
#     9.8,  9.5,  9.3,  9.6, 10.9, 12.4,
#    13.1, 13.8, 12.7, 11.2,  9.0,  7.3,
# ]


# def _read_from_db(date: datetime.date, node: str) -> dict | None:
#     """
#     Try reading cached prices for (date+1) first, then date.
#     Returns {"date": iso_str, "prices": [...]} or None.
#     """
#     dates_to_try = [date + datetime.timedelta(days=1), date]

#     for d in dates_to_try:
#         try:
#             with cursor() as cur:
#                 cur.execute("""
#                     SELECT hour, price_cents
#                     FROM hourly_prices
#                     WHERE price_date = %s AND node = %s
#                     ORDER BY hour
#                 """, (d, node))
#                 rows = cur.fetchall()

#             if len(rows) == 24:
#                 prices = [float(r["price_cents"]) for r in rows]
#                 print(f"[prices] DB hit for {d}")
#                 return {
#                     "date": d.isoformat(),
#                     "prices": prices
#                 }

#         except Exception as e:
#             print(f"[prices] DB read skipped for {d}: {e}")

#     return None


# def _write_to_db(date: datetime.date, node: str, prices: list[float], source: str):
#     """Insert 24 hourly prices. ON CONFLICT DO NOTHING avoids duplicate errors."""
#     try:
#         with cursor() as cur:
#             for hour, price in enumerate(prices):
#                 cur.execute("""
#                     INSERT INTO hourly_prices (price_date, hour, node, price_cents, source)
#                     VALUES (%s, %s, %s, %s, %s)
#                     ON CONFLICT (price_date, hour, node) DO NOTHING
#                 """, (date, hour, node, price, source))
#         print(f"[prices] Cached {len(prices)} prices to DB for {date}")
#     except Exception as e:
#         print(f"[prices] DB write skipped: {e}")


# def _read_date_range_from_db(node: str, days: int = 7) -> dict[str, list[float]]:
#     """
#     Return a dict of {date_str: [24 prices]} for the past `days` days.
#     Used by the /prices/history endpoint.
#     """
#     try:
#         with cursor() as cur:
#             cur.execute("""
#                 SELECT price_date, hour, price_cents
#                 FROM hourly_prices
#                 WHERE node = %s
#                   AND price_date >= CURRENT_DATE - INTERVAL '%s days'
#                 ORDER BY price_date, hour
#             """, (node, days))
#             rows = cur.fetchall()

#         result: dict[str, list] = {}
#         for row in rows:
#             key = row["price_date"].isoformat()
#             result.setdefault(key, []).append(float(row["price_cents"]))
#         # Only return complete days
#         return {k: v for k, v in result.items() if len(v) == 24}
#     except Exception as e:
#         print(f"[prices] DB history read skipped: {e}")
#         return {}
    
# def _fetch_iso_ne(date: datetime.date) -> dict:
#     """
#     Fetch 24 hourly day-ahead report LMPs from ISO-NE CSV link. Returns prices in ¢/kWh.
#     the data is from https://www.iso-ne.com/isoexpress/web/reports/pricing/-/tree/lmps-da-hourly
#     """

#     dates_to_try = [date + datetime.timedelta(days=1), date]
#     for d in dates_to_try:
#         try:
#             url = (
#                 f"https://www.iso-ne.com/static-transform/csv/histRpts/da-lmp/"
#                 f"WW_DALMP_ISO_{d.strftime('%Y%m%d')}.csv"
#             )

#             print(f"[prices] Trying: {url}")

#             req = urllib.request.Request(url,headers={"User-Agent": "Mozilla/5.0"})

#             with urllib.request.urlopen(req, timeout=10) as resp:
#                 raw = resp.read().decode("utf-8", errors="ignore")

#             lines = raw.splitlines()

#             header = None
#             prices = []
#             data_date = None

#             for line in lines:
#                 row = next(csv.reader([line]))

#                 if not row:
#                     continue

#                 record_type = row[0]

#                 # Capture the correct header row
#                 if record_type == "H" and "Location Name" in row:
#                     header = row[1:]  # skip "H"
#                     continue

#                 # Process data rows
#                 if record_type == "D" and header:
#                     values = row[1:]  # skip "D"
#                     row_dict = dict(zip(header, values))

#                     loc = row_dict.get("Location Name", "").strip()

#                     # Exact match (robust)
#                     if loc.upper() == NEMASSBOST_NODE:
#                         if data_date is None:
#                             data_date = datetime.datetime.strptime(row_dict["Date"], "%m/%d/%Y").date()
#                         hour = int(row_dict["Hour Ending"]) - 1
#                         lmp = float(row_dict["Locational Marginal Price"])  # $/MWh

#                         price = round(lmp / 10, 4)  # ¢/kWh
#                         prices.append((hour, price))

#             if not prices:
#                 raise ValueError("No matching node data found")

#             prices.sort(key=lambda x: x[0])
#             hourly = [p for _, p in prices]

#             if len(hourly) != 24:
#                 raise ValueError(f"Expected 24 prices, got {len(hourly)}")

#             print(f"[prices] SUCCESS using {url}")
#             return {"date": data_date.isoformat(), "prices": hourly}

#         except Exception as e:
#             print(f"[prices] Failed for {d}: {type(e).__name__}: {e}")

#     raise ValueError("All ISO-NE CSV attempts failed")

# def get_prices(live: bool = True) -> dict:
#     """
#     Return price data dict with source metadata.
#     Always tries live first when live=True; falls back to mock on failure.
#     """
#     today = datetime.date.today()

#     if live:
#         cached = _read_from_db(today, NEMASSBOST_NODE)
#         if cached:
#             print("[prices] Serving from DB cache")
#             return {
#                 "source": "iso_ne_cached",
#                 "node": NEMASSBOST_NODE,
#                 "date": cached["date"],
#                 "unit": "cents_per_kwh",
#                 "hours": list(range(24)),
#                 "prices": cached["prices"],
#                 "fallback": False,
#             }
        
#         try:
#             date_price_dict = _fetch_iso_ne(today)
#             date = date_price_dict["date"]
#             prices = date_price_dict["prices"]
#             _write_to_db(date, NEMASSBOST_NODE, prices, source="iso_ne_csv")
#             return {
#                 "source": "iso_ne_live",
#                 "node": NEMASSBOST_NODE,
#                 "date": date,
#                 "unit": "cents_per_kwh",
#                 "hours": list(range(24)),
#                 "prices": prices,
#                 "fallback": False,
#             }
#         except Exception as exc:
#             print(f"[prices] ISO-NE fetch failed ({type(exc).__name__}: {exc}), using mock")

#     return {
#         "source": "mock",
#         "node": "mock_iso_ne_typical_weekday",
#         "date": today.isoformat(),
#         "unit": "cents_per_kwh",
#         "hours": list(range(24)),
#         "prices": MOCK_PRICES,
#         "fallback": True,
#     }

# def get_price_history(days: int = 7) -> dict:
#     """Return cached prices for the past N days, keyed by date string."""
#     return _read_date_range_from_db(NEMASSBOST_NODE, days)


# if __name__ == "__main__":
#     result = get_prices(live=True)
#     print(json.dumps(result, indent=2))