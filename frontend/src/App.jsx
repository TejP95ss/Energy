import { useState, useEffect } from "react"
import { Routes, Route, NavLink } from "react-router-dom"
import { fetchPrices, runOptimize } from "./api"
import PriceChart from "./PriceChart"
import DeviceForm from "./DeviceForm"
import ScheduleResults from "./ScheduleResults"
import HistoryPage from "./HistoryPage"
import "./App.css"

function OptimizerPage({ useLive }) {
  const [priceData, setPriceData] = useState(null)
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [priceError, setPriceError] = useState(null)

  useEffect(() => {
    setPriceData(null)
    setPriceError(null)
    fetchPrices(useLive)
      .then(setPriceData)
      .catch(() => setPriceError("Could not load prices — is the backend running?"))
  }, [useLive])

  async function handleOptimize(devices, maxLoadKw) {
    setLoading(true)
    setError(null)
    try {
      const data = await runOptimize(devices, useLive, maxLoadKw)
      setResult(data)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <>
      <section className="section">
        <h2 className="section-title">Today's Electricity Prices</h2>
        <p className="section-desc">
          Day-ahead hourly LMPs (¢/kWh) · Node: .Z.NEMASSBOST · Highlighted bars show scheduled windows.
        </p>
        {priceError ? (
          <div className="error-box">{priceError}</div>
        ) : (
          <PriceChart
            prices={priceData?.prices}
            schedule={result?.schedule}
            source={priceData?.source}
            date={priceData?.date}
            isFallback={priceData?.fallback}
          />
        )}
      </section>

      <div className="two-col">
        <section className="section">
          <h2 className="section-title">Your Devices</h2>
          <p className="section-desc">
            Set each device's energy need, run duration, and allowed time window.
          </p>
          <DeviceForm onSubmit={handleOptimize} loading={loading} />
          {error && <div className="error-box">{error}</div>}
        </section>

        <section className="section">
          <ScheduleResults result={result} />
          {!result && (
            <div className="empty-state">
              <div className="empty-icon">📅</div>
              <p>Configure your devices and hit <strong>Optimize Schedule</strong> to see the cheapest run times.</p>
            </div>
          )}
        </section>
      </div>
    </>
  )
}

export default function App() {
  const [useLive, setUseLive] = useState(true)

  return (
    <div className="app">
      <header className="app-header">
        <div className="header-inner">
          <div className="logo">
            <span className="logo-icon">⚡</span>
            <div>
              <div className="logo-title">GridOptima</div>
              <div className="logo-sub">ISO New England · Cost Minimizer</div>
            </div>
          </div>
          <nav className="header-nav">
            <NavLink to="/" end className={({ isActive }) => isActive ? "nav-link nav-active" : "nav-link"}>
              Optimizer
            </NavLink>
            <NavLink to="/history" className={({ isActive }) => isActive ? "nav-link nav-active" : "nav-link"}>
              Price History
            </NavLink>
          </nav>
          <div className="header-right">
            <label className="toggle-label">
              <input
                type="checkbox"
                checked={useLive}
                onChange={(e) => setUseLive(e.target.checked)}
              />
              Live prices
            </label>
            <div className="header-badge">Phase 4 · History</div>
          </div>
        </div>
      </header>

      <main className="app-main">
        <Routes>
          <Route path="/" element={<OptimizerPage useLive={useLive} />} />
          <Route path="/history" element={<HistoryPage />} />
        </Routes>
      </main>

      <footer className="app-footer">
        GridOptima · ISO New England day-ahead LMP · Load-aware greedy optimizer
      </footer>
    </div>
  )
}