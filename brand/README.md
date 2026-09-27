# Brand assets

Source images for the ICHNOVA wordmark and emblem.

They live here rather than in `frontend/public/` on purpose: everything under `public/` is copied
into `frontend/dist/` by the Vite build and therefore shipped in the deployed image and served to
every visitor. These four files are 637 kB, they are referenced by nothing in the application, and
PNG does not compress further on the wire — so in `public/` they were the largest single payload the
deployment carried, larger than all of the evidence packs put together once those are gzipped.

The console draws its own wordmark and emblem as inline SVG (`frontend/src/components/brand.tsx`),
so nothing here is needed at runtime. Use these for decks, documents and anything outside the app.

| File | Size | Dimensions |
|---|---|---|
| `ichnova-logo-dark.png` | 430 kB | 886 x 490 |
| `ichnova-logo.png` | 107 kB | 416 x 256 |
| `ichnova-emblem.png` | 67 kB | 243 x 243 |
| `ichnova-mark.png` | 32 kB | 243 x 243 |

`frontend/public/favicon.png` (3 kB) and `favicon.svg` stay where they are: `index.html` references
them.
