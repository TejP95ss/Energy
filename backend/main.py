from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, model_validator
from typing import Optional
from optimizer import Device, optimize
from prices import get_prices, get_price_history
from contextlib import asynccontextmanager
from dotenv import load_dotenv
load_dotenv()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # DB init removed — using local file cache instead.
    # database.py is kept for future cloud deployment.
    print("[startup] GridOptima ready (file-cache mode)")
    yield

app = FastAPI(
    title="House Energy Optimizer API",
    description="ISO New England energy scheduler",
    version="0.5.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class DeviceInput(BaseModel):
    name: str = Field(..., example="EV Charger")
    energy_kwh: float = Field(..., gt=0)
    duration_hours: int = Field(..., ge=1, le=24)
    earliest_start: int = Field(..., ge=0, le=23)
    latest_end: int = Field(..., ge=1, le=24)
    power_kw: Optional[float] = Field(None, gt=0)

    @model_validator(mode="after")
    def window_fits_duration(self):
        window = self.latest_end - self.earliest_start
        if window < self.duration_hours:
            raise ValueError(
                f"Window ({window}h) is smaller than duration ({self.duration_hours}h) "
                f"for device '{self.name}'"
            )
        return self


class OptimizeRequest(BaseModel):
    devices: list[DeviceInput] = Field(..., min_length=1)
    use_live_prices: bool = Field(True)
    max_load_kw: float = Field(20.0, gt=0, le=100)


class ScheduledDeviceOut(BaseModel):
    name: str
    start_hour: int
    end_hour: int
    hours: list[int]
    power_kw: float
    energy_kwh: float
    cost_cents: float
    unoptimized_cost_cents: float
    savings_cents: float


class OptimizeResponse(BaseModel):
    price_source: str
    price_date: str
    price_node: str
    is_fallback: bool
    prices_cents_per_kwh: list[float]
    max_load_kw: float
    schedule: list[ScheduledDeviceOut]
    total_cost_cents: float
    total_cost_dollars: float
    total_unoptimized_cost_dollars: float
    total_savings_cents: float
    total_savings_dollars: float
    total_energy_kwh: float


@app.get("/health")
def health():
    return {"status": "ok", "version": "0.4.0"}


@app.get("/prices")
def fetch_prices(live: bool = Query(True)):
    return get_prices(live=live)

@app.get("/prices/history")
def price_history(days: int = Query(7, ge=1, le=30)):
    history = get_price_history(days=days)
    return {
        "node": ".Z.NEMASSBOST",
        "days_requested": days,
        "days_available": len(history),
        "history": history,
    }


@app.post("/optimize", response_model=OptimizeResponse)
def run_optimize(req: OptimizeRequest):
    price_data = get_prices(live=req.use_live_prices)
    prices = price_data["prices"]

    devices = [
        Device(
            name=d.name,
            energy_kwh=d.energy_kwh,
            duration_hours=d.duration_hours,
            earliest_start=d.earliest_start,
            latest_end=d.latest_end,
            power_kw=d.power_kw,
        )
        for d in req.devices
    ]

    try:
        result = optimize(devices, prices, max_load_kw=req.max_load_kw)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    return {
        "price_source": price_data["source"],
        "price_date": price_data["date"],
        "price_node": price_data["node"],
        "is_fallback": price_data["fallback"],
        **result,
    }