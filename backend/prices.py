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


def _build_url(date: datetime.date) -> str:
    """Day-ahead LMP endpoint for a given date."""
    d = date.strftime("%Y%m%d")
    return (
        f"https://webservices.iso-ne.com/api/v1.1/dalocationalmarginalprice"
        f"/day/{d}/location/{NEMASSBOST_NODE}"
    )

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
        try:
            prices = _fetch_iso_ne(today)
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
            # Log but don't crash — fall through to mock
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


if __name__ == "__main__":
    result = get_prices(live=True)
    print(json.dumps(result, indent=2))