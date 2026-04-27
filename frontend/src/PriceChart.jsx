const HOUR_LABELS = Array.from({ length: 24 }, (_, i) => {
  const h = i % 12 || 12;
  return `${h}${i < 12 ? "a" : "p"}`;
});

export default function PriceChart({ prices, schedule }) {
  if (!prices || prices.length === 0) return null;

  const max = Math.max(...prices);
  const min = Math.min(...prices);
  const range = max - min || 1;

  // Build a set of all hours that are scheduled
  const scheduledHours = new Map(); // hour -> device name
  if (schedule) {
    for (const dev of schedule) {
      for (const h of dev.hours) {
        scheduledHours.set(h, dev.name);
      }
    }
  }

  return (
    <div className="price-chart">
      <div className="chart-bars">
        {prices.map((p, i) => {
          const heightPct = 20 + ((p - min) / range) * 75;
          const isScheduled = scheduledHours.has(i);
          const isPeak = p >= 12;
          return (
            <div key={i} className="bar-col">
              <div className="bar-value">{Math.round(p * 10) / 10}</div>
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