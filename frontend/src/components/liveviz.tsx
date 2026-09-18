import { AnimatePresence, motion } from 'framer-motion'
import { useEffect, useMemo, useRef, useState } from 'react'
import { rampStops, useTheme } from '../lib/theme'
import { FIELD_LABEL, lightTimeMs, type AmMetrics, type Census, type DecodeEv, type LayoutPos, type LiveState, type ReceiverEv, type RowListener, type Runs, type StationInfo, type SymbolEv } from '../lib/live'
import { Icon } from './ui'

/** 256-entry colour table from the theme's spectrum ramp (quiet = page background). */
function buildLut() {
  const ramp = rampStops('spec')
  const out = new Uint8ClampedArray(256 * 3)
  for (let v = 0; v < 256; v++) {
    const p = (v / 255) * (ramp.length - 1)
    const i = Math.min(ramp.length - 2, Math.floor(p))
    const f = p - i
    for (let c = 0; c < 3; c++) out[v * 3 + c] = ramp[i][c] + (ramp[i + 1][c] - ramp[i][c]) * f
  }
  return out
}

export interface FreqLabel { hz: number; text: string; tone?: string }

/** Real spectrum rows scrolling down. Rows arrive through `subscribe`; drawing never touches React state. */
export function RealWaterfall({ subscribe, height = 320, labels = [], unit = 'Hz', idle }: {
  subscribe: (fn: RowListener) => () => void; height?: number; labels?: FreqLabel[]; unit?: 'Hz' | 'kHz'; idle?: string
}) {
  const canvas = useRef<HTMLCanvasElement>(null)
  const { theme } = useTheme()
  const lut = useRef<Uint8ClampedArray | null>(null)
  const [span, setSpan] = useState<[number, number] | null>(null)
  useEffect(() => {
    lut.current = buildLut()
    const el = canvas.current
    if (el) el.getContext('2d')?.clearRect(0, 0, el.width, el.height)
  }, [theme])
  const pending = useRef<{ row: Uint8Array; f0: number; f1: number }[]>([])
  useEffect(() => subscribe((row, f0, f1) => { pending.current.push({ row, f0, f1 }) }), [subscribe])
  useEffect(() => {
    const el = canvas.current
    if (!el) return
    let raf = 0
    const rowH = 2
    const draw = () => {
      raf = requestAnimationFrame(draw)
      const rows = pending.current.splice(0)
      if (!rows.length) return
      const w = el.clientWidth, h = el.clientHeight
      if (el.width !== w || el.height !== h) { el.width = w; el.height = h }
      const ctx = el.getContext('2d')!
      const LUT = lut.current ?? (lut.current = buildLut())
      const shift = rows.length * rowH
      ctx.drawImage(el, 0, 0, w, h - shift, 0, shift, w, h - shift)
      rows.reverse().forEach((r, k) => {
        const img = ctx.createImageData(w, rowH)
        for (let x = 0; x < w; x++) {
          const v = r.row[Math.min(r.row.length - 1, Math.floor((x / w) * r.row.length))]
          for (let y = 0; y < rowH; y++) {
            const o = (y * w + x) * 4
            img.data[o] = LUT[v * 3]; img.data[o + 1] = LUT[v * 3 + 1]; img.data[o + 2] = LUT[v * 3 + 2]; img.data[o + 3] = 255
          }
        }
        ctx.putImageData(img, 0, k * rowH)
      })
      const last = rows[0]
      setSpan((s) => (s && s[0] === last.f0 && s[1] === last.f1 ? s : [last.f0, last.f1]))
    }
    raf = requestAnimationFrame(draw)
    return () => cancelAnimationFrame(raf)
  }, [])
  const fmt = (hz: number) => unit === 'kHz' ? `${(hz / 1e3).toFixed(0)}` : `${hz > 0 ? '+' : ''}${hz.toFixed(0)}`
  const pos = (hz: number) => span ? ((hz - span[0]) / (span[1] - span[0])) * 100 : 0
  return (
    <div className="wf">
      <div className="wf-canvas" style={{ height }}>
        <canvas ref={canvas} />
        {!span && <div className="wf-idle">{idle ?? 'waiting for the first spectrum row…'}</div>}
        {span && labels.filter((l) => l.hz >= span[0] && l.hz <= span[1]).map((l, i) => (
          <div key={`${l.hz}-${i}`} className="wf-label" style={{ left: `${pos(l.hz)}%`, color: l.tone ?? 'var(--cyan)' }}>
            <span style={{ top: 6 + (i % 4) * 17 }}>{l.text}</span>
          </div>
        ))}
        <div className="wf-sweep" />
      </div>
      <div className="wf-axis mono">
        {span ? [0, 0.25, 0.5, 0.75, 1].map((k) => <span key={k}>{fmt(span[0] + k * (span[1] - span[0]))}</span>) : <span>&nbsp;</span>}
        <em>{unit === 'kHz' ? 'kHz' : 'Hz from carrier'}</em>
      </div>
    </div>
  )
}

