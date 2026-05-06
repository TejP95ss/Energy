# GridOptima - House Energy Usage Optimizer

Full-stack energy scheduling app. Given your devices and their constraints, finds the cheapest time windows to run them using ISO New England hourly electricity prices.

## Project Structure

```
/
├── backend/          # Python FastAPI + optimization engine
│   ├── main.py       # API routes
│   ├── optimizer.py  # Core scheduling logic
│   ├── database.py  
│   ├── prices.py  # Gets and stores data from ISO-NE
│   └── requirements.txt
├── data/          # Stores day-ahead data in json
├── frontend/         # React (Vite) UI
│   ├── src/
│   │   ├── App.jsx
│   │   ├── api.js
│   │   ├── PriceChart.jsx
│   │   ├── DeviceForm.jsx
│   │   └── ScheduleResults.jsx
│   │   └── HistoryPage.jsx
│   │   └── ZoneSelector.jsx
│   └── package.json
└── README.md

Note: data/ folder is not commited to git so it will only be created when you first run the program for a given node.
```

## Quickstart
### Run in 2 separate terminals
### Backend
```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload
# http://localhost:8000
# Docs: http://localhost:8000/docs
```

### Frontend
```bash
cd frontend
npm install
npm run dev
# http://localhost:5173
```

## API Reference

```
GET  /health        service status
GET  /prices        hourly electricity prices (¢/kWh)
POST /optimize      optimized device schedule
GET /prices/history see price history
GET /zones          list all ISO-NE load zones
```

See `http://localhost:8000/docs` for interactive Swagger docs.