import { motion } from 'framer-motion'
import { Link, useNavigate } from 'react-router-dom'
import { PRODUCT } from '../brand'
import { BrandMark, Lockup, Wordmark } from '../components/brand'
import { RealProof } from '../components/realproof'
import { Icon, Stamp, Tag } from '../components/ui'
import { UtilityBar } from '../components/utility'
import { useApp } from '../lib/store'
import type { Provenance, Status } from '../lib/types'

export const COVERAGE: { req: string; detail: string; status: Provenance | 'ESTABLISHED' }[] = [
  { req: 'Input .IQ and .wav', detail: 'Interleaved float32 I/Q; int16 stereo I/Q WAV (header sample rate)', status: 'ESTABLISHED' },
  { req: 'Waterfall, spectrum, constellation', detail: 'Time–frequency, PSD and symbol constellation for every capture', status: 'ESTABLISHED' },
  { req: 'Symbol rate & carrier offset', detail: 'Blind search over 2–20 samples/symbol; x²/x⁴ carrier lines', status: 'ESTABLISHED' },
  { req: 'Demodulation: PSK', detail: 'BPSK and QPSK, both tested for every candidate', status: 'ESTABLISHED' },
  { req: 'Demodulation: FSK', detail: 'Blind tone pair, shift, baud, polarity and character framing; verified on a real DWD teleprinter broadcast', status: 'ESTABLISHED' },
  { req: 'FEC: convolutional + Viterbi', detail: 'K=7, K=5, K=3 rate ½ catalogue; exact parity-check test', status: 'ESTABLISHED' },
  { req: 'De-interleaving: block', detail: 'Single block, rows 2–16 × cols 4–24 (≤384 bits)', status: 'ESTABLISHED' },
  { req: 'Real-world transmissions', detail: 'NIST, PTB, NPL, NICT time codes and DWD RTTY decoded blind, checked against receiver GPS time; AIR carriers vs official list', status: 'ESTABLISHED' },
  { req: 'Bit-stream correlation (header / payload)', detail: 'Frame synchronisation on marker patterns and redundancy checks for time codes and CHU packets; general header search planned', status: 'EXPERIMENTAL' },
  { req: 'Sampling frequency (blind)', detail: 'Currently read from WAV header or operator metadata', status: 'NOT ESTABLISHED' },
  { req: 'Demodulation: QAM', detail: 'Planned', status: 'NOT ESTABLISHED' },
  { req: 'De-interleaving: convolutional, diagonal, pseudo-random', detail: 'Planned', status: 'NOT ESTABLISHED' },
  { req: 'FEC: RS, concatenated, LDPC', detail: 'Planned', status: 'NOT ESTABLISHED' },
]

const SERVICES = [
  { icon: 'analysis', title: 'Analyse a capture', text: 'Upload an .IQ or .wav recording; get modulation, symbol rate, code and payload, or a clear refusal.', to: '/app/analysis' },
  { icon: 'monitor', title: 'Watch live signals', text: 'Receive government time and weather broadcasts and All India Radio as they arrive.', to: '/app/monitor' },
  { icon: 'review', title: 'Review undecided signals', text: 'Signals the engine could not prove wait here for an analyst decision.', to: '/app/review' },
  { icon: 'lab', title: 'Check the evidence', text: 'Benchmarks, null tests and real-signal results, each read from result files.', to: '/app/lab' },
]

const STEPS: [string, string, string][] = [
  ['Noise', 'Observe & search', 'Carrier, symbol rate, modulation, code and interleaver are treated as hypotheses and searched blind.'],
  ['Discovery', 'Verify', 'An answer is accepted only if exact statistical tests pass after correcting for every hypothesis tried.'],
  ['Harmony', 'Decide & act', 'Decoded, detected or unknown: each record carries its evidence into review, incidents and reports.'],
]

