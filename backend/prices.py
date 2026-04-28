"""
Price fetching for ISO New England day-ahead LMP data.
Node: .Z.NEMASSBOST (Northeast Mass / Boston load zone)


No authentication required for public endpoints.
Falls back to mock prices on any error.
"""

import datetime
import urllib.request
import json
import csv
import io

NEMASSBOST_NODE = ".Z.NEMASSBOST"

MOCK_PRICES: list[float] = [
    6.2,  6.0,  5.8,  5.7,  5.9,  6.5,
    8.1,  9.4, 10.2, 10.8, 10.5, 10.1,
    9.8,  9.5,  9.3,  9.6, 10.9, 12.4,
   13.1, 13.8, 12.7, 11.2,  9.0,  7.3,
]


def _read_from_db(date: datetime.date, node: str) -> list[float] | None:
    """Return 24 sorted prices from DB, or None if not cached / DB unavailable."""
    try:
        from database import cursor
        with cursor() as cur:
            cur.execute("""
                SELECT hour, price_cents
                FROM hourly_prices
                WHERE price_date = %s AND node = %s
                ORDER BY hour
            """, (date, node))
            rows = cur.fetchall()
        if len(rows) == 24:
            return [float(r["price_cents"]) for r in rows]
        return None
    except Exception as e:
        print(f"[prices] DB read skipped: {e}")
        return None


def _write_to_db(date: datetime.date, node: str, prices: list[float], source: str):
    """Insert 24 hourly prices. ON CONFLICT DO NOTHING avoids duplicate errors."""
    try:
        from database import cursor
        with cursor() as cur:
            for hour, price in enumerate(prices):
                cur.execute("""
                    INSERT INTO hourly_prices (price_date, hour, node, price_cents, source)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (price_date, hour, node) DO NOTHING
                """, (date, hour, node, price, source))
        print(f"[prices] Cached {len(prices)} prices to DB for {date}")
    except Exception as e:
        print(f"[prices] DB write skipped: {e}")


def _read_date_range_from_db(
    node: str, days: int = 7
) -> dict[str, list[float]]:
    """
    Return a dict of {date_str: [24 prices]} for the past `days` days.
    Used by the /prices/history endpoint.
    """
    try:
        from database import cursor
        with cursor() as cur:
            cur.execute("""
                SELECT price_date, hour, price_cents
                FROM hourly_prices
                WHERE node = %s
                  AND price_date >= CURRENT_DATE - INTERVAL '%s days'
                ORDER BY price_date, hour
            """, (node, days))
            rows = cur.fetchall()

        result: dict[str, list] = {}
        for row in rows:
            key = row["price_date"].isoformat()
            result.setdefault(key, []).append(float(row["price_cents"]))
        # Only return complete days
        return {k: v for k, v in result.items() if len(v) == 24}
    except Exception as e:
        print(f"[prices] DB history read skipped: {e}")
        return {}
    
def _fetch_iso_ne(date: datetime.date) -> list[float]:
    """
    Fetch 24 hourly day-ahead report LMPs from ISO-NE CSV link. Returns prices in ¢/kWh.
    the data is from https://www.iso-ne.com/isoexpress/web/reports/pricing/-/tree/lmps-da-hourly
    """

    dates_to_try = [date + datetime.timedelta(days=1), date]
    for d in dates_to_try:
        try:
            url = (
                f"https://www.iso-ne.com/static-transform/csv/histRpts/da-lmp/"
                f"WW_DALMP_ISO_{d.strftime('%Y%m%d')}.csv"
            )

            print(f"[prices] Trying: {url}")

            req = urllib.request.Request(url,headers={"User-Agent": "Mozilla/5.0"})

            with urllib.request.urlopen(req, timeout=10) as resp:
                raw = resp.read().decode("utf-8", errors="ignore")

            lines = raw.splitlines()

            header = None
            prices = []

            for line in lines:
                row = next(csv.reader([line]))

                if not row:
                    continue

                record_type = row[0]

                # Capture the correct header row
                if record_type == "H" and "Location Name" in row:
                    header = row[1:]  # skip "H"
                    continue

                # Process data rows
                if record_type == "D" and header:
                    values = row[1:]  # skip "D"
                    row_dict = dict(zip(header, values))

                    loc = row_dict.get("Location Name", "").strip()

                    # Exact match (robust)
                    if loc.upper() == NEMASSBOST_NODE:
                        hour = int(row_dict["Hour Ending"]) - 1
                        lmp = float(row_dict["Locational Marginal Price"])  # $/MWh

                        price = round(lmp / 10, 4)  # ¢/kWh
                        prices.append((hour, price))

            if not prices:
                raise ValueError("No matching node data found")

            prices.sort(key=lambda x: x[0])
            hourly = [p for _, p in prices]

            if len(hourly) != 24:
                raise ValueError(f"Expected 24 prices, got {len(hourly)}")

            print(f"[prices] SUCCESS using {url}")
            return hourly

        except Exception as e:
            print(f"[prices] Failed for {d}: {type(e).__name__}: {e}")

    raise ValueError("All ISO-NE CSV attempts failed")

def get_prices(live: bool = True) -> dict:
    """
    Return price data dict with source metadata.
    Always tries live first when live=True; falls back to mock on failure.
    """
    today = datetime.date.today()

    if live:
        cached = _read_from_db(today, NEMASSBOST_NODE)
        if cached:
            print("[prices] Serving from DB cache")
            return {
                "source": "iso_ne_cached",
                "node": NEMASSBOST_NODE,
                "date": today.isoformat(),
                "unit": "cents_per_kwh",
                "hours": list(range(24)),
                "prices": cached,
                "fallback": False,
            }
        
        try:
            prices = _fetch_iso_ne(today)
            _write_to_db(today, NEMASSBOST_NODE, prices, source="iso_ne_csv")
            return {
                "source": "iso_ne_live",
                "node": NEMASSBOST_NODE,
                "date": today.isoformat(),
                "unit": "cents_per_kwh",
                "hours": list(range(24)),
                "prices": prices,
                "fallback": False,
            }
        except Exception as exc:
            print(f"[prices] ISO-NE fetch failed ({type(exc).__name__}: {exc}), using mock")

    return {
        "source": "mock",
        "node": "mock_iso_ne_typical_weekday",
        "date": today.isoformat(),
        "unit": "cents_per_kwh",
        "hours": list(range(24)),
        "prices": MOCK_PRICES,
        "fallback": True,
    }

def get_price_history(days: int = 7) -> dict:
    """Return cached prices for the past N days, keyed by date string."""
    return _read_date_range_from_db(NEMASSBOST_NODE, days)


if __name__ == "__main__":
    result = get_prices(live=True)
    print(json.dumps(result, indent=2))