const SYMBOL_TONE: Record<string, string> = { M: 'var(--cyan)', H: 'var(--violet)', '1': 'var(--amber)', '0': 'var(--line-3)', '10': 'var(--amber)', '01': 'var(--orange)', '11': 'var(--orange)', '00': 'var(--line-3)' }

/** Sixty-second dial: each received second lands on its UTC position; markers, bits and erasures are colour-coded. */
export function MinuteDial({ symbols, positions, size = 300 }: { symbols: SymbolEv[]; positions?: LayoutPos[]; size?: number }) {
  const latest = symbols[symbols.length - 1]
  const byPos = useMemo(() => {
    const m = new Map<number, SymbolEv>()
    const cut = latest?.utc_second != null ? latest.utc_second - 59 : -Infinity
    for (const s of symbols) if (s.utc_second != null && s.utc_second >= cut) m.set(((s.utc_second % 60) + 60) % 60, s)
    return m
  }, [symbols, latest])
  const [hover, setHover] = useState<number | null>(null)
  const r0 = size / 2 - 34, r1 = size / 2 - 8, c = size / 2
  const seg = (i: number, rin: number, rout: number) => {
    const a0 = ((i - 0.44) / 60) * Math.PI * 2 - Math.PI / 2, a1 = ((i + 0.44) / 60) * Math.PI * 2 - Math.PI / 2
    const p = (r: number, a: number) => `${c + r * Math.cos(a)},${c + r * Math.sin(a)}`
    return `M${p(rin, a0)} L${p(rout, a0)} A${rout},${rout} 0 0 1 ${p(rout, a1)} L${p(rin, a1)} A${rin},${rin} 0 0 0 ${p(rin, a0)} Z`
  }
  const cur = latest?.utc_second != null ? ((latest.utc_second % 60) + 60) % 60 : null
  const focus = hover ?? cur
  const focusPos = focus != null ? positions?.[focus] : undefined
  const focusSym = focus != null ? byPos.get(focus) : undefined
  return (
    <svg viewBox={`0 0 ${size} ${size}`} className="dial" style={{ width: '100%', maxWidth: size }}>
      {Array.from({ length: 60 }, (_, i) => {
        const s = byPos.get(i)
        const kind = positions?.[i]?.kind
        const fill = s ? (s.symbol ? SYMBOL_TONE[s.symbol] ?? 'var(--line-3)' : 'transparent') : 'var(--panel-3)'
        return (
          <g key={i} onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)}>
            <path d={seg(i, r0 - 10, r0 - 4)} fill={kind === 'M' || kind === 'H' ? 'var(--cyan)' : kind === 'P' ? 'var(--violet)' : kind === 'F' ? 'var(--line-3)' : 'var(--line)'} fillOpacity={kind === 'M' || kind === 'H' || kind === 'P' ? 0.45 : 1} />
            <motion.path d={seg(i, r0, r1)} fill={fill} stroke={s && !s.symbol ? 'var(--red)' : i === cur ? 'var(--text)' : 'none'} strokeWidth={i === cur ? 1.4 : 1}
              initial={false} animate={{ opacity: s ? 0.45 + 0.55 * Math.max(0.2, s.confidence) : 1 }} transition={{ duration: 0.4 }} />
          </g>
        )
      })}
      {[0, 15, 30, 45].map((q) => {
        const a = (q / 60) * Math.PI * 2 - Math.PI / 2
        return <text key={q} x={c + (r1 + 1) * Math.cos(a) * 0.72} y={c + (r1 + 1) * Math.sin(a) * 0.72 + 4} className="dial-q">{q}</text>
      })}
      <text x={c} y={c - 18} className="dial-sec">{focus != null ? String(focus).padStart(2, '0') : '--'}</text>
      <text x={c} y={c + 6} className="dial-sym">{focusSym ? (focusSym.symbol ?? 'erased') : '—'}</text>
      <text x={c} y={c + 26} className="dial-field">{focusPos ? (focusPos.kind === 'M' ? 'position marker' : focusPos.kind === 'H' ? 'minute hole' : focusPos.kind === 'Z' ? 'always 0' : focusPos.kind === 'O' ? 'always 1' : focusPos.kind === 'P' ? `parity (${focusPos.field})` : focusPos.field ? FIELD_LABEL[focusPos.field] ?? focusPos.field : 'unused') : ''}</text>
    </svg>
  )
}

