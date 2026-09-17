import { AnimatePresence, motion } from 'framer-motion'
import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { PRODUCT } from '../brand'
import { Constellation, LiveWaterfall } from '../components/charts'
import { BrandMark, Icon, Stamp, Tag } from '../components/ui'
import { RealProof } from '../components/realproof'
import { useApp } from '../lib/store'
import type { Provenance, Status } from '../lib/types'

export const COVERAGE: { req: string; detail: string; status: Provenance | 'ESTABLISHED' }[] = [
  { req: 'Input .IQ and .wav', detail: 'Interleaved float32 I/Q; int16 stereo I/Q WAV (header sample rate)', status: 'ESTABLISHED' },
  { req: 'Waterfall, spectrum, constellation', detail: 'Time–frequency, PSD and symbol constellation for every capture', status: 'ESTABLISHED' },
  { req: 'Symbol rate & carrier offset', detail: 'Blind search over 2–20 samples/symbol; x²/x⁴ carrier lines', status: 'ESTABLISHED' },
  { req: 'Demodulation: PSK', detail: 'BPSK and QPSK, both tested for every candidate', status: 'ESTABLISHED' },
  { req: 'FEC: convolutional + Viterbi', detail: 'K=7, K=5, K=3 rate ½ catalogue; exact parity-check test', status: 'ESTABLISHED' },
  { req: 'De-interleaving: block', detail: 'Single block, rows 2–16 × cols 4–24 (≤384 bits)', status: 'ESTABLISHED' },
  { req: 'Sampling frequency (blind)', detail: 'Currently read from WAV header or operator metadata', status: 'NOT ESTABLISHED' },
  { req: 'Demodulation: FSK', detail: 'Blind tone pair, shift, baud, polarity and character framing; verified on a real DWD teleprinter broadcast', status: 'ESTABLISHED' },
  { req: 'Demodulation: QAM', detail: 'Planned', status: 'NOT ESTABLISHED' },
  { req: 'Real-world transmissions', detail: 'NIST, PTB, NPL, NICT time codes and DWD RTTY decoded blind, checked against receiver GPS time; AIR carriers vs official list', status: 'ESTABLISHED' },
  { req: 'De-interleaving: convolutional, diagonal, pseudo-random', detail: 'Planned', status: 'NOT ESTABLISHED' },
  { req: 'FEC: RS, concatenated, LDPC', detail: 'Planned', status: 'NOT ESTABLISHED' },
  { req: 'Bit-stream correlation (header / payload)', detail: 'Frame synchronisation on marker patterns and redundancy checks for time codes and CHU packets; general header search planned', status: 'EXPERIMENTAL' },
]

function makeCloud(kind: Status, seed: number) {
  let s = seed
  const r = () => { s = (s * 16807) % 2147483647; return s / 2147483647 }
  const noise = kind === 'DECODED' ? 0.16 : kind === 'SIGNAL_NO_CODE' ? 0.3 : 0.75
  return Array.from({ length: 420 }, () => {
    const g = () => (r() + r() + r() - 1.5) * noise
    return [(r() < 0.5 ? -0.707 : 0.707) + g(), (r() < 0.5 ? -0.707 : 0.707) + g()]
  })
}

