import { useState, useEffect } from "react"
import { fetchPriceHistory } from "./api"

const HOUR_LABELS = Array.from({ length: 24 }, (_, i) => {
  if (i === 0) return "12am"
  if (i === 12) return "12pm"
  return i < 12 ? `${i}am` : `${i - 12}pm`
})

// Color scale: green (cheap) → yellow → red (expensive)
function priceColor(price, min, max) {
  const t = Math.max(0, Math.min(1, (price - min) / (max - min || 1)))
  if (t < 0.5) {
    const r = Math.round(t * 2 * 255)
    return `rgb(${r}, 185, 80)`
  } else {
    const t2 = (t - 0.5) * 2
    const g = Math.round((1 - t2) * 185)
    return `rgb(248, ${g}, ${Math.round((1 - t2) * 80)})`
  }
}

function avg(arr) {
  return arr.reduce((a, b) => a + b, 0) / arr.length
}

export default function HistoryPage() {
  const [history, setHistory] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [days, setDays] = useState(7)
  const [view, setView] = useState("heatmap") // "heatmap" | "chart"

  useEffect(() => {
    setLoading(true)
    setError(null)
    fetchPriceHistory(days)
      .then(data => {
        setHistory(data)
        setLoading(false)
      })
      .catch(() => {
        setError("Could not load price history — is the backend running?")
        setLoading(false)
      })
  }, [days])

  if (loading) return <div className="history-loading">Loading price history…</div>
  if (error)   return <div className="error-box">{error}</div>

  const entries = Object.entries(history?.history ?? {}).sort(([a], [b]) => a.localeCompare(b))

  if (entries.length === 0) {
    return (
      <div className="empty-state">
        <div className="empty-icon">📂</div>
        <p>No cached price history yet. Visit the <strong>Optimizer</strong> page to fetch today's prices, then come back here.</p>
      </div>
    )
  }

  // Stats across all days
  const allPrices = entries.flatMap(([, prices]) => prices)
  const globalMin = Math.min(...allPrices)
  const globalMax = Math.max(...allPrices)

  const dailyStats = entries.map(([date, prices]) => ({
    date,
    avg: avg(prices),
    min: Math.min(...prices),
    max: Math.max(...prices),
    prices,
  }))

  const cheapestDay = dailyStats.reduce((a, b) => a.avg < b.avg ? a : b)
  const mostExpensiveDay = dailyStats.reduce((a, b) => a.avg > b.avg ? a : b)

  // Per-hour averages across all days
  const hourlyAvg = Array.from({ length: 24 }, (_, h) =>
    avg(entries.map(([, prices]) => prices[h]))
  )
  const cheapestHour = hourlyAvg.indexOf(Math.min(...hourlyAvg))
  const peakHour = hourlyAvg.indexOf(Math.max(...hourlyAvg))

  function formatDate(iso) {
    return new Date(iso + "T12:00:00").toLocaleDateString("en-US", {
      weekday: "short", month: "short", day: "numeric"
    })
  }

  return (
    <div className="history-page">

      {/* Controls */}
      <div className="history-controls">
        <div className="control-group">
          <span className="control-label">Days</span>
          {[7, 14, 30].map(d => (
            <button
              key={d}
              className={`control-btn ${days === d ? "control-btn-active" : ""}`}
              onClick={() => setDays(d)}
            >
              {d}d
            </button>
          ))}
        </div>
        <div className="control-group">
          <span className="control-label">View</span>
          <button
            className={`control-btn ${view === "heatmap" ? "control-btn-active" : ""}`}
            onClick={() => setView("heatmap")}
          >
            Heatmap
          </button>
          <button
            className={`control-btn ${view === "chart" ? "control-btn-active" : ""}`}
            onClick={() => setView("chart")}
          >
            Chart
          </button>
        </div>
        <span className="history-meta">
          {entries.length} day{entries.length !== 1 ? "s" : ""} cached · {globalMin.toFixed(1)}–{globalMax.toFixed(1)} ¢/kWh range
        </span>
      </div>

      {/* Summary cards */}
      <div className="history-summary">
        <div className="summary-card">
          <div className="summary-value" style={{ color: "var(--accent2)" }}>
            {formatDate(cheapestDay.date)}
          </div>
          <div className="summary-label">Cheapest day avg {cheapestDay.avg.toFixed(1)} ¢/kWh</div>
        </div>
        <div className="summary-card">
          <div className="summary-value" style={{ color: "var(--peak)" }}>
            {formatDate(mostExpensiveDay.date)}
          </div>
          <div className="summary-label">Most expensive avg {mostExpensiveDay.avg.toFixed(1)} ¢/kWh</div>
        </div>
        <div className="summary-card">
          <div className="summary-value" style={{ color: "var(--accent2)" }}>
            {HOUR_LABELS[cheapestHour]}
          </div>
          <div className="summary-label">Cheapest hour avg {hourlyAvg[cheapestHour].toFixed(1)} ¢/kWh</div>
        </div>
        <div className="summary-card">
          <div className="summary-value" style={{ color: "var(--peak)" }}>
            {HOUR_LABELS[peakHour]}
          </div>
          <div className="summary-label">Peak hour avg {hourlyAvg[peakHour].toFixed(1)} ¢/kWh</div>
        </div>
      </div>

      {/* Heatmap view */}
      {view === "heatmap" && (
        <div className="section">
          <h2 className="section-title">Price Heatmap</h2>
          <p className="section-desc">Each cell is ¢/kWh. Green = cheap, red = expensive.</p>
          <div className="heatmap-container">
            <div className="heatmap-grid" style={{ gridTemplateColumns: `64px repeat(24, 1fr)` }}>
              {/* Header row */}
              <div className="heatmap-corner" />
              {HOUR_LABELS.map(label => (
                <div key={label} className="heatmap-hour-label">{label}</div>
              ))}
              {/* Data rows */}
              {dailyStats.map(({ date, prices }) => (
                <>
                  <div key={`label-${date}`} className="heatmap-date-label">
                    {formatDate(date)}
                  </div>
                  {prices.map((price, h) => (
                    <div
                      key={`${date}-${h}`}
                      className="heatmap-cell"
                      style={{ background: priceColor(price, globalMin, globalMax) }}
                      title={`${formatDate(date)} ${HOUR_LABELS[h]}: ${price.toFixed(2)}¢/kWh`}
                    />
                  ))}
                </>
              ))}
              {/* Average row */}
              <div className="heatmap-date-label heatmap-avg-label">Avg</div>
              {hourlyAvg.map((price, h) => (
                <div
                  key={`avg-${h}`}
                  className="heatmap-cell heatmap-avg-cell"
                  style={{ background: priceColor(price, globalMin, globalMax) }}
                  title={`Hour avg ${HOUR_LABELS[h]}: ${price.toFixed(2)}¢/kWh`}
                />
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Line chart view */}
      {view === "chart" && (
        <div className="section">
          <h2 className="section-title">Daily Price Curves</h2>
          <p className="section-desc">Hourly prices overlaid across all cached days.</p>
          <div className="line-chart-container">
            <svg viewBox="0 0 760 220" className="line-chart-svg">
              {/* Grid lines */}
              {[0, 25, 50, 75, 100].map(pct => {
                const y = 10 + (pct / 100) * 190
                return (
                  <g key={pct}>
                    <line x1="40" y1={y} x2="750" y2={y} stroke="var(--border)" strokeWidth="0.5" />
                    <text x="35" y={y + 4} textAnchor="end" fontSize="8" fill="var(--text2)">
                      {(globalMax - (pct / 100) * (globalMax - globalMin)).toFixed(0)}
                    </text>
                  </g>
                )
              })}
              {/* Hour labels */}
              {[0, 6, 12, 18, 23].map(h => {
                const x = 40 + (h / 23) * 710
                return (
                  <text key={h} x={x} y={215} textAnchor="middle" fontSize="8" fill="var(--text2)">
                    {HOUR_LABELS[h]}
                  </text>
                )
              })}
              {/* One line per day */}
              {dailyStats.map(({ date, prices }, dayIdx) => {
                const hue = (dayIdx * 47) % 360
                const points = prices.map((price, h) => {
                  const x = 40 + (h / 23) * 710
                  const y = 10 + ((globalMax - price) / (globalMax - globalMin || 1)) * 190
                  return `${x},${y}`
                }).join(" ")
                return (
                  <polyline
                    key={date}
                    points={points}
                    fill="none"
                    stroke={`hsl(${hue}, 70%, 60%)`}
                    strokeWidth="1.5"
                    opacity="0.8"
                  />
                )
              })}
              {/* Average line */}
              {(() => {
                const points = hourlyAvg.map((price, h) => {
                  const x = 40 + (h / 23) * 710
                  const y = 10 + ((globalMax - price) / (globalMax - globalMin || 1)) * 190
                  return `${x},${y}`
                }).join(" ")
                return (
                  <polyline
                    points={points}
                    fill="none"
                    stroke="white"
                    strokeWidth="2"
                    strokeDasharray="4 2"
                    opacity="0.9"
                  />
                )
              })()}
            </svg>
            <div className="chart-legend" style={{ marginTop: "0.5rem" }}>
              {dailyStats.map(({ date }, i) => (
                <span key={date} style={{ display: "flex", alignItems: "center", gap: "4px", fontSize: "0.65rem", color: "var(--text2)" }}>
                  <span style={{ display: "inline-block", width: 12, height: 2, background: `hsl(${(i * 47) % 360}, 70%, 60%)`, borderRadius: 1 }} />
                  {formatDate(date)}
                </span>
              ))}
              <span style={{ display: "flex", alignItems: "center", gap: "4px", fontSize: "0.65rem", color: "var(--text2)" }}>
                <span style={{ display: "inline-block", width: 12, height: 2, background: "white", borderRadius: 1 }} />
                Average
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Daily averages bar chart */}
      <div className="section">
        <h2 className="section-title">Daily Average Price</h2>
        <p className="section-desc">Average ¢/kWh per day across all 24 hours.</p>
        <div className="daily-bars">
          {dailyStats.map(({ date, avg: dayAvg }) => {
            const pct = ((dayAvg - globalMin) / (globalMax - globalMin || 1)) * 100
            const isMin = date === cheapestDay.date
            const isMax = date === mostExpensiveDay.date
            return (
              <div key={date} className="daily-bar-col">
                <div className="daily-bar-value">{dayAvg.toFixed(1)}¢</div>
                <div
                  className="daily-bar-fill"
                  style={{
                    height: `${20 + pct * 0.7}%`,
                    background: isMin ? "var(--accent2)" : isMax ? "var(--peak)" : "var(--accent)",
                    opacity: 0.8,
                  }}
                />
                <div className="daily-bar-label">
                  {formatDate(date).replace(/,.*/, "").split(" ")[0]}
                </div>
              </div>
            )
          })}
        </div>
      </div>

    </div>
  )
}