const base = import.meta.env.VITE_API_BASE || ''

export async function api(path, opts) {
  const r = await fetch(`${base}/api${path}`, opts)
  if (!r.ok) throw new Error(`${r.status} ${path}`)
  return r.json()
}

export function fmt(v, dec = 2) {
  if (v === null || v === undefined || Number.isNaN(v)) return '—'
  const abs = Math.abs(v)
  if (abs >= 1e6) return (v / 1e6).toFixed(2) + 'M'
  return Number(v).toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: dec })
}
