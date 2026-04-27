from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, model_validator
from typing import Optional
from optimizer import Device, optimize, MOCK_PRICES_CENTS

app = FastAPI(
    title="House Energy Optimizer API",
    description="ISO New England greedy energy scheduler (Phase 1)",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# Pydantic schemas
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
    use_mock_prices: bool = Field(True, description="Use hardcoded ISO-NE mock prices")


class ScheduledDeviceOut(BaseModel):
    name: str
    start_hour: int
    end_hour: int
    hours: list[int]
    power_kw: float
    energy_kwh: float
    cost_cents: float


class OptimizeResponse(BaseModel):
    prices_cents_per_kwh: list[float]
    schedule: list[ScheduledDeviceOut]
    total_cost_cents: float
    total_cost_dollars: float
    total_energy_kwh: float


# Endpoints
@app.get("/health")
def health():
    return {"status": "ok", "version": "0.1.0"}


@app.get("/prices", summary="Get current mock hourly prices")
def get_prices():
    return {
        "source": "mock_iso_ne",
        "unit": "cents_per_kwh",
        "hours": list(range(24)),
        "prices": MOCK_PRICES_CENTS,
    }


@app.post("/optimize", response_model=OptimizeResponse, summary="Optimize device schedule")
def run_optimize(req: OptimizeRequest):
    prices = MOCK_PRICES_CENTS  #will later fetch real ISO-NE prices

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

    return result