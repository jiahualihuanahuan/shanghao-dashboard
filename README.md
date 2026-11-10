# Shanghao dashboard

A self-hosted, real-time-ish market dashboard that turns the topics covered in the weekly Chinese-language market
overviews of YouTube channel **@shanghaojin** into live indicators with free public data. Each indicator links to
what he said about it (from the video transcripts), newest episode first.

> **Not investment advice.** The dashboard shows indicators and what a commentator said. It never produces buy/sell
> signals. Transcript snippets are *auto-transcribed speech* and can contain errors.

```
docker compose up -d        # then open http://localhost:8080
```

## Quick start

```bash
cp .env.example .env        # optional: add FRED_API_KEY (free), set TRANSCRIPTS_HOST_PATH
docker compose up -d
```

* UI: <http://localhost:8080> (`WEB_PORT`, `BIND_ADDR` in `.env`; there is **no login** - keep `BIND_ADDR=127.0.0.1` unless
  you are on a trusted network).
* JSON endpoints: `/api/health`, `/api/panels`, `/api/alerts`, `/api/alerts/history`, `/api/view/<indicator>`, `/api/notes`, `/api/sources`.
* Without a `FRED_API_KEY` the FRED panels (credit spreads, jobs, CPI, Fed balance sheet) show **"add FRED key"**; every
  other panel works. Get a free key at <https://fred.stlouisfed.org/docs/api/api_key.html>. Nothing is registered for you.

## What is in it

| Tab | Topic | Main indicators |
|---|---|---|
| Liquidity & rates | T1 | US 10Y/30Y (live + Treasury), 10Y-2Y, MOVE (rate-vol proxy), SOFR + p99 spread, TGA, Fed assets / RRP / NFCI (FRED) |
| Credit & funding | T2 | HY / CCC / IG OAS (FRED), dollar index, CoreWeave as an AI-credit proxy |
| Fed & labor | T3 | Fed funds, unemployment, payroll change, wages, CPI / core CPI YoY (all FRED) |
| Positioning, flows & valuation | T4/T5 | VIX, VIX3M, term-structure ratio, SKEW, SPX gamma *estimate*, put/call OI, S&P drawdown, CFTC leveraged-fund / asset-manager positions, forward P/E (manual) |
| AI & semiconductors | T6 | Semis basket, hyperscalers, software vs semis (rebased), capex figures (manual) |
| Tariffs, energy, Japan & crypto | T7-T10 | Brent, ULSD-Brent crack, nat gas, USD/JPY, Nikkei, Japan 10Y, yen COT, Bitcoin, USD/CNY |
| Shanghao view | all | Per indicator: his latest dated statements with `youtu.be/<id>?t=<sec>` links |
| Notes feed | non-data topics | Politics, AI financing, power/supply chain, Intel foundry... newest first, each labelled by basis |
| Alerts | - | Current rule status, thresholds, history |
| Sources | - | Per-source status, age, errors |

Every card shows a **stale badge** (latest observation older than expected) and its source. Data panels poll every 60 s;
the backend refreshes each source on its own cadence.

## Data sources (all free, public)

| Source | Used for | Key? | Backend refresh |
|---|---|---|---|
| Yahoo Finance chart endpoint (**unofficial**, can break/rate-limit) | indices, yields, FX, futures, stocks, BTC | no | 10 min |
| Cboe CSV (`cdn.cboe.com`) | VIX/VIX3M official closes, SKEW | no | 3 h |
| Cboe delayed SPX option chain | gamma exposure *estimate*, put/call OI | no | 20 min |
| US Treasury yield-curve XML | 3M-30Y par yields | no | 1 h |
| FiscalData (Daily Treasury Statement) | TGA balance | no | 6 h |
| NY Fed markets API | SOFR + percentiles | no | 1 h |
| CFTC TFF weekly file | leveraged funds / asset managers net (ES, NQ, UST10Y, JPY, BTC) | no | 6 h (weekly data) |
| Frankfurter (ECB reference) | USD/JPY, CNY, CAD, EUR | no | 6 h |
| CoinGecko | Bitcoin | no | 10 min |
| FRED API | spreads, labour, CPI, Fed balance sheet, Japan 10Y | **free key** | 3 h |

Things he discusses that have **no free live source** (shown as notes / manual inputs instead): swaption and 6m10y
swap vol, CDS, CTA dollar flows, prime-broker positioning, Fed-funds-futures hike pricing (CME FedWatch), forward P/E,
DRAM spot prices, power-queue statistics, hyperscaler capex guidance. Use `config/manual_inputs.yaml` for numbers you
want on the dashboard.

