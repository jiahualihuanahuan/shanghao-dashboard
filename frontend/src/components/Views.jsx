import React, { useEffect, useState } from 'react'
import { api, fmt } from '../api'
import { BasisChip, SourceBadge, StaleBadge } from './Badges'
import ViewSnippets from './ViewSnippets'

export function Overview({ ov, alerts }) {
  if (!ov) return <div className="empty muted">loading…</div>
  return (
    <div>
      <div className="tiles">
        {ov.tiles.map((t) => (
          <div className="tile" key={t.id}>
            <div className="small muted">{t.label.replace(/\s*\[.*?\]\s*/g, '')}</div>
            <div className="big">
              {t.available ? fmt(t.value, t.decimals) : '—'} <span className="unit">{t.unit}</span>
            </div>
            <div className="small">
              {t.available && t.change_pct !== null && (
                <span className={'chg ' + (t.change > 0 ? 'up' : 'down')}>{t.change > 0 ? '▲' : '▼'} {Math.abs(t.change_pct).toFixed(2)}%</span>
              )}{' '}
              <StaleBadge info={t} />
            </div>
          </div>
        ))}
      </div>
      <h3>Triggered alerts</h3>
      {alerts && alerts.triggered_count === 0 && <div className="small muted">None right now. ({alerts.results.length} rules checked {alerts.evaluated_at})</div>}
      {alerts && alerts.results.filter((r) => r.triggered).map((r) => <AlertRow key={r.id} r={r} />)}
      <h3>Data sources</h3>
      <SourcesTable rows={ov.sources} />
    </div>
  )
}

function AlertRow({ r }) {
  return (
    <div className={'alert ' + r.severity}>
      <div><b>{r.id}</b> <BasisChip basis={r.basis} /> {r.stale && <span className="badge warn">stale data</span>} {r.in_cooldown && <span className="badge muted">reported earlier</span>}</div>
      <div>{r.message}</div>
      <div className="small muted">as of {r.as_of} · {r.source}</div>
    </div>
  )
}

export function AlertsPanel({ alerts, history }) {
  if (!alerts) return <div className="empty muted">loading…</div>
  return (
    <div>
      <p className="small muted">{alerts.note} Rules live in <code>config/alerts.yaml</code>; JSON at <code>/api/alerts</code>.</p>
      <h3>Rules ({alerts.results.length})</h3>
      <table>
        <thead><tr><th>Status</th><th>Rule</th><th>Metric</th><th>Value</th><th>Condition</th><th>Basis</th><th>As of</th></tr></thead>
        <tbody>
          {alerts.results.map((r) => (
            <tr key={r.id} className={r.triggered ? 'row-trig' : ''}>
              <td>{r.status}{r.stale ? ' (stale)' : ''}</td>
              <td>{r.id}</td>
              <td>{r.metric}{r.kind !== 'level' ? ` (${r.kind}, ${r.window_days}d)` : ''}</td>
              <td>{r.value ?? '—'}{r.reason ? <span className="small muted"> {r.reason}</span> : null}</td>
              <td>{r.op} {r.threshold}</td>
              <td><BasisChip basis={r.basis} /></td>
              <td>{r.as_of || '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <h3>Alert history</h3>
      {history.length === 0 && <div className="small muted">No alerts have fired since this database was created.</div>}
      <table>
        <thead><tr><th>Fired (UTC)</th><th>Rule</th><th>Value</th><th>Message</th><th>Basis</th></tr></thead>
        <tbody>
          {history.map((h) => (
            <tr key={h.id}><td>{h.fired_at.replace('T', ' ').slice(0, 19)}</td><td>{h.alert_id}</td><td>{h.value}</td><td>{h.message}{h.stale ? ' (stale data)' : ''}</td><td><BasisChip basis={h.basis} /></td></tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function SourcesTable({ rows }) {
  return (
    <table>
      <thead><tr><th>Source</th><th>Status</th><th>Last OK</th><th>Every</th><th>Notes</th></tr></thead>
      <tbody>
        {rows.map((s) => (
          <tr key={s.group}>
            <td>{s.label}</td>
            <td><SourceBadge s={s} /></td>
            <td>{s.last_ok ? `${s.age_min} min ago` : '—'}</td>
            <td>{s.interval_min} min</td>
            <td className="small">{s.state === 'needs_key' ? `add ${s.needs} to .env` : s.error || s.partial || ''}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

export function ViewPanel() {
  const [list, setList] = useState([])
  const [sel, setSel] = useState(null)
  useEffect(() => { api('/view').then((x) => { setList(x); if (x[0]) setSel(x[0].key) }) }, [])
  const topics = [...new Set(list.map((i) => i.topic))]
  return (
    <div className="viewgrid">
      <div className="viewlist">
        {topics.map((t) => (
          <div key={t}>
            <div className="small muted topic">{t} · {list.find((i) => i.topic === t).topic_name}</div>
            {list.filter((i) => i.topic === t).map((i) => (
              <button key={i.key} className={'pick ' + (sel === i.key ? 'on' : '')} onClick={() => setSel(i.key)}>
                {i.title} <span className="small muted">({i.episodes_matched} ep.)</span>
              </button>
            ))}
          </div>
        ))}
      </div>
      <div className="viewbody">{sel && <ViewSnippets key={sel} indicator={sel} limit={12} />}</div>
    </div>
  )
}

export function NotesFeed() {
  const [notes, setNotes] = useState([])
  useEffect(() => { api('/notes').then(setNotes) }, [])
  return (
    <div>
      <p className="small muted">
        Topics with no free live data (politics, AI financing, supply chain…). Newest episode first. Paraphrases of what he said,
        labelled by basis; not recommendations.
      </p>
      {notes.map((n, i) => (
        <div className="note" key={i}>
          <div className="small"><b>{n.date}</b> · <span className="badge muted">{n.topic} {n.topic_name}</span>{' '}
            <a href={n.url} target="_blank" rel="noreferrer">{n.title}</a>{' '}
            <span className={'badge ' + (n.basis === 'own ASR' ? 'heur' : 'muted')}>{n.basis}</span></div>
          <div>{n.text}</div>
        </div>
      ))}
    </div>
  )
}
