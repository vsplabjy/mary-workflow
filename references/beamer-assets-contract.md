# Mary Beamer Asset Contract

P5 vendors the ShanghaiTech red VSP-Beamer presentation base into `assets/beamer/` and consumes it only when the selected paper-slide backend is `beamer`. The Marp supply and the independent Hypoxanthine-LaTeX comparison keep their existing roles.

## Asset Layout

| Path | Purpose |
| --- | --- |
| `mary-paper.tex` | Loads the ShanghaiTech theme and defines native paper Figure and layout helpers |
| `themes/beamerthemeVSP.sty` | Localized VSP-Beamer core typography and layout |
| `themes/beamerthemetutorial-red-shtu.sty` | ShanghaiTech red theme selector |
| `images/shanghaitech-master.png` | ShanghaiTech 16:9 background |
| `images/ShanghaiTech_Logo_RGBA.png` | ShanghaiTech mark |
| `images/ShanghaiTech_Name_RGBA.png` | ShanghaiTech name artwork |
| `slides-template.tex` | Native TeX authoring starting point, requiring current paper metadata and claims |
| `LICENSE` | Included upstream code license |
| `THIRD_PARTY_ASSETS.md` | VSP provenance and separate media ownership notices |
| `<paper-workspace>/beamer/` | P5-deployed support bundle; does not depend on the reference checkout |

## Invariants

1. Preserve ShanghaiTech red, 16:9, Latin Modern Western text, Noto CJK SC Chinese text, and native LaTeX math. Font packages are installed locally; themes and paper images never load remote resources.
2. Compile with GNU Make, latexmk, and XeLaTeX. Ubuntu/Debian dependencies are `make latexmk texlive-xetex texlive-latex-extra texlive-lang-chinese texlive-fonts-recommended fonts-noto-cjk`; the Chinese language package provides CTEX and brings in xeCJK. This runtime does not require Node.js or Marp CLI for Beamer production.
3. Keep theme styling and helper definitions in the deployed support; `slides.tex` remains semantic native Beamer. The source includes only `beamer/mary-paper.tex`, starts with `\VSPtitleframe`, uses explicit frames, and ends with `\VSPendframe{...}`.
4. Preserve the current bundle fingerprint in `artifacts/slides-context.json`. Lint checks theme integrity along with the selected backend, source path, and summary lineage. Change the vendored supply through repository code; never hand-edit generated context to accept a modified bundle.
5. Keep actual page count explicit. The localized theme disables automatic section pages; source overlays, split frames, shrinking, extra includes, and custom macro definitions cannot bypass the shared paper-slide lint.
6. Use `\MaryFigure{<id>}{<locator>}{<caption>}{<path>}` for catalogued paper Figures. Its local asset uses `keepaspectratio`; do not distort, crop, download, or fabricate paper evidence. Leave the path empty only when no materialized asset exists.
7. Use native `columns` with at least two columns or `\MaryColumns`, `\MaryRows`, and `\MaryPinThree` for the same multi-panel content requirements as Marp. Do not relax narrative, claim, caption, Figure, local-media, closing-page, or capacity gates for TeX.
8. Keep generated exports under `build/`. Default delivery is editable `slides.tex` with its support. `make slide` creates `build/slides.pdf`; temporary compile smoke is optional and produces no persistent delivery. Do not promise an editable PPTX from Beamer.
9. Preserve upstream license/provenance records. ShanghaiTech logos, names and background media retain their own ownership; the theme code license does not transfer media or trademark rights.
10. Do not modify or depend on the local `vsp-beamer/` reference checkout at runtime. Preparation deploys the vendored supply into the paper workspace, so the generated deck remains independent of the Mary checkout location.

Read `references/slides-contract.md` for native preamble, frame metadata, Figure syntax, and the shared research-deck completion gate. `make hypo-template` remains an isolated original-template comparison and never substitutes for `slides.tex`.
