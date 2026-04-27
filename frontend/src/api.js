const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export async function fetchPrices() {
  const res = await fetch(`${BASE_URL}/prices`);
  if (!res.ok) throw new Error("Failed to fetch prices");
  return res.json();
}

export async function runOptimize(devices) {
  const res = await fetch(`${BASE_URL}/optimize`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ devices, use_mock_prices: true }),
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || "Optimization failed");
  }
  return res.json();
}