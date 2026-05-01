"""
Optimization engine for house energy scheduling.
Region: ISO New England

Phase 5: Linear Programming via PuLP
  - Binary decision variables: x[d][h] = 1 if device d runs during hour h
  - Objective: minimize total electricity cost across all devices and hours
  - Constraints:
      1. Each device runs for exactly its required duration
      2. Device only runs within its allowed time window
      3. Device runs in a consecutive block (not scattered hours)
      4. Total household load at any hour <= max_load_kw

Falls back to greedy if PuLP is unavailable or solver fails.
"""

from dataclasses import dataclass
from typing import Optional
import pulp

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
    unoptimized_cost_cents: float

# ---------------------------------------------------------------------------
# LP optimizer (PuLP)
# ---------------------------------------------------------------------------
def _optimize_lp(devices: list[Device], prices: list[float], max_load_kw: float) -> list[ScheduledDevice]:
    """
    Solve the scheduling problem as a Mixed-Integer Linear Program.

    Decision variable: start[d] = integer hour device d begins running
    This is a cleaner formulation than per-hour binary vars because
    consecutive-run constraints are trivially satisfied.

    For each device d with start hour s:
      - runs during hours s, s+1, ..., s+duration-1
      - cost = sum(prices[h] * power_kw) for h in that range
      - constraint: earliest_start <= s <= latest_end - duration
    """

    prob = pulp.LpProblem("energy_scheduling", pulp.LpMinimize)

    # Binary variable: b[d][s] = 1 if device d starts at hour s
    b = {}
    for d in devices:
        b[d.name] = {}
        latest_valid_start = d.latest_end - d.duration_hours
        for s in range(d.earliest_start, latest_valid_start + 1):
            b[d.name][s] = pulp.LpVariable(
                f"b_{d.name.replace(' ', '_')}_{s}",
                cat="Binary",
            )

    # Each device must start exactly once
    for d in devices:
        prob += pulp.lpSum(b[d.name].values()) == 1, f"one_start_{d.name}"

    # Objective: minimize total cost
    cost_terms = []
    for d in devices:
        for s, var in b[d.name].items():
            hours = range(s, s + d.duration_hours)
            window_cost = sum(prices[h] * d.power_kw for h in hours)
            cost_terms.append(window_cost * var)
    prob += pulp.lpSum(cost_terms), "total_cost"

    # Load cap: at each hour, sum of power from all running devices <= max_load_kw
    for h in range(24):
        load_terms = []
        for d in devices:
            for s, var in b[d.name].items():
                if s <= h < s + d.duration_hours:
                    load_terms.append(d.power_kw * var)
        if load_terms:
            prob += pulp.lpSum(load_terms) <= max_load_kw, f"load_cap_h{h}"

    # Solve (CBC solver, bundled with PuLP, no install needed)
    solver = pulp.PULP_CBC_CMD(msg=0)  # msg=0 = silent
    status = prob.solve(solver)

    if pulp.LpStatus[prob.status] not in ("Optimal", "Feasible"):
        raise ValueError(
            f"LP solver could not find a feasible schedule. "
            f"Status: {pulp.LpStatus[prob.status]}. "
            f"Try raising the load cap or widening device time windows."
        )

    # Extract solution
    results = []
    for d in devices:
        chosen_start = None
        for s, var in b[d.name].items():
            if pulp.value(var) is not None and pulp.value(var) > 0.5:
                chosen_start = s
                break

        if chosen_start is None:
            raise ValueError(f"No start hour found for '{d.name}' in LP solution")

        hours = list(range(chosen_start, chosen_start + d.duration_hours))
        cost = sum(prices[h] * d.power_kw for h in hours)

        unopt_hours = list(range(d.earliest_start, d.earliest_start + d.duration_hours))
        unopt_cost = sum(prices[h] * d.power_kw for h in unopt_hours)

        results.append(ScheduledDevice(
            name=d.name,
            start_hour=chosen_start,
            end_hour=chosen_start + d.duration_hours,
            hours=hours,
            cost_cents=round(cost, 4),
            energy_kwh=round(d.power_kw * d.duration_hours, 4),
            power_kw=round(d.power_kw, 4),
            unoptimized_cost_cents=round(unopt_cost, 4),
        ))

    return results


