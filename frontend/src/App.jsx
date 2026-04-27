import { useState, useEffect } from "react";
import { fetchPrices, runOptimize } from "./api";
import PriceChart from "./PriceChart";
import DeviceForm from "./DeviceForm";
import ScheduleResults from "./ScheduleResults";
import "./App.css";

export default function App() {
  const [prices, setPrices] = useState([]);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [priceError, setPriceError] = useState(null);

  useEffect(() => {
    fetchPrices()
      .then((data) => setPrices(data.prices))
      .catch(() => setPriceError("Could not load prices — is the backend running?"));
  }, []);

  async function handleOptimize(devices) {
    setLoading(true);
    setError(null);
    try {
      const data = await runOptimize(devices);
      setResult(data);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

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
          <div className="header-badge">Phase 1 · Mock Prices</div>
        </div>
      </header>

      <main className="app-main">
        <section className="section">
          <h2 className="section-title">Today's Electricity Prices</h2>
          <p className="section-desc">
            Hourly spot prices (¢/kWh) — highlighted bars show where your devices will be scheduled.
          </p>
          {priceError ? (
            <div className="error-box">{priceError}</div>
          ) : (
            <PriceChart prices={prices} schedule={result?.schedule} />
          )}
        </section>

        <div className="two-col">
          <section className="section">
            <h2 className="section-title">Your Devices</h2>
            <p className="section-desc">
              Enter each device's energy need and the window it's allowed to run in.
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
      </main>

      <footer className="app-footer">
        GridOptima · Phase 1 skeleton · ISO New England region · Greedy optimizer
      </footer>
    </div>
  );
}