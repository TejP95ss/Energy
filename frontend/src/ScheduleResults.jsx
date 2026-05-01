function hourLabel(h) {
  if (h === 0)  return "12:00 AM"
  if (h === 12) return "12:00 PM"
  if (h === 24) return "12:00 AM (+1)"
  if (h < 12)   return `${h}:00 AM`
  return `${h - 12}:00 PM`
}

function cents(c) {
  return `$${(c / 100).toFixed(3)}`
}

export default function ScheduleResults({ result }) {
  if (!result) return null

  const hasSavings = result.total_savings_dollars > 0
  const isLP = result.optimizer === "lp"

  return (
    <div className="results">
      <div className="results-header">
        <h2 className="results-title">Optimized Schedule</h2>
        <span className={`optimizer-badge ${isLP ? "badge-lp" : "badge-greedy"}`}>
          {isLP ? "Linear Program" : "Greedy"}
        </span>
      </div>

      <div className="summary-cards">
        <div className="summary-card">
          <div className="summary-value">${result.total_cost_dollars.toFixed(2)}</div>
          <div className="summary-label">Optimized cost</div>
        </div>
        <div className="summary-card accent-savings">
          <div className="summary-value savings-value">
            {hasSavings ? `–$${result.total_savings_dollars.toFixed(3)}` : "$0.000"}
          </div>
          <div className="summary-label">Saved vs. running immediately</div>
        </div>
        <div className="summary-card">
          <div className="summary-value">{result.total_energy_kwh} kWh</div>
          <div className="summary-label">Total energy</div>
        </div>
      </div>

      {hasSavings && (
        <div className="savings-banner">
          You save <strong>${result.total_savings_dollars.toFixed(3)}</strong> by
          running at optimized times vs. starting each device as early as possible.
        </div>
      )}

      <div className="device-results">
        {result.schedule.map((dev) => {
          const saved = dev.savings_cents
          return (
            <div key={dev.name} className="device-result-card">
              <div className="dr-header">
                <div className="dr-name">{dev.name}</div>
                {saved > 0 && (
                  <div className="dr-savings-badge">–{cents(saved)}</div>
                )}
              </div>
              <div className="dr-window">
                {hourLabel(dev.start_hour)} → {hourLabel(dev.end_hour)}
              </div>
              <div className="dr-stats">
                <span>{dev.power_kw} kW</span>
                <span>{dev.energy_kwh} kWh</span>
                <span className="dr-cost">{cents(dev.cost_cents)}</span>
                {saved > 0 && (
                  <span className="dr-was">was {cents(dev.unoptimized_cost_cents)}</span>
                )}
              </div>
            </div>
          )
        })}
      </div>

      <div className="load-info">
        Max household load cap: <strong>{result.max_load_kw} kW</strong>
      </div>
    </div>
  )
}