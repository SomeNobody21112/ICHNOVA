# Real-Signal Validation — Government Transmissions Received Blind

**Date:** 2026-09-17 · **Code:** `src/timecodes.py`, `src/fsk.py`, `src/broadcast.py`, `src/realsig.py`, `server/kiwi.py`, `server/live.py`
**Recordings:** `recordings/real/` (IQ `.wav` + JSON sidecar with GPS start time) · **Tests:** `tests/test_realsig.py` (21 tests, run in CI)

## Question

Does the engine produce correct answers on real, over-the-air transmissions, and can each answer be checked against something the engine did not use?

## Sources

No government website streams raw IQ. The transmitters themselves are government-operated and their formats are published by the operators; the IQ was received through public, volunteer-operated KiwiSDR receivers (0–30 MHz, 12 kHz IQ, per-block GPS timestamps when the receiver has a fix), selected automatically from the public receiver directory by distance to the transmitter.

| Station | Operator | Format reference |
|---|---|---|
| WWV 10 MHz, WWVB 60 kHz | NIST, U.S. Department of Commerce | [WWV](https://www.nist.gov/pml/time-and-frequency-division/time-distribution/radio-station-wwv), [WWV/WWVH time code](https://www.nist.gov/pml/time-and-frequency-division/time-distribution/radio-station-wwv/wwv-and-wwvh-digital-time-code), [WWVB](https://www.nist.gov/pml/time-and-frequency-division/time-distribution/radio-station-wwvb) |
| DCF77 77.5 kHz | PTB (Germany) | [PTB DCF77](https://www.ptb.de/cms/en/ptb/fachabteilungen/abt4/fb-44/ag-442/dissemination-of-legal-time/dcf77.html) |
| MSF 60 kHz | NPL (UK) | [NPL MSF](https://www.npl.co.uk/msf-signal) |
| JJY 40 kHz | NICT (Japan) | [NICT JJY format](https://jjy.nict.go.jp/jjy/trans/index-e.html) |
| DDH47 147.3 kHz RTTY | Deutscher Wetterdienst | [DWD maritime broadcasts](https://www.dwd.de/EN/specialusers/shipping/broadcast_en/_node.html) |
| All India Radio MW | Prasar Bharati (Government of India) | [Existing AIR stations and transmitters, 31 May 2024](https://prasarbharati.gov.in/wp-content/uploads/2025/03/19-LIST-OF-EXISTING-STATIONS-AND-TRANSMITTERS-310524.pdf) |
| CHU 7850 kHz | NRC Canada | [NRC CHU](https://nrc.canada.ca/en/certifications-evaluations-standards/canadas-official-time/nrc-shortwave-station-broadcasts-chu) (decoder implemented and tested on synthetic packets; not received during this session) |

## Method (what the engine is and is not told)

The engine is told where to listen (tuned frequency). It is **not** told the station, protocol, carrier offset, second epoch, symbol widths, baud rate, shift, framing or polarity.

- **Time codes** (`timecodes.receive`): for each of five catalogue protocols it finds the carrier, estimates the second epoch from the signal (fold, then least-squares refinement), classifies every second by least-squares fit to that protocol's symbol shapes, aligns 60-s frames on markers, and decodes each frame by **maximum likelihood over valid field values only, with parity bits as constraints** (dynamic programming over parity state). All complete frames are then scored jointly against the frames implied by the decoded minute.
  - *Detection:* p = P(≤ observed disagreements | symbols unrelated to any frame) × number of distinct frames the search can output (every minute 2000–2099 × flags × 60 alignments), Bonferroni over the catalogue; α = 0.01.
  - *Digits:* every time digit (year tens … minute units) must beat every alternative value by ≥ 100:1, using the capture's own symbol error rate. A significant frame with an unresolved digit is **SIGNAL_NO_CODE**, never a time.
- **FSK text** (`fsk.analyze_fsk`): alternating tone pair (anti-correlated tone energies), shift from coherent periodograms of mark and space runs, baud from transition phase coherence (with the half-bit grid of 1.5 stop bits resolved inside the framing test), then start-stop framing hypotheses (baud × polarity × data bits × parity × stop bits) accepted by an exact binomial test on stop bits, Bonferroni over the hypotheses.
- **AM** (`broadcast.analyze_am`): carrier offset by phase-slope fit, carrier-to-noise, coherent product detection, audio bandwidth; one-sided receiver passbands are detected and reported instead of producing fake modulation depth.
- **Medium-wave census** (`live.spectrum_census`): waterfall rows averaged, carriers kept only if topographically prominent against their ±1.5-channel neighbourhood (removes the skirts of a strong local transmitter), snapped to the 9-kHz raster and matched to the official Prasar Bharati list.

**Independent checks** (never used for the decision): receiver GPS time vs the decoded minute; the RTTY text's own statement of callsign and frequency; the official AIR transmitter list.

## Results

| Recording | Receiver (distance) | Engine answer | Evidence | Independent check |
|---|---|---|---|---|
| JJY 40 kHz | Okegawa, Saitama (191 km), GPS | **DECODED** 2026-09-17 03:17 UTC | 2 frames, 0/120 symbols disagree, p = 10^-32.3; all 9 digits established | arrival − decoded **+1.9 ms** (light time 0.6 ms) |
| DCF77 77.5 kHz | Trémolat, France (839 km), GPS | **DECODED** 03:17 UTC | 2 frames, 0/88, p = 10^-14.7 | **+4.7 ms** (light time 2.8 ms) |
| MSF 60 kHz | South West England (466 km), GPS | **DECODED** 02:58 UTC | 2 frames, 11/120, p = 10^-15.0 | **+3.6 ms** (1.6 ms) |
| WWV 10 MHz | W. Montana (976 km), GPS | **DECODED** 02:58 UTC (DST flags set) | 2 frames, 3/109, p = 10^-23.4 | **+23.4 ms** (3.3 ms ground; sky-wave and receiver filters add delay) |
| WWVB 60 kHz | W. Montana (976 km), GPS | **SIGNAL_NO_CODE** — WWVB structure significant (p = 10^-4.7), time **refused** | 25/119 symbols disagree (21 %), no digit reaches 100:1 | ML frame was 2066-09-17 03:57 — wrong; the digit test is what prevented a false time |
| DDH47 147.3 kHz | Høll Strand, Denmark (219 km), GPS | **DECODED** ITA2 text | 50 Bd, shift 85.0 Hz, 5 data bits, 1.5 stop, 825/828 stop bits valid, p = 10^-241 | Text reads `CQ CQ CQ DE DDH47 DDH9 DDH8 / FREQUENCIES 147.3 KHZ 11039 KHZ 14467.3 KHZ` — its own callsign and the tuned frequency; DWD publishes 50 Bd / 85 Hz |
| AIR Chennai 720 kHz | Bangalore (287 km) | **SIGNAL_NO_CODE** — AM broadcast | carrier 53 dB above noise, offset −0.17 Hz (receiver not GPS-locked), audio bandwidth 2.6 kHz; receiver delivered one sideband (detected and reported) | 720 kHz Chennai 200 kW in the official list; programme audio demodulated (`frontend/public/live/*.wav`) |
| AIR MW band | Bangalore, 60 s waterfall | 5 carriers | prominence-filtered, axis fit scale 1.0021 | **5/5** matched: Bangalore 612 (200 kW), Chennai 720 (200 kW), Vijayawada 837, Cuddapah 900, Tiruchirapalli 936 (100 kW) |

Earlier single-frame WWV captures (Michigan 03:17, Tennessee 5 MHz 03:17) decoded the right minute with 0–1 errors but were reported as provisional: one frame gives each digit a single observation, below the 100:1 rule. The live monitor therefore captures ~3 minutes for time codes.

## Live operation

`server/live.py` runs the same processing incrementally on a live KiwiSDR stream (Server-Sent Events to the browser): spectrum rows, one symbol per received second, frame decodes as digits become established, and the final blind analysis over the whole capture, saved as a recording. Verified live during development: DWD (text, then idle carrier correctly reported as no keying), WWV Jackson TN (carrier 50–55 dB, epoch stable to ±1 ms across refits, symbols streaming). Replays in the frontend are produced by the same `LiveProcessor` over the committed recordings (`server/export_live_replays.py`).

## Limitations

- Stations are chosen by the operator (the engine is told where to listen); the protocol is still identified blindly from the catalogue.
- Five time-code formats, ITA2/ASCII start-stop FSK, CHU packets and AM are covered; NAVTEX/SITOR-B, DRM (AIR's digital MW) and PSK modems on air are not yet.
- Receiver clocks: the GPS check measures arrival delay including receiver filter delay, which is not calibrated per receiver (WWV +23 ms stands out).
- The Indian receivers deliver one sideband in IQ mode; modulation depth is therefore reported as not measurable rather than estimated.
- Propagation decides availability: CHU was not receivable during the session; DWD transmits in scheduled slots.
