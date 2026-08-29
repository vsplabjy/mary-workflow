# Mary Beamer Asset Contract

P5 vendors a minimal VSP-Beamer runtime under `assets/beamer/` and deploys an
identical project-local copy during `prepare-slides`.

## Runtime Layout

| Path | Purpose |
| --- | --- |
| `themes/beamerthemeVSP.sty` | Pinned shared VSP-Beamer implementation |
| `themes/beamerthememary-shanghaitech-red.sty` | Mary red/report/SHTU entry and `\MaryFigure` API |
| `assets/shanghaitech-master.png` | 16:9 ShanghaiTech background |
| `assets/ShanghaiTech_Logo_RGBA.png` | Cover logo |
| `assets/ShanghaiTech_Name_RGBA.png` | ShanghaiTech wordmark |
| `templates/offline-preview.tex` | Chinese, formula, columns, cover, and closing smoke deck |
| `LICENSE.vsp-beamer` | Upstream MIT license retained with the vendored code |
| `<target>/.mary-research/beamer/` | Deployed runtime for independent paper workspaces |

The shared theme and brand assets come from `Heaticy/vsp-beamer` commit
`e7bf4e5e5588ee10a386e6c79668e50f9b749124`. Keep that provenance in the Mary
entry theme. Upstream code is MIT-licensed; ShanghaiTech marks remain third-party
assets and are not relicensed by Mary Workflow.

## Invariants

1. Support Linux only, with Ubuntu/Debian as the validated baseline.
2. Use GNU Make, `latexmk`, and XeLaTeX. Do not add pdfLaTeX fallbacks.
3. Use TeX Live Latin Modern and system Noto CJK SC; do not vendor web fonts.
4. Keep all runtime and paper images local. Do not add HTTP(S) dependencies.
5. Preserve the shared theme as a pinned upstream snapshot; put Mary-specific
   behavior in the thin `beamerthememary-shanghaitech-red.sty` entry.
6. Deploy and fingerprint the complete runtime bundle, not one isolated `.sty`.
7. Resolve themes/assets through `TEXINPUTS`; never hardcode plugin checkout paths
   into `slides.tex`.
8. Keep editable `slides.tex` semantic and keep reusable typography/layout in the
   theme.

## Validation

Run the deterministic bundle check:

```bash
python scripts/validate_beamer_assets.py
```

Compile the offline preview:

```bash
TEXINPUTS="$(pwd)/assets/beamer/themes//:$(pwd)/assets/beamer/assets//:" \
  latexmk -xelatex -interaction=nonstopmode -halt-on-error \
  -outdir=/tmp/mary-beamer-preview assets/beamer/templates/offline-preview.tex
```

After changing the shared theme or runtime assets, run the full test suite and a
real `complete-slides` path. Inspect the rendered PDF pages, not only the TeX
source or successful exit status.
