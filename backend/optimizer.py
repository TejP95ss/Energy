"""
Core optimization engine for house energy scheduling.
Region: ISO New England
Approach: Greedy cost minimization (Phase 1)

Each device has:
  - energy_kwh: total energy needed
  - duration_hours: how many consecutive hours it must run
  - earliest_start: first hour it can begin (0-23)
  - latest_end: last hour it must finish by (1-24)
"""

from dataclasses import dataclass
from typing import Optional
import json


# Hardcoded ISO-NE style hourly prices (cents/kWh) for a typical weekday
# Hours 0-23. Prices are lowest at night, peak in morning/evening.
MOCK_PRICES_CENTS: list[float] = [
    6.2,  6.0,  5.8,  5.7,  5.9,  6.5,   # 0–5 AM (off-peak night)
    8.1,  9.4, 10.2, 10.8, 10.5, 10.1,   # 6–11 AM (morning ramp)
    9.8,  9.5,  9.3,  9.6, 10.9, 12.4,   # 12–5 PM (midday + afternoon)
   13.1, 13.8, 12.7, 11.2,  9.0,  7.3,   # 6–11 PM (evening peak)
]


@dataclass
class Device:
    name: str
    energy_kwh: float
    duration_hours: int       # must run this many consecutive hours
    earliest_start: int       # hour index 0–23
    latest_end: int           # hour index 1–24 (exclusive end)
    power_kw: Optional[float] = None  # derived if not given

    def __post_init__(self):
        if self.power_kw is None:
            self.power_kw = self.energy_kwh / self.duration_hours


@dataclass
class ScheduledDevice:
    name: str
    start_hour: int
    end_hour: int
    hours: list[int]
    cost_cents: float
    energy_kwh: float
    power_kw: float


def find_cheapest_window(device: Device, prices: list[float]) -> ScheduledDevice:
    """
    Greedy: try every valid start hour, pick the one with lowest total cost.
    """
    best_start = None
    best_cost = float("inf")

    window = device.duration_hours
    for start in range(device.earliest_start, device.latest_end - window + 1):
        hours = list(range(start, start + window))
        cost = sum(prices[h] * device.power_kw for h in hours)
        if cost < best_cost:
            best_cost = cost
            best_start = start

    if best_start is None:
        raise ValueError(
            f"No valid window found for '{device.name}' "
            f"(earliest={device.earliest_start}, latest_end={device.latest_end}, "
            f"duration={device.duration_hours})"
        )

    hours = list(range(best_start, best_start + window))
    return ScheduledDevice(
        name=device.name,
        start_hour=best_start,
        end_hour=best_start + window,
        hours=hours,
        cost_cents=round(best_cost, 4),
        energy_kwh=round(device.power_kw * window, 4),
        power_kw=round(device.power_kw, 4),
    )


def optimize(devices: list[Device], prices: list[float] = MOCK_PRICES_CENTS) -> dict:
    """
    Run the greedy optimizer for each device independently.
    Returns a schedule dict with per-device results and totals.
    """
    schedule = []
    total_cost = 0.0
    total_energy = 0.0

    for device in devices:
        result = find_cheapest_window(device, prices)
        schedule.append(result)
        total_cost += result.cost_cents
        total_energy += result.energy_kwh

    return {
        "prices_cents_per_kwh": prices,
        "schedule": [
            {
                "name": s.name,
                "start_hour": s.start_hour,
                "end_hour": s.end_hour,
                "hours": s.hours,
                "power_kw": s.power_kw,
                "energy_kwh": s.energy_kwh,
                "cost_cents": s.cost_cents,
            }
            for s in schedule
        ],
        "total_cost_cents": round(total_cost, 4),
        "total_cost_dollars": round(total_cost / 100, 4),
        "total_energy_kwh": round(total_energy, 4),
    }


if __name__ == "__main__":

    devices = [
        Device(
            name="EV Charger",
            energy_kwh=40.0,
            duration_hours=8,
            earliest_start=0,    # overnight charging window
            latest_end=8,        # must finish by 8 AM
        ),
        Device(
            name="Dishwasher",
            energy_kwh=1.5,
            duration_hours=2,
            earliest_start=19,   # after dinner
            latest_end=24,
        ),
        Device(
            name="Washing Machine",
            energy_kwh=2.0,
            duration_hours=1,
            earliest_start=0,
            latest_end=8,        # anytime overnight
        ),
    ]

    result = optimize(devices)
    print(json.dumps(result, indent=2))