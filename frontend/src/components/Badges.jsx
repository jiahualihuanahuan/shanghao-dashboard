import React from 'react'

export function StaleBadge({ info }) {
  if (!info) return null
  if (!info.available) return <span className="badge muted">no data</span>
  if (info.stale) return <span className="badge warn" title="Latest observation is older than expected">stale · {info.as_of}</span>
  return <span className="badge ok" title="Latest observation date">{info.as_of}</span>
}

export function BasisChip({ basis }) {
  const his = (basis || '').toLowerCase().startsWith('his stated')
  return <span className={'badge ' + (his ? 'his' : 'heur')}>{his ? 'his stated level' : 'heuristic'}</span>
}

export function SourceBadge({ s }) {
  const cls = s.state === 'ok' ? 'ok' : s.state === 'partial' ? 'warn' : s.state === 'needs_key' ? 'muted' : s.state === 'pending' ? 'muted' : 'bad'
  const label = s.state === 'needs_key' ? 'needs key' : s.state
  return <span className={'badge ' + cls}>{label}{s.stale ? ' · stale' : ''}</span>
}
