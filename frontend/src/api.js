const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000"

export async function fetchZones() {
  const res = await fetch(`${BASE_URL}/zones`)
  if (!res.ok) throw new Error("Failed to fetch zones")
  return res.json()
}

export async function fetchPrices(live = true, node = ".Z.NEMASSBOST") {
  const res = await fetch(`${BASE_URL}/prices?live=${live}&node=${encodeURIComponent(node)}`)
  if (!res.ok) throw new Error("Failed to fetch prices")
  return res.json()
}

export async function fetchPriceHistory(days = 7, node = ".Z.NEMASSBOST") {
  const res = await fetch(`${BASE_URL}/prices/history?days=${days}&node=${encodeURIComponent(node)}`)
  if (!res.ok) throw new Error("Failed to fetch price history")
  return res.json()
}

export async function runOptimize(devices, useLivePrices = true, maxLoadKw = 10, node = ".Z.NEMASSBOST") {
  const res = await fetch(`${BASE_URL}/optimize`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      devices,
      use_live_prices: useLivePrices,
      max_load_kw: maxLoadKw,
      node,
    }),
  })
  if (!res.ok) {
    const err = await res.json()
    throw new Error(err.detail || "Optimization failed")
  }
  return res.json()
}