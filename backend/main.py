from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, model_validator
from typing import Optional
from optimizer import Device, optimize
from prices import get_prices, MOCK_PRICES

app = FastAPI(
    title="House Energy Optimizer API",
    description="ISO New England energy scheduler",
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# Schemas
class DeviceInput(BaseModel):
    name: str = Field(..., example="EV Charger")
    energy_kwh: float = Field(..., gt=0, example=40.0)
    duration_hours: int = Field(..., ge=1, le=24, example=8)
    earliest_start: int = Field(..., ge=0, le=23, example=0)
    latest_end: int = Field(..., ge=1, le=24, example=8)
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
    use_live_prices: bool = Field(True, description="Fetch real ISO-NE prices")


class ScheduledDeviceOut(BaseModel):
    name: str
    start_hour: int
    end_hour: int
    hours: list[int]
    power_kw: float
    energy_kwh: float
    cost_cents: float


class OptimizeResponse(BaseModel):
    price_source: str
    price_date: str
    price_node: str
    is_fallback: bool
    prices_cents_per_kwh: list[float]
    schedule: list[ScheduledDeviceOut]
    total_cost_cents: float
    total_cost_dollars: float
    total_energy_kwh: float


# Endpoints
@app.get("/health")
def health():
    return {"status": "ok", "version": "0.2.0"}


@app.get("/prices", summary="Get hourly electricity prices")
def fetch_prices(live: bool = Query(True, description="Fetch from ISO-NE (false = mock)")):
    return get_prices(live=live)


@app.post("/optimize", response_model=OptimizeResponse, summary="Optimize device schedule")
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
        result = optimize(devices, prices)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    return {
        "price_source": price_data["source"],
        "price_date": price_data["date"],
        "price_node": price_data["node"],
        "is_fallback": price_data["fallback"],
        **result,
    }