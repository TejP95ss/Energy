function hourLabel(h) {
  if (h === 0) return "12:00 AM";
  if (h === 12) return "12:00 PM";
  if (h < 12) return `${h}:00 AM`;
  if (h === 24) return "12:00 AM (+1)";
  return `${h - 12}:00 PM`;
}

export default function ScheduleResults({ result }) {
  if (!result) return null;

  return (
    <div className="results">
      <h2 className="results-title">Optimized Schedule</h2>

      <div className="summary-cards">
        <div className="summary-card">
          <div className="summary-value">${result.total_cost_dollars.toFixed(2)}</div>
          <div className="summary-label">Total cost</div>
        </div>
        <div className="summary-card">
          <div className="summary-value">{result.total_energy_kwh} kWh</div>
          <div className="summary-label">Total energy</div>
        </div>
        <div className="summary-card">
          <div className="summary-value">{result.schedule.length}</div>
          <div className="summary-label">Devices scheduled</div>
        </div>
      </div>

      <div className="device-results">
        {result.schedule.map((dev) => (
          <div key={dev.name} className="device-result-card">
            <div className="dr-name">{dev.name}</div>
            <div className="dr-window">
              {hourLabel(dev.start_hour)} → {hourLabel(dev.end_hour)}
            </div>
            <div className="dr-stats">
              <span>{dev.power_kw} kW</span>
              <span>{dev.energy_kwh} kWh</span>
              <span className="dr-cost">{(dev.cost_cents / 100).toFixed(3)} USD</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}