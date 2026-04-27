import { useState } from "react";

const PRESETS = [
  { name: "EV Charger", energy_kwh: 40, duration_hours: 8, earliest_start: 0, latest_end: 8 },
  { name: "Dishwasher", energy_kwh: 1.5, duration_hours: 2, earliest_start: 19, latest_end: 24 },
  { name: "Washing Machine", energy_kwh: 2.0, duration_hours: 1, earliest_start: 0, latest_end: 8 },
  { name: "Dryer", energy_kwh: 5.0, duration_hours: 1, earliest_start: 6, latest_end: 22 },
];

function toHHMM(hour) {
  const h = hour === 24 ? 0 : hour;
  return `${String(h).padStart(2, "0")}:00${hour === 24 ? " (+1)" : ""}`;
}

export default function DeviceForm({ onSubmit, loading }) {
  const [devices, setDevices] = useState([{ ...PRESETS[0] }]);

  function addPreset(preset) {
    setDevices((d) => [...d, { ...preset }]);
  }

  function removeDevice(i) {
    setDevices((d) => d.filter((_, idx) => idx !== i));
  }

  function updateDevice(i, field, value) {
    setDevices((d) =>
      d.map((dev, idx) =>
        idx === i ? { ...dev, [field]: field === "name" ? value : Number(value) } : dev
      )
    );
  }

  function handleSubmit(e) {
    e.preventDefault();
    onSubmit(devices);
  }

  return (
    <form className="device-form" onSubmit={handleSubmit}>
      <div className="device-list">
        {devices.map((dev, i) => (
          <div key={i} className="device-card">
            <div className="device-card-header">
              <input
                className="device-name-input"
                value={dev.name}
                onChange={(e) => updateDevice(i, "name", e.target.value)}
                placeholder="Device name"
                required
              />
              <button
                type="button"
                className="remove-btn"
                onClick={() => removeDevice(i)}
                disabled={devices.length === 1}
              >
                ✕
              </button>
            </div>
            <div className="device-fields">
              <label>
                Energy needed
                <div className="input-unit">
                  <input
                    type="number"
                    min="0.1"
                    step="0.1"
                    value={dev.energy_kwh}
                    onChange={(e) => updateDevice(i, "energy_kwh", e.target.value)}
                    required
                  />
                  <span>kWh</span>
                </div>
              </label>
              <label>
                Must run for
                <div className="input-unit">
                  <input
                    type="number"
                    min="1"
                    max="24"
                    value={dev.duration_hours}
                    onChange={(e) => updateDevice(i, "duration_hours", e.target.value)}
                    required
                  />
                  <span>hrs</span>
                </div>
              </label>
              <label>
                Earliest start
                <div className="input-unit">
                  <input
                    type="number"
                    min="0"
                    max="23"
                    value={dev.earliest_start}
                    onChange={(e) => updateDevice(i, "earliest_start", e.target.value)}
                    required
                  />
                  <span>hr (0–23)</span>
                </div>
              </label>
              <label>
                Must finish by
                <div className="input-unit">
                  <input
                    type="number"
                    min="1"
                    max="24"
                    value={dev.latest_end}
                    onChange={(e) => updateDevice(i, "latest_end", e.target.value)}
                    required
                  />
                  <span>hr (1–24)</span>
                </div>
              </label>
            </div>
            <div className="device-window-hint">
              Window: {toHHMM(dev.earliest_start)} → {toHHMM(dev.latest_end)}
            </div>
          </div>
        ))}
      </div>

      <div className="preset-row">
        <span className="preset-label">Add preset:</span>
        {PRESETS.map((p) => (
          <button
            key={p.name}
            type="button"
            className="preset-btn"
            onClick={() => addPreset(p)}
          >
            + {p.name}
          </button>
        ))}
      </div>

      <button type="submit" className="optimize-btn" disabled={loading}>
        {loading ? "Optimizing…" : "Optimize Schedule"}
      </button>
    </form>
  );
}