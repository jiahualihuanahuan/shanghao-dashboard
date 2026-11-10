import React, { useCallback, useEffect, useState } from 'react'
import { api } from './api'
import ChartCard from './components/ChartCard'
import { AlertsPanel, NotesFeed, Overview, SourcesTable, ViewPanel } from './components/Views'

const REFRESH_MS = 60_000

export default function App() {
  const [tab, setTab0] = useState(window.location.hash.slice(1) || 'overview')
  const setTab = (t) => { window.location.hash = t; setTab0(t) }
  const [ov, setOv] = useState(null)
  const [panels, setPanels] = useState([])
  const [alerts, setAlerts] = useState(null)
  const [history, setHistory] = useState([])
  const [tick, setTick] = useState(0)
  const [health, setHealth] = useState(null)
  const [error, setError] = useState(null)

  const load = useCallback(async () => {
    try {
      const [o, p, a, h, hl] = await Promise.all([
        api('/overview'), api('/panels'), api('/alerts'), api('/alerts/history?limit=100'), api('/health'),
      ])
      setOv(o); setPanels(p); setAlerts(a); setHistory(h); setHealth(hl); setError(null); setTick((t) => t + 1)
    } catch (e) { setError(String(e)) }
  }, [])

  useEffect(() => { load(); const t = setInterval(load, REFRESH_MS); return () => clearInterval(t) }, [load])

  const tabs = [
    { id: 'overview', title: 'Overview' },
    ...panels.map((p) => ({ id: p.id, title: p.title })),
    { id: 'view', title: 'Shanghao view' },
    { id: 'notes', title: 'Notes feed' },
    { id: 'alerts', title: `Alerts${alerts && alerts.triggered_count ? ` (${alerts.triggered_count})` : ''}` },
    { id: 'sources', title: 'Sources' },
  ]
  const panel = panels.find((p) => p.id === tab)

  return (
    <div className="app">
      <header>
        <div>
          <h1>Shanghao dashboard</h1>
          <div className="small muted">
            Indicators from the topics covered in @shanghaojin's weekly market overviews · public data only · not investment advice
          </div>
        </div>
        <div className="chips">
          {health && <span className="badge muted" title="Episodes transcribed / total">transcripts {health.transcripts.transcribed}/{health.transcripts.total}</span>}
          {health && <span className={'badge ' + (health.fred_key ? 'ok' : 'warn')}>{health.fred_key ? 'FRED key set' : 'add FRED key'}</span>}
          {alerts && <span className={'badge ' + (alerts.triggered_count ? 'bad' : 'ok')}>{alerts.triggered_count} alerts</span>}
          {error && <span className="badge bad">API: {error}</span>}
        </div>
      </header>
      <nav>
        {tabs.map((t) => (
          <button key={t.id} className={tab === t.id ? 'on' : ''} onClick={() => setTab(t.id)}>{t.title}</button>
        ))}
      </nav>
      <main>
        {tab === 'overview' && <Overview ov={ov} alerts={alerts} />}
        {panel && (
          <div>
            <div className="small muted topic">{panel.topic} · {panel.topic_name}</div>
            <div className="grid">{panel.charts.map((c) => <ChartCard key={c.id} chart={c} tick={tick} />)}</div>
          </div>
        )}
        {tab === 'view' && <ViewPanel />}
        {tab === 'notes' && <NotesFeed />}
        {tab === 'alerts' && <AlertsPanel alerts={alerts} history={history} />}
        {tab === 'sources' && ov && <SourcesTable rows={ov.sources} />}
      </main>
      <footer className="small muted">
        Yahoo Finance data is unofficial and may break; GEX is an estimate; transcript snippets are auto-transcribed and may contain errors.
        Nothing here is a buy/sell signal.
      </footer>
    </div>
  )
}