const DIGIT_TEXT: Record<string, string> = {
  year_tens: 'year tens', year_units: 'year units', day_hundreds: 'day-of-year hundreds', day_tens: 'day tens', day_units: 'day units',
  hour_tens: 'hour tens', hour_units: 'hour units', minute_tens: 'minute tens', minute_units: 'minute units', month: 'month',
}

/** Decoded time, one box per digit: established digits are solid; unresolved digits show their odds. */
export function DecodedTime({ decode, zoneNote }: { decode?: DecodeEv; zoneNote?: string }) {
  const utc = decode?.utc ? new Date(decode.utc) : null
  const d = decode?.digits ?? {}
  const pad = (n: number, w = 2) => String(n).padStart(w, '0')
  const doy = utc ? Math.floor((Date.UTC(utc.getUTCFullYear(), utc.getUTCMonth(), utc.getUTCDate()) - Date.UTC(utc.getUTCFullYear(), 0, 0)) / 864e5) : null
  const groups: { label: string; chars: { ch: string; key?: string }[] }[] = utc ? [
    { label: 'year', chars: [{ ch: '2' }, { ch: '0' }, { ch: pad(utc.getUTCFullYear() % 100)[0], key: 'year_tens' }, { ch: pad(utc.getUTCFullYear() % 100)[1], key: 'year_units' }] },
    d.month ? { label: 'month · day', chars: [{ ch: pad(utc.getUTCMonth() + 1)[0], key: 'month' }, { ch: pad(utc.getUTCMonth() + 1)[1], key: 'month' }, { ch: '·' }, { ch: pad(utc.getUTCDate())[0], key: 'day_tens' }, { ch: pad(utc.getUTCDate())[1], key: 'day_units' }] }
      : { label: 'day of year', chars: [{ ch: pad(doy ?? 0, 3)[0], key: 'day_hundreds' }, { ch: pad(doy ?? 0, 3)[1], key: 'day_tens' }, { ch: pad(doy ?? 0, 3)[2], key: 'day_units' }] },
    { label: 'UTC', chars: [{ ch: pad(utc.getUTCHours())[0], key: 'hour_tens' }, { ch: pad(utc.getUTCHours())[1], key: 'hour_units' }, { ch: ':' }, { ch: pad(utc.getUTCMinutes())[0], key: 'minute_tens' }, { ch: pad(utc.getUTCMinutes())[1], key: 'minute_units' }] },
  ] : []
  return (
    <div className="dtime">
      {!decode && <div className="dtime-wait"><span className="spinner" /> assembling the first 60-second frame…</div>}
      <div className="row-wrap" style={{ gap: 16, alignItems: 'flex-end' }}>
        {groups.map((g) => (
          <div key={g.label} className="col" style={{ gap: 4 }}>
            <div className="row" style={{ gap: 3 }}>
              {g.chars.map((c, i) => {
                const info = c.key ? d[c.key] : undefined
                const ok = !c.key || info?.established
                return (
                  <motion.span key={`${g.label}-${i}-${c.ch}-${ok}`} className={`dchar${c.key ? (ok ? ' ok' : ' pending') : ' fixed'}`}
                    initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.16 }}
                    title={info ? `${DIGIT_TEXT[c.key!] ?? c.key}: ${info.established ? 'established' : 'not established'} · margin ${info.margin_symbols ?? '—'} symbols · log10 odds ${info.log10_odds ?? '—'}` : undefined}>
                    {c.key && !ok ? '?' : c.ch}
                  </motion.span>
                )
              })}
            </div>
            <span className="dlabel">{g.label}</span>
          </div>
        ))}
      </div>
      {decode && decode.frames === 0 && <div className="dtime-wait"><span className="spinner" /> symbols are arriving; waiting for the first complete 60-second frame</div>}
      {decode && decode.frames > 0 && (
        <div className="row-wrap muted mono" style={{ gap: 14, fontSize: 11.5, marginTop: 10 }}>
          <span>{decode.frames} frame{decode.frames === 1 ? '' : 's'}</span>
          <span>{decode.mismatches ?? '—'}/{decode.observed ?? '—'} symbols disagree</span>
          <span>p = 10<sup>{decode.log10_p?.toFixed(1)}</sup></span>
          <span style={{ color: decode.established ? 'var(--green)' : 'var(--amber)' }}>{decode.established ? 'TIME ESTABLISHED' : decode.detected ? 'STRUCTURE DETECTED · DIGITS PENDING' : 'NOT YET SIGNIFICANT'}</span>
          {zoneNote && <span>{zoneNote}</span>}
        </div>
      )}
    </div>
  )
}