export default function Landing() {
  const { session, setTour } = useApp()
  const nav = useNavigate()
  const go = (to: string) => (session ? nav(to) : nav('/signin', { state: { from: to } }))
  const tour = () => { if (session) { setTour({ active: true, scene: 0 }); nav('/app/monitor?rec=jjy40-japan-2026-09-17') } else nav('/signin', { state: { tour: true } }) }
  return (
    <div className="landing">
      <UtilityBar />
      <header className="land-nav">
        <Link to="/" className="row" style={{ gap: 10, color: 'var(--text)', textDecoration: 'none' }} aria-label={`${PRODUCT.name} home`}>
          <BrandMark size={34} /><Wordmark height={12} />
        </Link>
        <span className="spacer" />
        <nav className="row nav-links" style={{ gap: 22 }} aria-label="Sections">
          <a href="#services">Services</a><a href="#real">Real signals</a><a href="#how">How it works</a><a href="#coverage">Problem statement</a>
        </nav>
        {session ? <Link className="btn btn-primary" to="/app/command">Open console</Link> : <Link className="btn btn-primary" to="/signin">Sign in</Link>}
      </header>

      <main id="main">
        <section className="land-hero">
          <motion.div initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }}>
            <div className="eyebrow">{PRODUCT.context} · {PRODUCT.sponsor}</div>
            <h1 className="land-h1">Hidden signals, <em>made clear</em> — with the evidence to prove it.</h1>
            <p className="land-lede">
              {PRODUCT.name} analyses .IQ and .wav recordings without being told what they contain: carrier, symbol rate, modulation,
              error-correcting code and interleaver. {PRODUCT.restraint}
            </p>
            <div className="row-wrap" style={{ gap: 10 }}>
              <button className="btn btn-primary btn-lg" onClick={() => go('/app/analysis')}><Icon name="upload" size={15} /> Analyse a capture</button>
              <button className="btn btn-lg" onClick={() => go('/app/monitor?rec=jjy40-japan-2026-09-17')}><Icon name="monitor" size={15} /> Watch a real signal</button>
            </div>
            <button className="btn btn-ghost" style={{ marginTop: 10, paddingLeft: 0 }} onClick={tour}><Icon name="play" size={12} /> Take the 2-minute guided tour</button>
          </motion.div>
          <motion.div initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5, delay: 0.12 }}>
            <div className="hero-card">
              <Lockup width={380} animate />
              <div className="concept">
                {PRODUCT.concept.map((c, i) => (
                  <motion.div key={c} className="concept-step" initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 1.2 + i * 0.25 }}>
                    <b>{c}</b><span>{['raw recording', 'tested hypotheses', 'accountable decision'][i]}</span>
                  </motion.div>
                ))}
              </div>
            </div>
          </motion.div>
        </section>

        <section className="land-sec" style={{ paddingTop: 0 }} aria-label="At a glance">
          <div className="stats">
            <div className="stat"><b>5</b><span>real government transmissions decoded blind</span><small><Tag kind="LIVE">Real signals</Tag></small></div>
            <div className="stat"><b>2–23 ms</b><span>agreement with receiver GPS time</span><small>NICT, NPL, PTB, NIST</small></div>
            <div className="stat"><b>0 / 900</b><span>false accepts on non-code captures</span><small><Tag kind="BENCHMARK">Benchmark</Tag></small></div>
            <div className="stat"><b>3.8×</b><span>faster search, identical decisions</span><small>1,480 files re-checked</small></div>
          </div>
        </section>

        <section className="land-sec" id="services">
          <div className="eyebrow">Services</div>
          <h2>What you can do</h2>
          <div className="tasks" style={{ marginTop: 18 }}>
            {SERVICES.map((s) => (
              <button key={s.title} className="task" style={{ textAlign: 'left', cursor: 'pointer', font: 'inherit' }} onClick={() => go(s.to)}>
                <span className="task-icon"><Icon name={s.icon} /></span>
                <span><b>{s.title}</b><span>{s.text}</span></span>
                <span className="go"><Icon name="arrow" size={16} /></span>
              </button>
            ))}
          </div>
        </section>

        <section className="land-sec alt" id="real">
          <div className="inner">
            <div className="eyebrow">Proven on the air</div>
            <h2>Real transmissions, decoded blind and checked</h2>
            <p className="dim" style={{ maxWidth: '72ch', margin: '0 0 18px' }}>
              Time signals from NIST, PTB, NPL and NICT, a German Meteorological Service teleprinter and All India Radio medium wave, received
              through public receivers. Each answer is compared with something the engine did not use: the receiver&apos;s GPS clock, the message itself,
              or Prasar Bharati&apos;s official transmitter list.
            </p>
            <RealProof limit={4} />
            <div style={{ marginTop: 14 }}><button className="btn" onClick={() => go('/app/lab')}>See all results in the Evidence lab <Icon name="arrow" size={14} /></button></div>
          </div>
        </section>

        <section className="land-sec" id="how">
          <div className="eyebrow">How it works</div>
          <h2>From noise to harmony, in three steps</h2>
          <div className="flow three">
            {STEPS.map(([k, t, d], i) => (
              <motion.div key={t} className="flow-step" initial={{ opacity: 0, y: 10 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: i * 0.08 }}>
                <span className="flow-idx">{k.toUpperCase()}</span><b>{t}</b><p>{d}</p>
              </motion.div>
            ))}
          </div>
          <div className="row-wrap" style={{ gap: 12, marginTop: 20 }}>
            {([['DECODED', 'Evidence passed'], ['SIGNAL_NO_CODE', 'Signal present, code not proven'], ['UNKNOWN', 'Not enough evidence']] as [Status, string][]).map(([s, d]) => (
              <span key={s} className="row" style={{ gap: 8 }}><Stamp status={s} /><span className="dim" style={{ fontSize: 13 }}>{d}</span></span>
            ))}
          </div>
        </section>

        <section className="land-sec" id="coverage" style={{ paddingTop: 0 }}>
          <div className="eyebrow">Problem statement SIH26147 · {PRODUCT.sponsor}</div>
          <h2>{PRODUCT.psTitle}</h2>
          <details className="more">
            <summary>What the prototype does, and does not, claim ({COVERAGE.filter((c) => c.status === 'ESTABLISHED').length} of {COVERAGE.length} requirements established)</summary>
            <div className="panel" style={{ marginTop: 12 }}>
              {COVERAGE.map((c) => (
                <div key={c.req} className="cov-row">
                  <span style={{ fontWeight: 500 }}>{c.req}</span><span className="dim" style={{ fontSize: 13 }}>{c.detail}</span>
                  {c.status === 'ESTABLISHED' ? <span className="tag tag-LIVE" style={{ justifySelf: 'end' }}>Established</span> : <span style={{ justifySelf: 'end' }}><Tag kind={c.status} /></span>}
                </div>
              ))}
            </div>
          </details>
        </section>
      </main>

      <footer className="site-foot">
        <div className="cols">
          <div className="col" style={{ gap: 10 }}>
            <div className="row" style={{ gap: 10 }}><BrandMark size={30} /><Wordmark height={11} /></div>
            <span>{PRODUCT.tagline}</span>
            <span className="muted" style={{ fontSize: 12 }}>{PRODUCT.disclaimer}</span>
          </div>
          <div><h4>Use the platform</h4><ul>
            <li><a onClick={() => go('/app/analysis')} href="#services">Analyse a capture</a></li>
            <li><a onClick={() => go('/app/monitor')} href="#services">Live signals</a></li>
            <li><a onClick={() => go('/app/review')} href="#services">Review queue</a></li>
            <li><a onClick={tour} href="#how">Guided tour</a></li>
          </ul></div>
          <div><h4>Evidence</h4><ul>
            <li><a onClick={() => go('/app/lab')} href="#real">Evidence lab</a></li>
            <li><a href="https://github.com/SomeNobody21112/SIH26147/blob/baseline-hardening/reports/REAL_SIGNAL_VALIDATION.md" target="_blank" rel="noreferrer">Real-signal validation report</a></li>
            <li><a href="https://github.com/SomeNobody21112/SIH26147/blob/baseline-hardening/reports/RESEARCH_LANDSCAPE.md" target="_blank" rel="noreferrer">Research landscape</a></li>
            <li><a href="https://github.com/SomeNobody21112/SIH26147" target="_blank" rel="noreferrer">Source code</a></li>
          </ul></div>
          <div><h4>Data sources</h4><ul>
            <li><a href="https://prasarbharati.gov.in/" target="_blank" rel="noreferrer">Prasar Bharati transmitter list</a></li>
            <li><a href="http://kiwisdr.com/public/" target="_blank" rel="noreferrer">Public KiwiSDR receivers</a></li>
            <li><a href="https://www.nist.gov/pml/time-and-frequency-division/time-distribution/radio-station-wwv" target="_blank" rel="noreferrer">NIST, PTB, NPL, NICT, DWD formats</a></li>
            <li><span>Map: DataMeet India (CC BY 4.0)</span></li>
          </ul></div>
        </div>
        <div className="base"><span>Last updated: {PRODUCT.updated}</span><span>Best viewed in current Chrome, Edge, Firefox or Safari</span><span>{PRODUCT.context}</span></div>
      </footer>
    </div>
  )
}