# ---------------------------------------------------------------------------
# Greedy fallback
# ---------------------------------------------------------------------------
def _optimize_greedy(devices: list[Device], prices: list[float], max_load_kw: float) -> list[ScheduledDevice]:
    load_by_hour = [0.0] * 24
    ordered = sorted(devices, key=lambda d: d.power_kw, reverse=True)
    results = []

    for d in ordered:
        best_start = None
        best_cost = float("inf")
        window = d.duration_hours

        for start in range(d.earliest_start, d.latest_end - window + 1):
            hours = list(range(start, start + window))
            if any(load_by_hour[h] + d.power_kw > max_load_kw for h in hours):
                continue
            cost = sum(prices[h] * d.power_kw for h in hours)
            if cost < best_cost:
                best_cost = cost
                best_start = start

        if best_start is None:
            raise ValueError(
                f"No valid window for '{d.name}'. "
                f"Try raising the load cap or widening the time window."
            )

        hours = list(range(best_start, best_start + window))
        for h in hours:
            load_by_hour[h] += d.power_kw

        unopt_hours = list(range(d.earliest_start, d.earliest_start + window))
        unopt_cost = sum(prices[h] * d.power_kw for h in unopt_hours)

        results.append(ScheduledDevice(
            name=d.name,
            start_hour=best_start,
            end_hour=best_start + window,
            hours=hours,
            cost_cents=round(best_cost, 4),
            energy_kwh=round(d.power_kw * window, 4),
            power_kw=round(d.power_kw, 4),
            unoptimized_cost_cents=round(unopt_cost, 4),
        ))

    return results


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------
def optimize(devices: list[Device], prices: list[float], max_load_kw: float = 10.0) -> dict:
    """
    Run LP optimizer with greedy fallback.
    Returns a unified result dict regardless of which solver ran.
    """
    method_used = "lp"
    try:
        schedule = _optimize_lp(devices, prices, max_load_kw)
    except ImportError:
        print("[optimizer] PuLP not available, falling back to greedy")
        method_used = "greedy_fallback"
        schedule = _optimize_greedy(devices, prices, max_load_kw)
    except Exception as e:
        # If LP fails for any reason (infeasible, solver crash), try greedy
        print(f"[optimizer] LP failed ({e}), falling back to greedy")
        method_used = "greedy_fallback"
        schedule = _optimize_greedy(devices, prices, max_load_kw)

    # Restore original input order for display
    name_order = {d.name: i for i, d in enumerate(devices)}
    schedule.sort(key=lambda s: name_order.get(s.name, 999))

    total_cost = sum(s.cost_cents for s in schedule)
    total_unopt = sum(s.unoptimized_cost_cents for s in schedule)
    total_energy = sum(s.energy_kwh for s in schedule)
    savings = total_unopt - total_cost

    return {
        "optimizer": method_used,
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
        "total_unoptimized_cost_cents": round(total_unopt, 4),
        "total_unoptimized_cost_dollars": round(total_unopt / 100, 4),
        "total_savings_cents": round(savings, 4),
        "total_savings_dollars": round(savings / 100, 4),
        "total_energy_kwh": round(total_energy, 4),
    }


if __name__ == "__main__":
    import json
    from prices import MOCK_PRICES

    devices = [
        Device("EV Charger",      energy_kwh=40.0, duration_hours=8, earliest_start=0,  latest_end=8),
        Device("Dishwasher",      energy_kwh=1.5,  duration_hours=2, earliest_start=19, latest_end=24),
        Device("Washing Machine", energy_kwh=2.0,  duration_hours=1, earliest_start=0,  latest_end=8),
    ]

    result = optimize(devices, MOCK_PRICES, max_load_kw=10.0)
    print(json.dumps(result, indent=2))
    print(f"\nOptimizer used: {result['optimizer']}")
    print(f"Total savings: ${result['total_savings_dollars']:.4f}")