/** Independent check: the decoded minute vs the receiver's own timestamp, next to the light-time of the path. */
export function Verification({ decode, receiver }: { decode?: DecodeEv; receiver?: ReceiverEv }) {
  const v = decode?.verification
  const light = lightTimeMs(receiver?.distance_km)
  const gps = v?.timing === 'gps'
  return (
    <div className={`verify${v && decode?.established ? (v.agrees ? ' ok' : ' bad') : ''}`}>
      <div className="row" style={{ gap: 8 }}>
        <Icon name={v && decode?.established && v.agrees ? 'check' : 'clock'} size={16} />
        <b>Independent verification</b>
        <span className="grow" />
        <span className="mono muted" style={{ fontSize: 11 }}>{gps ? 'receiver GPS time' : receiver?.timing === 'arrival' ? 'network arrival time' : '—'}</span>
      </div>
      {v && decode?.established ? (
        <>
          <div className="verify-num mono">{v.arrival_minus_decoded_ms > 0 ? '+' : ''}{v.arrival_minus_decoded_ms.toFixed(1)} <small>ms</small></div>
          <div className="dim" style={{ fontSize: 12 }}>
            The frame the code says starts at {decode.utc?.slice(11, 16)} UTC arrived {Math.abs(v.arrival_minus_decoded_ms).toFixed(1)} ms {v.arrival_minus_decoded_ms >= 0 ? 'after' : 'before'} that instant by the receiver&apos;s {gps ? 'GPS-disciplined' : 'network'} clock.
            {light != null && gps && <> Ground distance {receiver?.distance_km} km is {light.toFixed(1)} ms of light time; sky-wave paths and receiver filters add a few ms.</>}
          </div>
        </>
      ) : <div className="dim" style={{ fontSize: 12, marginTop: 6 }}>Shown once every time digit is established. A decode that the receiver&apos;s clock contradicts would be flagged here.</div>}
    </div>
  )
}

export interface Step { key: string; label: string; detail?: string; state: 'done' | 'active' | 'pending' | 'failed' }