function Instrument() {
  const states: Status[] = ['DECODED', 'SIGNAL_NO_CODE', 'UNKNOWN']
  const [k, setK] = useState(0)
  useEffect(() => { const id = setInterval(() => setK((x) => (x + 1) % 3), 3600); return () => clearInterval(id) }, [])
  const st = states[k]
  const caption: Record<Status, string> = {
    DECODED: 'Parity evidence passes after correcting for every hypothesis tested.',
    SIGNAL_NO_CODE: 'A signal is present. No code could be verified, so none is claimed.',
    UNKNOWN: 'The evidence supports no interpretation. The platform says so.',
  }
  return (
    <div className="panel" style={{ overflow: 'hidden' }}>
      <div className="panel-head"><span className="panel-title grow">Evidence instrument</span><Tag kind="SIMULATED">Illustration</Tag></div>
      <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr', gap: 0 }}>
        <div style={{ borderRight: '1px solid var(--line)' }}>
          <LiveWaterfall height={300} channels={120} seed={3} events={[
            { id: 'a', f0: 28, f1: 44, label: 'burst', tone: '#5fd0f0', startRow: 3, rows: 22 },
            { id: 'b', f0: 70, f1: 78, label: 'burst', tone: '#e9b949', startRow: 30, rows: 14 },
          ]} />
        </div>
        <div className="col" style={{ padding: 14, gap: 10 }}>
          <AnimatePresence mode="wait">
            <motion.div key={st} initial={{ opacity: 0, scale: 0.96 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.35 }}>
              <Constellation points={makeCloud(st, 17 + k)} ideal={st === 'UNKNOWN' ? null : 'QPSK'} height={190} />
              <div style={{ marginTop: 10 }}><Stamp status={st} size="lg" /></div>
              <p className="dim" style={{ fontSize: 13, margin: '10px 0 0' }}>{caption[st]}</p>
            </motion.div>
          </AnimatePresence>
        </div>
      </div>
    </div>
  )
}

