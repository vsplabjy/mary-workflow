# Mary Marp Asset Contract

P4 vendors the ShanghaiTech red presentation base into `assets/marp/`; P5 consumes it for the contract-validated paper `slides` stage.

## Asset Layout

| Path | Purpose |
| --- | --- |
| `themes/mary-shanghaitech-red.source.css` | Maintainable localized VSP-Marp CSS with relative asset references |
| `themes/mary-shanghaitech-red.css` | Generated self-contained theme used by VS Code and Marp CLI |
| `backgrounds/` | ShanghaiTech 16:9 master background |
| `logos/` | ShanghaiTech mark and name artwork used by the theme |
| `fonts/latin-modern/` | Latin display, body, and monospace fonts |
| `fonts/noto-cjk-sc/` | Complete Simplified Chinese regular and bold web fonts |
| `fonts/katex/` | KaTeX 0.16.45 WOFF2 font set |
| `marp-engine.cjs` | Forces KaTeX to resolve fonts from the local asset tree |
| `marp.config.mjs` | Registers the theme, engine, and local-file access |
| `templates/offline-preview.md` | P4 smoke deck for Chinese, background, logo, and formula rendering |
| `.vscode/settings.json` | Registers the local theme for every Markdown file in this workspace |

The CSS header records the exact upstream commit. There is intentionally no `VENDOR.md`. The current integration is private-use and risk-accepted; perform a complete license and trademark review before public distribution.

## Invariants

1. Keep every source-theme URL relative; reject HTTP(S), protocol-relative, and escaping URLs.
2. Resolve every source-theme `url(...)` from the theme directory to an existing repository file.
3. Generate the runtime CSS deterministically with every asset embedded as a `data:` URL.
4. Register that compiled CSS in the workspace-level `markdown.marp.themes` setting.
5. Keep all 20 KaTeX WOFF2 files and both complete Noto CJK SC weights.
6. Keep `math: katex` explicit in slide front matter.
7. Resolve the registered theme from the workspace root so Markdown can live in any workspace subdirectory.
8. Do not modify or depend on the ignored `vsp-marp/` checkout at runtime.

P5 adds the `.figure-placeholder`, `.figure-placeholder__number`, and `.figure-placeholder__caption` styles to the localized theme while retaining the pinned P4 source and deterministic self-contained build.

## Validation

Run the deterministic asset check:

```bash
python scripts/validate_marp_assets.py
```

After changing the source theme or any referenced asset, rebuild and verify the self-contained CSS:

```bash
python scripts/build_marp_theme.py
python scripts/build_marp_theme.py --check
```

After Marp CLI 4.3.1 has been cached or installed, compile the offline HTML preview. The input and output may be outside `assets/marp/` because the registered theme is self-contained:

```bash
npm_config_offline=true npx --yes @marp-team/marp-cli@4.3.1 \
  --config-file assets/marp/marp.config.mjs \
  assets/marp/templates/offline-preview.md \
  --output assets/marp/templates/offline-preview.html
```

For visual acceptance, render PNG pages with the same config and inspect the cover, formula page, and ShanghaiTech table-of-contents page. Generated HTML and PNG files are test output, not vendored assets.
