"""Catalogue of real transmitters the platform can receive live, with their official references.

Every entry is a public, government-operated (or government-mandated) transmission whose format is
published by the operator, so a decoded answer can be checked against an independent source.
"""

STATIONS = {
    'WWV': {
        'name': 'WWV', 'operator': 'NIST — U.S. Department of Commerce', 'country': 'United States',
        'service': 'Standard time and frequency (HF)', 'frequency_khz': 10000.0, 'tuning_offset_hz': -1000.0,
        'site': {'name': 'Fort Collins, Colorado', 'lat': 40.6781, 'lon': -105.0471},
        'receivers': {'min_km': 250, 'max_km': 2500}, 'analysis': 'timecode', 'protocol': 'WWV', 'capture_s': 185,
        'references': [{'title': 'NIST Radio Station WWV', 'url': 'https://www.nist.gov/pml/time-and-frequency-division/time-distribution/radio-station-wwv'},
                       {'title': 'WWV/WWVH digital time code', 'url': 'https://www.nist.gov/pml/time-and-frequency-division/time-distribution/radio-station-wwv/wwv-and-wwvh-digital-time-code'}],
    },
    'WWVB': {
        'name': 'WWVB', 'operator': 'NIST — U.S. Department of Commerce', 'country': 'United States',
        'service': 'Standard time (LF 60 kHz)', 'frequency_khz': 60.0, 'tuning_offset_hz': -1000.0,
        'site': {'name': 'Fort Collins, Colorado', 'lat': 40.6776, 'lon': -105.0471},
        'receivers': {'min_km': 0, 'max_km': 1500}, 'analysis': 'timecode', 'protocol': 'WWVB', 'capture_s': 185,
        'references': [{'title': 'NIST Radio Station WWVB', 'url': 'https://www.nist.gov/pml/time-and-frequency-division/time-distribution/radio-station-wwvb'}],
    },
    'DCF77': {
        'name': 'DCF77', 'operator': 'PTB — Physikalisch-Technische Bundesanstalt (Germany)', 'country': 'Germany',
        'service': 'Legal time of Germany (LF 77.5 kHz)', 'frequency_khz': 77.5, 'tuning_offset_hz': -1000.0,
        'site': {'name': 'Mainflingen', 'lat': 50.0156, 'lon': 9.0106},
        'receivers': {'min_km': 0, 'max_km': 900}, 'analysis': 'timecode', 'protocol': 'DCF77', 'capture_s': 185,
        'references': [{'title': 'PTB: DCF77', 'url': 'https://www.ptb.de/cms/en/ptb/fachabteilungen/abt4/fb-44/ag-442/dissemination-of-legal-time/dcf77.html'}],
    },
    'MSF': {
        'name': 'MSF', 'operator': 'NPL — National Physical Laboratory (UK)', 'country': 'United Kingdom',
        'service': 'UK national time signal (LF 60 kHz)', 'frequency_khz': 60.0, 'tuning_offset_hz': -1000.0,
        'site': {'name': 'Anthorn, Cumbria', 'lat': 54.9111, 'lon': -3.2789},
        'receivers': {'min_km': 0, 'max_km': 900}, 'analysis': 'timecode', 'protocol': 'MSF', 'capture_s': 185,
        'references': [{'title': 'NPL: MSF radio time signal', 'url': 'https://www.npl.co.uk/msf-signal'}],
    },
    'JJY': {
        'name': 'JJY (40 kHz)', 'operator': 'NICT — National Institute of Information and Communications Technology (Japan)',
        'country': 'Japan', 'service': 'Japan Standard Time (LF 40 kHz)', 'frequency_khz': 40.0, 'tuning_offset_hz': -1000.0,
        'site': {'name': 'Mt. Otakadoya, Fukushima', 'lat': 37.3725, 'lon': 140.8489},
        'receivers': {'min_km': 0, 'max_km': 1200}, 'analysis': 'timecode', 'protocol': 'JJY', 'capture_s': 185,
        'references': [{'title': 'NICT: JJY transmission format', 'url': 'https://jjy.nict.go.jp/jjy/trans/index-e.html'}],
    },
    'DDH47': {
        'name': 'DDH47', 'operator': 'DWD — Deutscher Wetterdienst (German Meteorological Service)', 'country': 'Germany',
        'service': 'Maritime weather RTTY (LF 147.3 kHz)', 'frequency_khz': 147.3, 'tuning_offset_hz': -1000.0,
        'site': {'name': 'Pinneberg', 'lat': 53.6703, 'lon': 9.8014},
        'receivers': {'min_km': 0, 'max_km': 900}, 'analysis': 'fsk', 'capture_s': 90,
        'references': [{'title': 'DWD: maritime weather broadcasts (radioteletype)', 'url': 'https://www.dwd.de/EN/specialusers/shipping/broadcast_en/_node.html'}],
    },
    'CHU': {
        'name': 'CHU', 'operator': 'NRC — National Research Council Canada', 'country': 'Canada',
        'service': 'Canada official time (HF, FSK time code)', 'frequency_khz': 7850.0, 'tuning_offset_hz': -1500.0,
        'site': {'name': 'Ottawa, Ontario', 'lat': 45.2950, 'lon': -75.7564},
        'receivers': {'min_km': 0, 'max_km': 1500}, 'analysis': 'chu', 'capture_s': 70,
        'references': [{'title': 'NRC: CHU broadcasts', 'url': 'https://nrc.canada.ca/en/certifications-evaluations-standards/canadas-official-time/nrc-shortwave-station-broadcasts-chu'}],
    },
    'AIR-MW': {
        'name': 'All India Radio (medium wave)', 'operator': 'Prasar Bharati — Government of India public broadcaster',
        'country': 'India', 'service': 'AM broadcasting 531–1602 kHz', 'frequency_khz': 720.0, 'tuning_offset_hz': 0.0,
        'site': {'name': 'Chennai (720 kHz, 200 kW)', 'lat': 13.0827, 'lon': 80.2707},
        'receivers': {'min_km': 0, 'max_km': 800, 'preferred': ['http://vu2cpl.ddns.net:8073', 'http://117.205.198.153:8073']},
        'analysis': 'am', 'capture_s': 30, 'band_khz': (531.0, 1602.0),
        'references': [{'title': 'Prasar Bharati: existing AIR stations and transmitters (31 May 2024)',
                        'url': 'https://prasarbharati.gov.in/wp-content/uploads/2025/03/19-LIST-OF-EXISTING-STATIONS-AND-TRANSMITTERS-310524.pdf'}],
    },
}