export default function Landing() {
  const { session, setTour } = useApp()
  const nav = useNavigate()
  const start = () => { if (session) { setTour({ active: true, scene: 0 }); nav('/app/monitor') } else nav('/signin', { state: { tour: true } }) }
  const flow = [
    ['Observe', 'Ingest .IQ / .wav captures with station and receiver metadata.'],
    ['Infer', 'Search symbol rate, carrier offset, modulation, code and interleaver as explicit hypotheses.'],
    ['Verify', 'Accept only what survives exact parity tests, multiple-testing correction and structural checks.'],
    ['Correlate', 'Turn each evidence record into a fingerprint; link recurrences across stations.'],
    ['Act', 'Route unknowns to analysts, open incidents, export auditable reports.'],
  ]
  return (
    <div className="landing">
      <nav className="land-nav">
        <div className="row"><BrandMark size={28} /><span className="brand-name">{PRODUCT.name}</span></div>
        <span className="spacer" />
        <a href="#real">Real signals</a><a href="#flow">Workflow</a><a href="#restraint">Restraint</a><a href="#coverage">Problem statement</a>
        {session ? <Link className="btn btn-primary" to="/app/command">Open console</Link> : <Link className="btn btn-primary" to="/signin">Sign in</Link>}
      </nav>
      <section className="land-hero">
        <motion.div initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }}>
          <div className="eyebrow">{PRODUCT.context} · {PRODUCT.sponsor}</div>
          <h1 className="land-h1">From unknown signals to <em>actionable RF intelligence</em>.</h1>
          <p className="land-lede">
            Blind analysis of .IQ and .wav captures in which every inferred parameter carries its evidence: symbol rate,
            carrier offset, modulation, FEC and interleaving. {PRODUCT.restraint}
          </p>
          <div className="row-wrap" style={{ gap: 10 }}>
            <button className="btn btn-primary btn-lg" onClick={start}><Icon name="play" size={14} /> Six-scene walkthrough</button>
            <Link className="btn btn-lg" to={session ? '/app/command' : '/signin'}>{session ? 'Open console' : 'Sign in'}</Link>
          </div>
          <div style={{ marginTop: 26 }} className="philosophy"><Icon name="shield" size={15} /><s>{PRODUCT.antiPhilosophy}</s></div>
          <div className="philosophy" style={{ marginTop: 6, color: 'var(--text)' }}><Icon name="check" size={15} /><span>{PRODUCT.philosophy}</span></div>
        </motion.div>
        <motion.div initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5, delay: 0.15 }}>
          <Instrument />
        </motion.div>
      </section>

      <section className="land-sec" id="real">
        <div className="eyebrow">Proven on the air, not only on test sets</div>
        <h2>Real government transmissions, decoded blind and checked</h2>
        <p className="dim" style={{ maxWidth: '76ch' }}>
          Time signals from NIST (USA), PTB (Germany), NPL (UK) and NICT (Japan), weather teleprinter from the German Meteorological Service and
          All India Radio medium wave, received through public receivers. Decoded times agree with each receiver&apos;s GPS clock to within milliseconds;
          India&apos;s carriers are matched to Prasar Bharati&apos;s official transmitter list; a weak capture is refused rather than guessed.
        </p>
        <div style={{ marginTop: 18 }}><RealProof /></div>
      </section>

      <section className="land-sec" id="flow">
        <div className="eyebrow">Workflow</div>
        <h2>Observe → Infer → Verify → Correlate → Act</h2>
        <p className="dim" style={{ maxWidth: '70ch' }}>Not upload → AI → answer. Each step leaves a record an analyst, a supervisor or an auditor can open.</p>
        <div className="flow">
          {flow.map(([t, d], i) => (
            <motion.div key={t} className="flow-step" initial={{ opacity: 0, y: 10 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: i * 0.08 }}>
              <span className="flow-idx">0{i + 1}</span><b>{t.toUpperCase()}</b><p>{d}</p>
            </motion.div>
          ))}
        </div>
        <div className="row-wrap" style={{ marginTop: 22, gap: 8 }}>
          {['Blind signal analysis', 'Statistical validation', 'Signal fingerprinting', 'Anomaly review', 'Cross-station correlation', 'Human-in-the-loop intelligence'].map((c) => <span key={c} className="chip" style={{ cursor: 'default' }}>{c}</span>)}
        </div>
      </section>

      <section className="land-sec" id="restraint">
        <div className="grid g-2" style={{ alignItems: 'center', gap: 40 }}>
          <div>
            <div className="eyebrow">Scientific restraint</div>
            <p className="statement" style={{ marginTop: 10 }}>When the evidence isn't enough, it says <span className="amber">UNKNOWN</span>.</p>
            <p className="dim" style={{ maxWidth: '60ch', marginTop: 16 }}>
              On 900 benchmark captures that carry no catalogue code (noise, uncoded, out-of-family), the engine asserted a code 0 times.
              Refusing to manufacture an answer is a result, not a failure.
            </p>
            <Tag kind="BENCHMARK">Benchmark: synthetic captures</Tag>
          </div>
          <div className="grid g-3">
            {([['DECODED', 'Evidence passed'], ['SIGNAL_NO_CODE', 'Signal detected · code unverified'], ['UNKNOWN', 'Insufficient evidence']] as [Status, string][]).map(([s, d], i) => (
              <motion.div key={s} className="card" initial={{ opacity: 0, y: 10 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: i * 0.1 }} style={{ minHeight: 150 }}>
                <Stamp status={s} /><p className="dim" style={{ marginTop: 14 }}>{d}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      <section className="land-sec" id="coverage">
        <div className="eyebrow">Problem statement SIH26147 · {PRODUCT.sponsor}</div>
        <h2>{PRODUCT.psTitle}</h2>
        <p className="dim" style={{ maxWidth: '72ch' }}>What the prototype establishes today, and what it does not claim.</p>
        <div className="panel" style={{ marginTop: 18 }}>
          {COVERAGE.map((c) => (
            <div key={c.req} className="cov-row">
              <span style={{ fontWeight: 500 }}>{c.req}</span><span className="dim" style={{ fontSize: 13 }}>{c.detail}</span>
              {c.status === 'ESTABLISHED' ? <span className="tag tag-LIVE" style={{ justifySelf: 'end' }}>Established</span> : <span style={{ justifySelf: 'end' }}><Tag kind={c.status} /></span>}
            </div>
          ))}
        </div>
      </section>
      <footer className="land-foot">{PRODUCT.disclaimer} Map boundaries: DataMeet India, Survey of India depiction (CC BY 4.0).</footer>
    </div>
  )
}
