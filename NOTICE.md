# Attribution and licensing

This project is a **derivative work**: it converts the figure-making approach of
[figures4papers](https://github.com/ChenLiu-1996/figures4papers) by
Chen Liu (Yale University) from scientific paper figures to football data
visualisation.

## Upstream

`figures4papers` is licensed **Creative Commons
Attribution-NonCommercial 4.0 International (CC BY-NC 4.0)**.

Its full text is in [`LICENSE`](LICENSE), carried over unchanged.

### What was taken from it

- The **organisational structure**: a skill package with `SKILL.md` plus a
  `references/` set (`api.md`, `design-theory.md`, `common-patterns.md`,
  `tutorials.md`, `demos.md`), alongside `figure_*`-style per-topic projects.
- The **design system**: minimalist spines, frameless legends, explicit y-limits,
  dedicated legend panels, direct in-place annotation, print-safe encoding, and
  the `dpi=300` PNG + vector PDF export policy.
- Part of the **palette**. In particular the anchor blue `#0F4D92` and the
  green/red/neutral families are the upstream values, because the visual lineage
  is the point of the conversion.
- The **`make_*` helper naming and signatures**, adapted from numeric plots to
  football ones.

### What is new here

- All football-specific code: pitch geometry and drawing, event data layer,
  metric definitions, and the seven figure families.
- `ROLE` colour semantics (attack/defend/success/failure), which replaces the
  upstream method-based semantics. See
  [`references/design-theory.md`](football-data-visualisation/references/design-theory.md) §2.
- The pitch-control, Voronoi, xThreat, and pressure implementations.

## Because of the non-commercial clause

The CC BY-NC 4.0 terms apply to the derived style system and structure. **If you
intend to use this commercially** — for a club, a broadcaster, a betting product,
or any paid service — review the upstream licence first and contact the upstream
author, or replace the derived style system with your own design.

The football analysis code is independently written and can be reused on its own
terms, but it carries the same inherited non-commercial obligation as long as the
derived visual style travels with it.

## Data

Figures use **StatsBomb open data**, free for research and public use under the
StatsBomb Public Data User Agreement. Attribution is required:

> Data provided by StatsBomb — https://statsbomb.com/what-we-do/hub/free-data/

The data is downloaded into `data/cache/` and is deliberately not committed.

## Models

The pitch-control surface is a stylised reimplementation inspired by:

- Spearman, W. (2018). *Beyond Expected Goals.* Journal of Sports Analytics.
- Singh, K. *Introducing Expected Threat (xT).* https://karun.in/blog/expected-threat.html

The xThreat surface here is a hand-built 12 × 8 grid, **not** the authors' fitted
model, and is labelled as stylised throughout the code and documentation. The
pitch-control constants are tuned to look right on broadcast frames and are not
validated against tracking ground truth.