export function EvidenceSteps({ steps }: { steps: Step[] }) {
  return (
    <ol className="esteps">
      {steps.map((s) => (
        <motion.li key={s.key} className={`estep ${s.state}`} layout>
          <span className="estep-dot">{s.state === 'done' ? <Icon name="check" size={11} /> : s.state === 'failed' ? <Icon name="cross" size={11} /> : null}</span>
          <div className="grow">
            <div className="estep-label">{s.label}</div>
            <AnimatePresence>{s.detail && <motion.div className="estep-detail mono" initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }}>{s.detail}</motion.div>}</AnimatePresence>
          </div>
        </motion.li>
      ))}
    </ol>
  )
}

/** Characters appear at the rate a 50-baud teleprinter would print them. */
export function Teletype({ text, cps = 6.7 }: { text: string; cps?: number }) {
  const [shown, setShown] = useState(0)
  const box = useRef<HTMLPreElement>(null)
  useEffect(() => { if (text.length < shown) setShown(0) }, [text, shown])
  useEffect(() => {
    if (shown >= text.length) return
    const id = setTimeout(() => setShown((n) => Math.min(text.length, n + Math.max(1, Math.round((text.length - n) / 60)))), 1000 / cps)
    return () => clearTimeout(id)
  }, [shown, text, cps])
  useEffect(() => { box.current?.scrollTo({ top: box.current.scrollHeight }) }, [shown])
  return <pre ref={box} className="teletype">{text.slice(0, shown)}<span className="caret">▌</span></pre>
}

export function PathCard({ station, receiver }: { station: StationInfo; receiver?: ReceiverEv }) {
  const light = lightTimeMs(receiver?.distance_km)
  return (
    <div className="path">
      <div className="path-end">
        <span className="path-k">TRANSMITTER</span>
        <b>{station.name}</b>
        <span className="muted">{station.site.name}</span>
        <span className="mono muted">{station.site.lat.toFixed(2)}°, {station.site.lon.toFixed(2)}°</span>
      </div>
      <div className="path-line">
        <div className="path-wire"><span className="path-pulse" /><span className="path-pulse d2" /></div>
        <span className="mono">{receiver?.distance_km != null ? `${receiver.distance_km.toLocaleString('en-IN')} km` : '—'}{light != null ? ` · ${light.toFixed(2)} ms light time` : ''}</span>
        <span className="mono muted">{(station.frequency_khz >= 1000 ? `${(station.frequency_khz / 1000).toFixed(3)} MHz` : `${station.frequency_khz} kHz`)}</span>
      </div>
      <div className="path-end right">
        <span className="path-k">RECEIVER</span>
        <b>{receiver?.name ?? (receiver ? 'KiwiSDR' : 'selecting…')}</b>
        <span className="muted">{receiver?.location ?? ''}</span>
        <span className="mono muted">{receiver?.gps_timed ? 'GPS-timed' : receiver ? 'no GPS time' : ''}{receiver?.rssi_dbm != null ? ` · ${receiver.rssi_dbm} dBm` : ''}</span>
      </div>
    </div>
  )
}

export function CensusTable({ census, onPick }: { census?: Census; onPick?: (khz: number) => void }) {
  if (!census) return <div className="empty">Waiting for enough waterfall rows to average…</div>
  return (
    <div>
      <table className="tbl">
        <thead><tr><th>Channel</th><th className="num">Level</th><th>Official AIR transmitter (Prasar Bharati list)</th><th className="num">Power</th><th>DRM</th></tr></thead>
        <tbody>
          <AnimatePresence initial={false}>
            {census.channels.map((c) => (
              <motion.tr key={c.khz} className={onPick ? 'click' : undefined} onClick={() => onPick?.(c.khz)} initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0 }}>
                <td className="mono">{c.khz} kHz</td>
                <td className="num">{c.level_db.toFixed(0)} dB</td>
                <td>{c.stations.length ? c.stations.map((s) => `${s.station}, ${s.state}`).join(' / ') : <span className="amber">not in the official list</span>}</td>
                <td className="num">{c.stations.length ? c.stations.map((s) => `${s.power_kw} kW`).join(' / ') : '—'}</td>
                <td>{c.stations.some((s) => s.drm) ? <span className="tag tag-LIVE" style={{ paddingLeft: 6 }}>capable</span> : <span className="muted">—</span>}</td>
              </motion.tr>
            ))}
          </AnimatePresence>
        </tbody>
      </table>
      <div className="muted" style={{ fontSize: 11.5, padding: '8px 12px' }}>
        Reference: <a href={census.reference.url} target="_blank" rel="noreferrer">{census.reference.title}</a> (retrieved {census.reference.retrieved}).
      </div>
    </div>
  )
}

