import React, { useEffect, useState } from 'react'
import { api } from '../api'

function Eps({ eps }) {
  if (!eps) return null
  const list = Array.isArray(eps) ? eps : [eps]
  return (
    <span className="small muted">
      {' '}
      {list.map((e, i) => (
        <span key={e.id + i}>{i ? ', ' : ''}<a href={e.url} target="_blank" rel="noreferrer" title={e.title}>{e.date || e.id}</a></span>
      ))}
    </span>
  )
}

export default function StancePanel() {
  const [d, setD] = useState(null)
  const [err, setErr] = useState(null)
  useEffect(() => { api('/stance').then(setD).catch((e) => setErr(String(e))) }, [])
  if (err) return <div className="small bad">{err}</div>
  if (!d) return <div className="empty muted">loading…</div>
  if (!d.latest || !d.latest.headline) return <div className="empty muted">No stance summary configured (config/stance.yaml).</div>
  const L = d.latest
  return (
    <div className="stance">
      <p className="small muted">
        Curated summary as of {d.as_of} · {d.source}. Paraphrases of auto-transcribed speech, each linked to its episode;
        not quotes and not buy/sell signals.
      </p>
      <h3>Latest stance <Eps eps={L.episode} /></h3>
      <div className="note"><b>{L.headline}</b></div>
      <ul>{L.points.map((p, i) => <li key={i}>{p.text}<Eps eps={p.episode} /></li>)}</ul>
      <h3>What would change his mind / risks he names</h3>
      <ul>{L.would_change_mind.map((p, i) => <li key={i}>{p.text}<Eps eps={p.episode} /></li>)}</ul>
      <h3>Levels he has cited</h3>
      <table>
        <thead><tr><th>Indicator</th><th>What he said</th><th>Episodes</th></tr></thead>
        <tbody>
          {d.key_levels.map((k, i) => (
            <tr key={i}><td><code>{k.metric}</code></td><td>{k.text}</td><td><Eps eps={k.episodes} /></td></tr>
          ))}
        </tbody>
      </table>
      <h3>Timeline of calls</h3>
      <table>
        <thead><tr><th>Period</th><th>Stance</th><th>Episodes</th></tr></thead>
        <tbody>
          {[...d.timeline].reverse().map((t, i) => (
            <tr key={i}><td className="nowrap">{t.period}</td><td>{t.stance}</td><td><Eps eps={t.episodes} /></td></tr>
          ))}
        </tbody>
      </table>
      <h3>Framework: what he watches</h3>
      <ul>{d.framework.map((f, i) => <li key={i}><span className="badge muted">{f.topic} {f.topic_name}</span> {f.text}</li>)}</ul>
      <div className="small muted">{d.disclaimer}</div>
    </div>
  )
}
