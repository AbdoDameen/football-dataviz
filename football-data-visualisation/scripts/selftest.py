"""Smoke test: exercise the whole engine against real cached StatsBomb data.

    python football-data-visualisation/scripts/selftest.py

Exits non-zero on the first failure so it can be used as a CI gate.
"""

from __future__ import annotations

import sys
import time
import traceback
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

import football_style as fs  # noqa: E402
from metrics import momentum, player_metrics, team_metrics, xg_race  # noqa: E402
from pitch_control import spearman_control, voronoi_control  # noqa: E402
from sb_data import Dataset  # noqa: E402

FAILURES: list[str] = []


def check(name: str, fn):
    t0 = time.time()
    try:
        result = fn()
        dt = time.time() - t0
        print(f"  PASS  {name:<48} {dt:6.2f}s")
        return result
    except Exception as exc:  # noqa: BLE001
        dt = time.time() - t0
        print(f"  FAIL  {name:<48} {dt:6.2f}s  {type(exc).__name__}: {exc}")
        traceback.print_exc()
        FAILURES.append(name)
        return None


def main() -> int:
    style = fs.apply_pitch_style()
    print(f"style: font={style.font_size} pitch={style.pitch_color}")

    ds = Dataset.load()
    ids = ds.cached_match_ids()
    print(f"cached matches: {len(ids)}")
    if not ids:
        print("No cached matches. Run fetch_statsbomb.py --core first.")
        return 2

    # Prefer the World Cup final if present, else the first cached match.
    mid = 3869685 if 3869685 in ids else ids[0]
    match = check(f"load match {mid}", lambda: ds.match(mid))
    if match is None:
        return 1
    print(f"        {match.scoreline}  ({match.competition} {match.season})")

    shots = check("extract shots", lambda: ds.shots(match))
    passes = check("extract passes", lambda: ds.passes(match))
    carries = check("extract carries", lambda: ds.carries(match))
    defs = check("extract defensive actions", lambda: ds.defensive_actions(match))
    frames = check("extract 360 frames", lambda: ds.frames(match))

    if shots:
        total_xg = sum(s.xg for s in shots)
        goals = sum(s.is_goal for s in shots)
        print(f"        shots={len(shots)} goals={goals} total_xG={total_xg:.2f}")
        assert 5 <= goals <= 8, f"unexpected goal count {goals}"
        assert 0.5 < total_xg < 8.0, f"implausible total xG {total_xg}"
        # Orientation: every shot must be in the attacking half after flipping.
        assert min(s.x for s in shots) > 40, "orientation flip failed for shots"

    if passes:
        prog = sum(p.is_progressive for p in passes)
        print(f"        passes={len(passes)} progressive={prog} "
              f"completion={sum(p.completed for p in passes)/len(passes):.1%}")

    check("player metrics", lambda: player_metrics(ds, match))
    check("team metrics", lambda: team_metrics(ds, match))
    check("xg race", lambda: xg_race(ds, match))
    check("momentum", lambda: momentum(ds, match))

    # --- pitch control ----------------------------------------------------- #
    if frames:
        with_players = [f for f in frames if len(f.teammates) + len(f.opponents) >= 8]
        print(f"        frames={len(frames)} usable(>=8 players)={len(with_players)}")
        if with_players:
            frame = max(with_players, key=lambda f: len(f.opponents))
            ctrl, known = check(
                "voronoi control",
                lambda: voronoi_control(frame.teammates, frame.opponents, resolution=90),
            )
            if ctrl is not None:
                assert ctrl.shape == (90, 90) == known.shape
                mate_share = float(np.mean(ctrl[known]))
                print(f"        teammate share of known pitch = {mate_share:.1%} "
                      f"(data covers {known.mean():.1%})")
                assert 0.15 < mate_share < 0.85, f"implausible teammate share {mate_share}"

            sc = check(
                "spearman control (res=60)",
                lambda: spearman_control(frame.teammates, frame.opponents,
                                         ball_xy=(frame.x, frame.y), resolution=60),
            )
            if sc is not None:
                control, coverage = sc
                assert control.shape == coverage.shape == (60, 60)
                assert 0.0 <= control.min() and control.max() <= 1.0
                spread = float(control[coverage].std()) if coverage.any() else 0.0
                print(f"        coverage {coverage.mean():.1%} of cells, "
                      f"control {control.min():.2f}-{control.max():.2f}, sd={spread:.3f}")
                # The surface must be spatially discriminating, not near-uniform.
                assert spread > 0.08, f"pitch control surface is flat (sd={spread:.3f})"

    # --- one figure end-to-end --------------------------------------------- #
    def render():
        import matplotlib.pyplot as plt
        fig, ax = fs.figure_with_pitch(figsize=(13, 9), show_third_lines=True)
        if shots:
            xs = [s.x for s in shots]
            ys = [s.y for s in shots]
            sizes = [60 + 900 * s.xg for s in shots]
            cols = [fs.ROLE["success"] if s.is_goal else fs.ROLE["attack"] for s in shots]
            ax.scatter(xs, ys, s=sizes, c=cols, alpha=0.85, edgecolor="black",
                       linewidth=0.8, zorder=5)
        fs.add_title(ax, "Engine self-test", match.scoreline)
        return fs.finalize_figure(fig, "/tmp/smoke/selftest_shotmap", formats=["png"], dpi=120)

    check("render + export PNG", render)

    print()
    if FAILURES:
        print(f"FAILED ({len(FAILURES)}): {', '.join(FAILURES)}")
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
