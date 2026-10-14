# Figures for Football

A **football data-visualisation skill and figure library** — a conversion of
[ChenLiu-1996/figures4papers](https://github.com/ChenLiu-1996/figures4papers)
from scientific paper figures into football analytics figures, built on real
[StatsBomb open data](https://github.com/statsbomb/open-data).

Where the source repo answered *"show that my method beats the baseline"*, this
repo answers *"show me how this team plays, and what to change."*

Data provided by **StatsBomb**.

---

## The idea

A visual guide to improving football. Every figure is meant to be readable by a
coach, not just a modeller: a shot map that explains *why* a team underperforms
its xG, a pass network that shows where the ball gets stuck, a pressure map that
shows which zone a press breaks down in.

## What's here

```
football-data-visualisation/
├── SKILL.md                        # when to use, patterns, quick reference
├── references/
│   ├── api.md                      # PALETTE, ROLE, PitchStyle, helper signatures
│   ├── design-theory.md            # why the football style looks the way it does
│   ├── common-patterns.md          # 12 reusable football figure patterns
│   ├── tutorials.md                # end-to-end walkthroughs
│   └── demos.md                    # the fig_* projects, with what each proves
└── scripts/
    ├── fetch_statsbomb.py          # download the open-data cache
    ├── sb_data.py                  # data layer (Dataset, Match, Shot, Pass, Frame)
    ├── football_style.py           # house style + pitch drawing + make_* helpers
    ├── pitch_control.py            # Voronoi + Spearman pitch control, pressure
    ├── metrics.py                  # per-player / per-team metrics, momentum
    └── selftest.py                 # end-to-end engine check

fig_shooting/      shot maps, goal-mouth plots, shot-quality grids
fig_passing/       pass networks, progressive flow fields, passing sonars
fig_defending/     pressure maps, PPDA trade-off, high turnovers
fig_territory/     zone occupancy, field tilt, progressive carries
fig_comparison/    percentile radars, percentile bars, similarity
fig_trends/        xG race, momentum, rolling form
fig_tracking/      pitch control and Voronoi (360 freeze-frames)

run_all.sh         regenerate every figure, then run the self-test
```

19 figures across seven metric families, each exported as PNG (300 dpi) and PDF.

## Quick start

```bash
# 1. environment
python3 -m venv .venv
.venv/bin/pip install numpy pandas matplotlib scipy

# 2. data (StatsBomb open data, no API key; ~1.8 GB for the full core set)
.venv/bin/python football-data-visualisation/scripts/fetch_statsbomb.py --core

# 3. everything
./run_all.sh

# or one family
.venv/bin/python fig_shooting/plot_shot_map.py
```

Every script writes `figures/*.png` and `figures/*.pdf` at 300 dpi.

## Reading order

If you are new here, read in this order:

1. `football-data-visualisation/references/design-theory.md` — the visual grammar
2. `football-data-visualisation/references/api.md` — the vocabulary
3. `fig_shooting/plot_shot_map.py` — the simplest complete figure
4. `fig_tracking/plot_pitch_control.py` — the most advanced one

If you are an AI agent, start at `football-data-visualisation/SKILL.md`.

## Using this as an AI agent skill

Point your agent at `football-data-visualisation/SKILL.md` and it has the house
style, the helper API, and worked examples. Or symlink it:

```bash
ln -s "$(pwd)/football-data-visualisation" ~/.claude/skills/football-data-visualisation
```

## Attribution

Figures use StatsBomb open data, free for research and public use under the
StatsBomb Public Data User Agreement.

> Data provided by StatsBomb — https://statsbomb.com/what-we-do/hub/free-data/

Pitch-control and xThreat implementations are stylised reimplementations
inspired by Spearman (2018) and Karun Singh's xT. They are labelled as such in
the code and are not the authors' original models.

Style system and repository structure converted from
[figures4papers](https://github.com/ChenLiu-1996/figures4papers) by Chen Liu,
which is licensed **CC BY-NC 4.0** (see `LICENSE`). Because that licence is
non-commercial, **review [`NOTICE.md`](NOTICE.md) before any commercial use.**
