import { useState, useEffect } from "react"
import { fetchZones } from "./api"

export default function ZoneSelector({ value, onChange }) {
  const [zones, setZones] = useState([])

  useEffect(() => {
    fetchZones().then(data => setZones(data.zones)).catch(() => {})
  }, [])

  if (zones.length === 0) return null

  return (
    <div className="zone-selector">
      <label className="zone-label" htmlFor="zone-select">Zone</label>
      <select
        id="zone-select"
        className="zone-select"
        value={value}
        onChange={e => onChange(e.target.value)}
      >
        {zones.map(z => (
          <option key={z.node} value={z.node}>{z.name}</option>
        ))}
      </select>
    </div>
  )
}