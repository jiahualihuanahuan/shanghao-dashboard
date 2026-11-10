import React, { useEffect, useState } from 'react'
import { api } from '../api'

export default function ViewSnippets({ indicator, limit = 4 }) {
  const [d, setD] = useState(null)
  const [err, setErr] = useState(null)
  useEffect(() => {
    let alive = true
    api(`/view/${indicator}?limit=${limit}`).then((x) => alive && setD(x)).catch((e) => alive && setErr(String(e)))
    return () => { alive = false }
  }, [indicator, limit])
  if (err) return <div className="small bad">{err}</div>
  if (!d) return <div className="small muted">loading…</div>
  return (
    <div className="snips">
      <div className="small muted">
        Shanghao view · {d.title} · {d.transcripts.transcribed}/{d.transcripts.total} episodes transcribed
      </div>
      {d.snippets.length === 0 && <div className="small muted">No matching transcript passages yet (new transcripts are indexed automatically).</div>}
      {d.snippets.map((s, i) => (
        <div className="snip" key={i}>
          <div className="small">
            <a href={s.url} target="_blank" rel="noreferrer">{s.date}</a> · {s.title}
            <span className="badge muted" title={d.disclaimer}>auto-transcribed (ASR)</span>
          </div>
          <div className="snip-text">{s.text}</div>
        </div>
      ))}
      <div className="small muted">{d.disclaimer}</div>
    </div>
  )
}
