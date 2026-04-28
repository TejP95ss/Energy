const HOUR_LABELS = Array.from({ length: 24 }, (_, i) => {
  const h = i % 12 || 12;
  return `${h}${i < 12 ? "a" : "p"}`;
});

export default function PriceChart({ prices, schedule, source, date, isFallback }) {
  if (!prices || prices.length === 0) return null;

  const max = Math.max(...prices);
  const min = Math.min(...prices);
  const range = max - min || 1;

  const scheduledHours = new Map();
  if (schedule) {
    for (const dev of schedule) {
      for (const h of dev.hours) {
        scheduledHours.set(h, dev.name);
      }
    }
  }

  return (
    <div className="price-chart">
      <div className="chart-meta">
        <span className={`source-badge ${isFallback ? "badge-mock" : "badge-live"}`}>
          {isFallback ? "⚠ Mock data" : "● ISO-NE Predictions"}
        </span>
        {date && <span className="chart-date">{date}</span>}
        <span className="chart-range">
          {min.toFixed(2)}–{max.toFixed(2)} ¢/kWh
        </span>
      </div>
      <div className="chart-bars">
        {prices.map((p, i) => {
          const FLOOR = 2; //change the floor and ceiling if some values go out of the chart
          const CEIL = 10; 
          const heightPct = ((p - FLOOR) / (CEIL - FLOOR)) * 100;
          const isScheduled = scheduledHours.has(i);
          const isPeak = p >= max * 0.8;
          return (
            <div key={i} className="bar-col">
              <div className="bar-value">{p.toFixed(2)}</div>
              <div
                className={`bar ${isPeak ? "bar-peak" : "bar-low"} ${isScheduled ? "bar-scheduled" : ""}`}
                style={{ height: `${heightPct}%` }}
                title={`${HOUR_LABELS[i]}: ${p}¢${isScheduled ? ` — ${scheduledHours.get(i)}` : ""}`}
              />
              <div className="bar-label">{HOUR_LABELS[i]}</div>
            </div>
          );
        })}
      </div>
      <div className="chart-legend">
        <span className="legend-dot dot-low" /> Off-peak
        <span className="legend-dot dot-peak" /> Peak
        <span className="legend-dot dot-scheduled" /> Scheduled
      </div>
    </div>
  );
}