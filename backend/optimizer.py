"""
Optimization engine for house energy scheduling.
Region: ISO New England
Phase 3: Greedy with household load cap + savings calculation

Each device has:
  - energy_kwh: total energy needed
  - duration_hours: consecutive hours it must run
  - earliest_start: first hour it can begin (0-23)
  - latest_end: last hour it must finish by (1-24)

Household constraint:
  - max_load_kw: total kW across all devices at any hour cannot exceed this
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Device:
    name: str
    energy_kwh: float
    duration_hours: int
    earliest_start: int
    latest_end: int
    power_kw: Optional[float] = None

    def __post_init__(self):
        if self.power_kw is None:
            self.power_kw = round(self.energy_kwh / self.duration_hours, 4)


@dataclass
class ScheduledDevice:
    name: str
    start_hour: int
    end_hour: int
    hours: list[int]
    cost_cents: float
    energy_kwh: float
    power_kw: float
    # Cost if device had run at its earliest allowed start instead
    unoptimized_cost_cents: float


def _window_cost(hours: list[int], power_kw: float, prices: list[float]) -> float:
    return sum(prices[h] * power_kw for h in hours)


def _find_cheapest_window(
    device: Device,
    prices: list[float],
    load_by_hour: list[float],
    max_load_kw: float,
) -> ScheduledDevice:
    """
    Try every valid consecutive window for the device.
    Skip any window where adding this device would exceed max_load_kw in any hour.
    Pick the valid window with lowest total cost.
    """
    best_start = None
    best_cost = float("inf")
    window = device.duration_hours

    for start in range(device.earliest_start, device.latest_end - window + 1):
        hours = list(range(start, start + window))

        # Check load cap: would any hour exceed the household max?
        if any(load_by_hour[h] + device.power_kw > max_load_kw for h in hours):
            continue

        cost = _window_cost(hours, device.power_kw, prices)
        if cost < best_cost:
            best_cost = cost
            best_start = start

    if best_start is None:
        raise ValueError(
            f"No valid window found for '{device.name}'. "
            f"This may be because the household load cap ({max_load_kw} kW) is too "
            f"restrictive for the given time window, or the window is too narrow. "
            f"Try raising the load cap or widening the device's allowed hours."
        )

    hours = list(range(best_start, best_start + window))

    # Unoptimized baseline: device runs at its earliest allowed start
    unoptimized_hours = list(range(device.earliest_start, device.earliest_start + window))
    unoptimized_cost = _window_cost(unoptimized_hours, device.power_kw, prices)

    return ScheduledDevice(
        name=device.name,
        start_hour=best_start,
        end_hour=best_start + window,
        hours=hours,
        cost_cents=round(best_cost, 4),
        energy_kwh=round(device.power_kw * window, 4),
        power_kw=round(device.power_kw, 4),
        unoptimized_cost_cents=round(unoptimized_cost, 4),
    )


def optimize(
    devices: list[Device],
    prices: list[float],
    max_load_kw: float = 20.0,
) -> dict:
    """
    Greedy optimizer with household load cap.

    Devices are sorted by power draw descending — place the hungriest
    devices first so they claim cheap low-contention hours, and smaller
    devices fill in around them.
    """
    # Track cumulative load per hour across already-scheduled devices
    load_by_hour: list[float] = [0.0] * 24

    # Schedule biggest power draws first (greedy priority)
    ordered = sorted(devices, key=lambda d: d.power_kw, reverse=True)

    schedule = []
    total_cost = 0.0
    total_unoptimized = 0.0
    total_energy = 0.0

    for device in ordered:
        result = _find_cheapest_window(device, prices, load_by_hour, max_load_kw)

        # Commit this device's load into the shared hour tracker
        for h in result.hours:
            load_by_hour[h] += result.power_kw

        schedule.append(result)
        total_cost += result.cost_cents
        total_unoptimized += result.unoptimized_cost_cents
        total_energy += result.energy_kwh

    # Restore original order for display
    name_order = {d.name: i for i, d in enumerate(devices)}
    schedule.sort(key=lambda s: name_order.get(s.name, 999))

    savings = total_unoptimized - total_cost

    return {
        "prices_cents_per_kwh": prices,
        "max_load_kw": max_load_kw,
        "schedule": [
            {
                "name": s.name,
                "start_hour": s.start_hour,
                "end_hour": s.end_hour,
                "hours": s.hours,
                "power_kw": s.power_kw,
                "energy_kwh": s.energy_kwh,
                "cost_cents": s.cost_cents,
                "unoptimized_cost_cents": s.unoptimized_cost_cents,
                "savings_cents": round(s.unoptimized_cost_cents - s.cost_cents, 4),
            }
            for s in schedule
        ],
        "total_cost_cents": round(total_cost, 4),
        "total_cost_dollars": round(total_cost / 100, 4),
        "total_unoptimized_cost_cents": round(total_unoptimized, 4),
        "total_unoptimized_cost_dollars": round(total_unoptimized / 100, 4),
        "total_savings_cents": round(savings, 4),
        "total_savings_dollars": round(savings / 100, 4),
        "total_energy_kwh": round(total_energy, 4),
    }


if __name__ == "__main__":
    import json
    from prices import MOCK_PRICES

    devices = [
        Device("EV Charger",     energy_kwh=40.0, duration_hours=8, earliest_start=0,  latest_end=8),
        Device("Dishwasher",     energy_kwh=1.5,  duration_hours=2, earliest_start=19, latest_end=24),
        Device("Washing Machine",energy_kwh=2.0,  duration_hours=1, earliest_start=0,  latest_end=8),
    ]

    result = optimize(devices, MOCK_PRICES, max_load_kw=10.0)
    print(json.dumps(result, indent=2))