import React, { useEffect, useState } from 'react'
import { api, fmt } from '../api'
import Chart from './Chart'
import { StaleBadge } from './Badges'
import ViewSnippets from './ViewSnippets'

export default function ChartCard({ chart, tick }) {
  const [data, setData] = useState(null)
  const [showView, setShowView] = useState(false)
  const l = chart.latest
  const unavailable = chart.members.every((m) => !m.available)

  useEffect(() => {
    if (unavailable) { setData(null); return }
    let alive = true
    const q = `/series?ids=${chart.series.join(',')}&days=${chart.days}` + (chart.transform ? `&transform=${chart.transform}` : '')
    api(q).then((x) => alive && setData(x)).catch(() => alive && setData(null))
    return () => { alive = false }
  }, [chart.id, unavailable, tick])

  const up = l.change > 0
  return (
    <div className="card">
      <div className="card-head">
        <div>
          <div className="card-title">{chart.title}</div>
          <div className="card-sub small muted">{l.source}</div>
        </div>
        <StaleBadge info={l} />
      </div>
      {l.available && chart.series.length === 1 && !chart.transform && (
        <div className="big">
          {fmt(l.value, l.decimals)} <span className="unit">{l.unit}</span>
          {l.change !== null && (
            <span className={'chg ' + (up ? 'up' : 'down')}>{up ? '▲' : '▼'} {fmt(Math.abs(l.change), l.decimals)}</span>
          )}
        </div>
      )}
      {unavailable ? (
        <div className="empty">{l.reason || 'no data'}</div>
      ) : data ? (
        <Chart series={data} kind={chart.kind} unit={chart.unit} />
      ) : (
        <div className="empty muted">loading…</div>
      )}
      {chart.note && <div className="small muted note">{chart.note}</div>}
      {chart.indicator && (
        <button className="link" onClick={() => setShowView((v) => !v)}>
          {showView ? 'Hide' : 'Show'} what he said
        </button>
      )}
      {showView && <ViewSnippets indicator={chart.indicator} />}
    </div>
  )
}