export function AmPanel({ am, audioUrl }: { am?: AmMetrics; audioUrl?: string | null }) {
  if (!am) return <div className="empty">Measuring the carrier…</div>
  const cells: [string, string, string?][] = [
    ['Carrier offset', `${am.carrier_offset_hz >= 0 ? '+' : ''}${am.carrier_offset_hz.toFixed(2)} Hz`, `± ${am.carrier_offset_se_hz.toFixed(3)} Hz (fit)`],
    ['Carrier / noise', `${am.carrier_to_noise_db.toFixed(0)} dB`],
    ['Modulation depth', am.modulation_depth_rms == null ? 'not measurable' : `${(am.modulation_depth_rms * 100).toFixed(0)} % rms`, am.modulation_depth_rms == null ? 'receiver passband cuts one sideband' : undefined],
    ['Audio bandwidth', am.audio_bandwidth_99_hz ? `${(am.audio_bandwidth_99_hz / 1000).toFixed(1)} kHz` : '—', '99 % of modulation power'],
    ['Receiver passband', am.receiver_passband],
  ]
  return (
    <div className="col" style={{ gap: 12 }}>
      <div className="am-grid">
        {cells.map(([k, v, n]) => (
          <div key={k} className="am-cell"><span className="kpi-label">{k}</span><b className="mono">{v}</b>{n && <span className="muted" style={{ fontSize: 11 }}>{n}</span>}</div>
        ))}
      </div>
      <div className="muted" style={{ fontSize: 12 }}>{am.modulation}</div>
      {audioUrl && <audio controls src={audioUrl} style={{ width: '100%' }} />}
    </div>
  )
}

export function BlindCatalogue({ runs }: { runs?: Runs }) {
  const tc = runs?.timecode
  if (!tc) return null
  return (
    <div className="catalogue">
      <div className="catalogue-head"><span>Blind time-code catalogue</span><span className="mono">threshold 10^{tc.log10_threshold}</span></div>
      {tc.results.map((r) => (
        <div key={r.protocol} className={`catalogue-row${r.accepted ? ' ok' : r.detected ? ' mid' : ''}`}>
          <b>{r.protocol}</b>
          <span className="muted">{r.operator.split(' — ')[0].split(' (')[0]}</span>
          <span className="mono">{r.decoded ? `p 10^${r.log10_p.toFixed(1)}` : 'no frame'}</span>
          <span className="mono">{r.decoded ? `${r.mismatches}/${r.observed_symbols}` : ''}</span>
          <span className="catalogue-verdict">{r.accepted ? 'ACCEPTED' : r.detected ? 'DIGITS OPEN' : 'rejected'}</span>
        </div>
      ))}
      {!tc.results.some((r) => r.protocol === 'WWV') && <div className="muted" style={{ fontSize: 11 }}>WWV not tested: its 100-Hz subcarrier needs at least 2.4 kHz of sample rate.</div>}
    </div>
  )
}

