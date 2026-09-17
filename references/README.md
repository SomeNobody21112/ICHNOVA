# Reference data

Normative constants transcribed from their defining documents, plus vectors from an independent implementation. Engine code loads or re-derives them; tests check the engine against them. Never edit by hand without re-checking the source.

| File | Content | Source | Verification |
|---|---|---|---|
| `ccsds_constants.json` | ASM patterns, randomizer polynomials/seeds with the published first 40 bits, RS dual-basis matrices and Annex F examples/table rows, LDPC (128,64) H block layout and generator hex rows | CCSDS 131.0-B-5 (Sep 2023), CCSDS 231.0-B-4 (Jul 2021) | `tests/test_catalogue.py` regenerates randomizers, converts the Annex F examples, and checks H·Gᵀ = 0, rank H = 64 |
| `lte_qpp_table.json` | 188 QPP turbo-interleaver parameters (K, f1, f2) | 3GPP TS 36.212 v10.0.0 Table 5.1.3-3 (parsed from the PDF text) | K grid equals 40..512/8, 528..1024/16, 1056..2048/32, 2112..6144/64; every entry is a permutation |
| `rs_ccsds_conventional_vectors.json` | CCSDS RS(255,223) and RS(255,239) parity in the **conventional** basis (field 0x187, roots β^(fcr+i), β = α¹¹), full-length and shortened | Generated once with `reedsolo` 1.7.0 (independent implementation, not a project dependency) | `tests/test_catalogue.py` compares the engine's encoder; dual-basis conversion is checked separately against Annex F |
