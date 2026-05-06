import { useState, useEffect } from "react"
import { fetchPriceHistory } from "./api"

const HOUR_LABELS = Array.from({ length: 24 }, (_, i) => {
  if (i === 0) return "12am"
  if (i === 12) return "12pm"
  return i < 12 ? `${i}am` : `${i - 12}pm`
})

function avg(arr) {
  const valid = arr.filter(v => v != null)
  if (!valid.length) return null
  return valid.reduce((a, b) => a + b, 0) / valid.length
}

function formatDate(iso) {
  return new Date(iso + "T12:00:00").toLocaleDateString("en-US", {
    weekday: "short", month: "short", day: "numeric",
  })
}

// Reliability helpers (magnitude-based)
function reliabilityLevel(absDiff) {
  if (absDiff > 1) return "Low"
  if (absDiff > 0.5) return "Medium"
  return "High"
}

function reliabilityColor(level) {
  if (level === "Low") return "var(--peak)"      // red
  if (level === "Medium") return "orange"
  return "var(--accent2)"                        // green
}

export default function HistoryPage({ node = ".Z.NEMASSBOST" }) {
  const [history, setHistory] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [days, setDays] = useState(7)

  useEffect(() => {
    setLoading(true)
    setError(null)
    fetchPriceHistory(days, node)
      .then(data => { setHistory(data); setLoading(false) })
      .catch(() => {
        setError("Could not load price history — is the backend running?")
        setLoading(false)
      })
  }, [days, node])

  if (loading) return <div className="history-loading">Loading price history…</div>
  if (error) return <div className="error-box">{error}</div>

  const entries = history?.history ?? []

  if (entries.length === 0) {
    return (
      <div className="empty-state">
        <div className="empty-icon">📂</div>
        <p>No cached price history yet for <strong>{history?.zone_name || node}</strong>.</p>
      </div>
    )
  }

  const entriesWithRT = entries.filter(e => e.real_time_complete)

  // Hourly avg diff
  const hourlyAvgDiff = Array.from({ length: 24 }, (_, h) => {
    const diffs = entriesWithRT
      .map(e => e.real_time[h] != null ? e.real_time[h] - e.day_ahead[h] : null)
      .filter(v => v != null)
    return diffs.length ? avg(diffs) : null
  })

  // Hourly avg percent error
  const hourlyAvgPctError = Array.from({ length: 24 }, (_, h) => {
    const das = entriesWithRT
      .map(e => e.day_ahead[h])
      .filter(v => v != null)

    const avgDA = das.length ? avg(das) : null
    const absDiff = hourlyAvgDiff[h] != null ? Math.abs(hourlyAvgDiff[h]) : null

    if (avgDA == null || avgDA === 0 || absDiff == null) return null

    return (absDiff / avgDA) * 100
  })

  // ---- Forecast metrics ----
  const allErrors = entriesWithRT.flatMap(e =>
    e.real_time.map((rt, h) =>
      rt != null ? rt - e.day_ahead[h] : null
    )
  ).filter(v => v != null)

  const mae = avg(allErrors.map(e => Math.abs(e)))
  const rmse = Math.sqrt(avg(allErrors.map(e => e * e)))
  const bias = avg(allErrors)

  // Best / worst hour
  const sortedHours = hourlyAvgDiff
    .map((d, h) => ({ h, d }))
    .filter(x => x.d != null)
    .sort((a, b) => Math.abs(b.d) - Math.abs(a.d))

  const worst = sortedHours[0]
  const best = sortedHours[sortedHours.length - 1]

  return (
    <div className="history-page">

      {/* Controls */}
      <div className="history-controls">
        <div className="control-group">
          <span className="control-label">Days</span>
          {[7, 14, 30].map(d => (
            <button key={d}
              className={`control-btn ${days === d ? "control-btn-active" : ""}`}
              onClick={() => setDays(d)}>{d}d</button>
          ))}
        </div>

        <span className="history-meta">
          {entries.length} days · {entriesWithRT.length} with RT · {history?.zone_name || node}
        </span>
      </div>

      {/* Forecast accuracy */}
      <div className="history-summary">
        <div className="summary-card">
          <div className="summary-value">{mae?.toFixed(2) ?? "—"} ¢</div>
          <div className="summary-label">Mean absolute error</div>
        </div>
        <div className="summary-card">
          <div className="summary-value">{rmse?.toFixed(2) ?? "—"} ¢</div>
          <div className="summary-label">RMSE</div>
        </div>
        <div className="summary-card">
          <div className="summary-value" style={{ color: bias > 0 ? "var(--peak)" : "var(--accent2)" }}>
            {bias?.toFixed(2) ?? "—"} ¢
          </div>
          <div className="summary-label">Bias (RT − DA)</div>
        </div>
      </div>

      {/* Insight banner */}
      {worst && (
        <div className="savings-banner">
          Worst hour: <strong>{HOUR_LABELS[worst.h]}</strong> ({worst.d > 0 ? "+" : ""}{worst.d.toFixed(2)}¢)
          {" · "}
          Most accurate: <strong>{HOUR_LABELS[best.h]}</strong> ({best.d.toFixed(2)}¢)
        </div>
      )}

      {/* Chart */}
      <div className="section">
        <h2 className="section-title">Forecast Error by Hour</h2>

        <p className="section-desc">
          How accurate day-ahead prices are by hour. Lower error = more reliable.
        </p>

        {entriesWithRT.length === 0 ? (
          <div className="empty-state"><p>No RT data yet.</p></div>
        ) : (
          <div className="hourly-table-wrapper">
            <table className="hourly-table">
              <thead>
                <tr>
                  <th>Hour</th>
                  <th>Avg Bias</th>
                  <th>Avg % Error</th>
                  <th>Reliability</th>
                </tr>
              </thead>
              <tbody>
                {hourlyAvgDiff.map((diff, h) => {
                  const pct = hourlyAvgPctError[h]

                  if (diff == null) {
                    return (
                      <tr key={h}>
                        <td>{HOUR_LABELS[h]}</td>
                        <td colSpan="4">—</td>
                      </tr>
                    )
                  }

                  const abs = Math.abs(diff)
                  const reliability = reliabilityLevel(abs)
                  const color = reliabilityColor(reliability)

                  return (
                    <tr key={h}>
                      <td>{HOUR_LABELS[h]}</td>

                      <td style={{ color }}>
                      {diff != null
                        ? `${diff > 0 ? "+" : ""}${diff.toFixed(2)} ¢`
                        : "—"}
                      </td>
                      
                      <td style={{ color }}>
                        {pct != null ? `${pct.toFixed(1)}%` : "—"}
                      </td>

                      <td style={{ color }}>
                        {reliability}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Table */}
      <div className="dart-table-wrapper">
        <table className="dart-table">
          <thead>
            <tr>
              <th>Date</th>
              <th>DA avg</th>
              <th>RT avg</th>
              <th>Diff</th>
              <th>Avg Hourly Error</th>
              <th>Max Hourly Error</th>
            </tr>
          </thead>
          <tbody>
            {entries.map(e => {
              const daRaw = avg(e.day_ahead)
              const rtRaw = e.real_time ? avg(e.real_time.filter(Boolean)) : null

              const da = daRaw != null ? Number(daRaw.toFixed(2)) : null
              const rt = rtRaw != null ? Number(rtRaw.toFixed(2)) : null

              const diff = (da != null && rt != null)? Number((da - rt).toFixed(2)) : null

              const errors = e.real_time?.map((rt, h) =>
                rt != null ? Math.abs(rt - e.day_ahead[h]) : null
              ).filter(v => v != null) || []

              const avgError = avg(errors)
              const maxError = errors.length ? Math.max(...errors) : null

              return (
                <tr key={e.date}>
                  <td>{formatDate(e.date)}</td>
                  <td>{da?.toFixed(2)} ¢</td>
                  <td>{rt?.toFixed(2) ?? "—"} ¢</td>
                  <td >{diff != null ? `${diff > 0 ? "+" : ""}${diff.toFixed(2)} ¢` : "—"}
                  </td>
                  <td>{avgError?.toFixed(2) ?? "—"} ¢</td>
                  <td style={{ color: "var(--peak)" }}>{maxError?.toFixed(2) ?? "—"} ¢</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

    </div>
  )
}