export function progressSteps(kind: string, st: LiveState, station: StationInfo): Step[] {
  const r = st.receiver
  const has = (phase: string) => st.statuses.some((s) => s.phase === phase)
  const final = st.result
  const steps: Step[] = [
    { key: 'rx', label: 'Receiver in range selected', detail: r ? `${r.location ?? r.url ?? ''}${r.distance_km != null ? ` · ${r.distance_km} km from ${station.site.name}` : ''}` : undefined, state: r ? 'done' : 'active' },
  ]
  if (kind === 'timecode') {
    const n = st.symbols.length
    steps.push(
      { key: 'carrier', label: 'Carrier located', detail: st.carrierDb != null ? `${st.carrierDb.toFixed(0)} dB above noise` : undefined, state: st.carrierDb != null ? 'done' : r ? 'active' : 'pending' },
      { key: 'epoch', label: 'Second epoch estimated from the signal', detail: st.epochMs != null ? `${st.epochMs.toFixed(0)} ms into the capture second${st.epochFixed ? ' (locked)' : ''}` : undefined, state: st.epochMs != null ? (st.epochFixed ? 'done' : 'active') : 'pending' },
      { key: 'symbols', label: 'Seconds classified', detail: n ? `${n} symbols · ${st.symbols.filter((s) => !s.symbol).length} erased` : undefined, state: n >= 60 ? 'done' : n ? 'active' : 'pending' },
      { key: 'frame', label: 'Frame decoded under parity constraints', detail: st.decode ? `${st.decode.frames} frame(s) · p = 10^${st.decode.log10_p?.toFixed(1)}` : undefined, state: st.decode?.detected ? 'done' : st.decode ? 'active' : 'pending' },
      { key: 'digits', label: 'Every time digit established', detail: st.decode?.digits ? `${Object.values(st.decode.digits).filter((d) => d.established).length}/${Object.keys(st.decode.digits).length} digits` : undefined, state: st.decode?.established ? 'done' : st.decode ? 'active' : 'pending' },
      { key: 'verify', label: 'Checked against the receiver clock', detail: st.decode?.established && st.decode.verification ? `${st.decode.verification.arrival_minus_decoded_ms.toFixed(1)} ms` : undefined, state: st.decode?.established && st.decode.verification ? (st.decode.verification.agrees ? 'done' : 'failed') : 'pending' },
    )
  } else if (kind === 'fsk') {
    const f = st.fsk
    steps.push(
      { key: 'pair', label: 'Alternating tone pair found', detail: f?.shift_hz ? `shift ${f.shift_hz.toFixed(1)} Hz` : f?.reason, state: f?.status === 'DECODED' ? 'done' : f ? 'active' : 'pending' },
      { key: 'baud', label: 'Symbol rate from transition timing', detail: f?.baud ? `${f.baud} Bd${f.baud_estimate && Math.abs(f.baud_estimate / f.baud - 2) < 0.05 ? ' (transitions on a half-bit grid: 1.5 stop bits)' : ''}` : undefined, state: f?.baud ? 'done' : 'pending' },
      { key: 'framing', label: 'Character framing significant', detail: f?.framing ? `${f.framing.data_bits}-bit, ${f.framing.stop_bits} stop, ${(f.framing.stop_ok_fraction * 100).toFixed(1)} % stop bits valid` : undefined, state: f?.framing ? 'done' : 'pending' },
      { key: 'text', label: 'Text decoded', detail: f?.text ? `${f.text.length} characters (${f.code})` : undefined, state: f?.text ? 'done' : 'pending' },
    )
  } else if (kind === 'am') {
    steps.push({ key: 'carrier', label: 'Carrier measured', detail: st.am ? `${st.am.carrier_to_noise_db.toFixed(0)} dB · offset ${st.am.carrier_offset_hz.toFixed(2)} Hz` : undefined, state: st.am ? 'done' : r ? 'active' : 'pending' },
      { key: 'mod', label: 'Modulation characterised', detail: st.am?.modulation, state: st.am ? 'done' : 'pending' })
  } else if (kind === 'band') {
    const c = st.census
    steps.push({ key: 'rows', label: 'Wideband spectrum rows received', state: st.span ? 'done' : r ? 'active' : 'pending' },
      { key: 'census', label: 'Carriers separated from skirts (prominence)', detail: c ? `${c.channels.length} channels` : undefined, state: c ? 'done' : 'pending' },
      { key: 'match', label: 'Matched to the official AIR list', detail: c ? `${c.channels.filter((x) => x.stations.length).length} matched` : undefined, state: c ? 'done' : 'pending' })
  }
  steps.push({ key: 'final', label: 'Blind analysis of the whole capture', detail: final ? `${final.answer.status}${final.answer.protocol ? ` · ${final.answer.protocol}` : ''}` : has('analysing') ? 'running…' : undefined, state: final ? 'done' : has('analysing') ? 'active' : 'pending' })
  return steps
}
