# GridOptima — House Energy Usage Optimizer

Full-stack energy scheduling app. Given your devices and their constraints, finds the cheapest time windows to run them using ISO New England hourly electricity prices.

## Project Structure

```
/
├── backend/          # Python FastAPI + optimization engine
│   ├── main.py       # API routes
│   ├── optimizer.py  # Core scheduling logic
│   └── requirements.txt
├── frontend/         # React (Vite) UI
│   ├── src/
│   │   ├── App.jsx
│   │   ├── api.js
│   │   ├── PriceChart.jsx
│   │   ├── DeviceForm.jsx
│   │   └── ScheduleResults.jsx
│   └── package.json
└── README.md
```

## Quickstart
### Run in 2 separate terminals
### Backend
```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload
# → http://localhost:8000
# → Docs: http://localhost:8000/docs
```

### Frontend
```bash
cd frontend
npm install
npm run dev
# → http://localhost:5173
```

## Roadmap

| Phase | Status | Description |
|-------|--------|-------------|
| 1 | ✅ | Core optimizer (greedy) + FastAPI + React skeleton |
| 2 | 🔜 | Real ISO-NE price data via API |
| 3 | 🔜 | PostgreSQL price storage |
| 4 | 🔜 | Advanced constraints (load cap, continuous run) |
| 5 | 🔜 | Pyomo/LP formal optimization |
| 6 | 🔜 | Carbon optimization mode |

## API Reference

```
GET  /health        → service status
GET  /prices        → hourly electricity prices (¢/kWh)
POST /optimize      → optimized device schedule
```

See `http://localhost:8000/docs` for interactive Swagger docs.