**Gamma estimate caveat:** `net_gex` assumes dealers are long calls / short puts and sums gamma x open interest for
options expiring within 45 days. It is a rough indicator, not a measurement of dealer positioning.

## The "Shanghao view" and transcripts

The backend reads `<video_id>.txt` files (lines `[seconds] text`) from the folder mounted at `/data/transcripts`
(read-only; set `TRANSCRIPTS_HOST_PATH`). **A fresh clone has no transcripts, so the Shanghao view stays empty until you point `TRANSCRIPTS_HOST_PATH` at a folder of `<video_id>.txt` files** (they are not in this repo). It rescans every `TRANSCRIPT_SCAN_MINUTES` (default 5) by modification time, so
transcripts that arrive later appear without a restart. The header chip shows `transcripts x/90`.

* `config/videos.csv` maps video id -> real upload date and title (titles contain typos, e.g. "2026年12月30日" was
  uploaded 2025-12-30). Add rows for new episodes.
* `config/indicators.yaml` lists, per indicator, the keyword regexes used to find relevant passages, including common
  ASR mis-hearings ("compressorly" for convexity). Edit and `POST /api/alerts/reload` (or restart).
* Results are ordered **newest episode first**, at most 2 passages per episode, labelled *auto-transcribed (ASR)*.
* The repository does **not** contain transcripts, audio or database files (`.gitignore`). `tools/transcribe.py`
  (optional, needs `faster-whisper` + ffmpeg) produces the expected format from audio; YouTube captions do not exist
  for this channel, so a local ASR pass is the only source.

## Alerts

`config/alerts.yaml` defines threshold rules (`kind`: `level`, `change_abs`, `change_pct`; `window_days` for changes;
`basis`: **"his stated level"** vs **"heuristic"**; per-rule `cooldown_hours`; `enabled: false` to disable).

* App: evaluated after every refresh. `GET /api/alerts` (all rules + current status), `GET /api/alerts/history`,
  `POST /api/alerts/reload`. The *Alerts* tab shows rule status and history. A rule re-alerts only after its cooldown.
* **Standalone script** (Python standard library only, public data only, same adapters and evaluator; written for 3.9+, verified on 3.13 only):

  ```bash
  python3 tools/check_alerts.py --state ~/.shanghao_alerts_state.json      # prints JSON
  FRED_API_KEY=... python3 tools/check_alerts.py --all                      # include FRED rules and every rule's status
  ```

  Output keys: `triggered` (new alerts, each with `id, metric, value, threshold, as_of, source, stale, message, basis,
  severity`), `ongoing` (still breached, within cooldown), `unavailable`, `source_errors`, `sources_without_key`.
  `--state` makes a scheduled run report each breach once per cooldown instead of every run.
* Default thresholds and their basis are listed in `config/alerts.yaml` (comments explain each).

## Layout

```
backend/app        FastAPI app, APScheduler jobs, SQLite, adapters (sources/), derived series, alert evaluator
config/            alerts.yaml, indicators.yaml, notes.yaml, manual_inputs.yaml, videos.csv   (bind-mounted, editable)
frontend/          React + Vite + ECharts, served by nginx in Docker (nginx proxies /api to the backend)
tools/             check_alerts.py (standalone), transcribe.py (optional)
```

## Develop and test

```bash
python3 -m venv .venv && .venv/bin/pip install -r backend/requirements-dev.txt
cd backend && ../.venv/bin/python -m pytest -q          # offline tests, recorded fixtures, no network
CONFIG_DIR=../config DATA_DIR=/tmp/shdata TRANSCRIPTS_DIR=../transcripts ../.venv/bin/uvicorn app.main:app --port 8000
cd ../frontend && npm install && npm run dev            # http://localhost:5173 (proxies /api to :8000)
```

Environment: `CONFIG_DIR`, `DATA_DIR`, `TRANSCRIPTS_DIR`, `FRED_API_KEY`, `SCHEDULER=0` (disable background jobs),
`GROUPS=yahoo,cboe_vol` (limit sources), `REFRESH_SCALE`, `YAHOO_PAUSE_S`.

## Known limits

* Yahoo's endpoint is undocumented; if it breaks, the affected cards go stale and the Sources tab shows the error.
* Free sources are delayed (typically 15 min) or end-of-day; this is not a trading terminal.
* Transcripts are machine-generated: English finance terms are often garbled, so keyword matching misses some passages.
* No authentication. Do not expose it to the internet.
