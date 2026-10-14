"""Per-player and per-team metric aggregation from StatsBomb event streams.

Design goal: every metric a demo figure plots is produced here, with its
definition written down. That keeps "what does this number mean" answerable
without reading the plotting code.

Definitions used (documented so figures can carry them in captions):

xG            Sum of StatsBomb's ``statsbomb_xg`` for shots taken.
npxG          xG excluding penalty kicks.
xT            Stylised expected threat of a pass (see :mod:`sb_data.xthreat`).
Progressive   A pass or carry that advances the ball >= 10 yards up-pitch while
              starting in the team's own 80 yards (carries use a 5-yard gate).
Line-breaking A pass advancing >= 20 yards up-pitch.
Packing       Number of opponents bypassed by a pass (opponents positioned
              between the pass start and end, within the pass corridor).
PPDA          Opponent passes allowed per defensive action, in the opponent's
              defensive half - lower means more aggressive pressing.
Pressure rate Share of a team's defensive actions that are pressures.
Field tilt    Share of final-third touches/events belonging to each team.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field

import numpy as np

from sb_data import Dataset, Match, Pass, Shot, xthreat


# --------------------------------------------------------------------------- #
# Packing / bypassed opponents
# --------------------------------------------------------------------------- #
def opponents_bypassed(p: Pass, opponent_positions: np.ndarray) -> int:
    """Count opponents inside the trapezoid/corridor between pass start and end."""
    opps = np.asarray(opponent_positions, dtype=float).reshape(-1, 2)
    if len(opps) == 0:
        return 0
    start = np.array([p.x, p.y])
    end = np.array([p.end_x, p.end_y])
    # Exclude opponents behind the pass origin - only bypassed ones count.
    if end[0] - start[0] < 25.0:
        return 0
    t = (opps[:, 0] - start[0]) / (end[0] - start[0] + 1e-9)
    inside_x = (t > 0.05) & (t < 0.95)
    corridor_y = start[1] + t * (end[1] - start[1])
    inside_y = np.abs(opps[:, 1] - corridor_y) < 9.0
    return int(np.sum(inside_x & inside_y))


# --------------------------------------------------------------------------- #
# Player metrics
# --------------------------------------------------------------------------- #
@dataclass
class PlayerMetrics:
    """Every per-player number a demo figure needs."""

    player: str
    team: str
    minutes: float = 0.0
    # shooting
    shots: int = 0
    goals: int = 0
    xg: float = 0.0
    npxg: float = 0.0
    # passing
    passes: int = 0
    passes_completed: int = 0
    progressive_passes: int = 0
    line_breaking_passes: int = 0
    key_passes: int = 0
    assists: int = 0
    xt: float = 0.0
    packing: int = 0
    progressive_carries: int = 0
    carry_distance: float = 0.0
    # defending
    pressures: int = 0
    interceptions: int = 0
    blocks: int = 0
    clearances: int = 0
    recoveries: int = 0
    duels: int = 0
    duels_won: int = 0
    # territory
    touches_final_third: int = 0
    touches_box: int = 0
    # passing network
    pass_links: Counter = field(default_factory=Counter)

    @property
    def pass_completion(self) -> float:
        return self.passes_completed / self.passes if self.passes else 0.0

    @property
    def xg_per_shot(self) -> float:
        return self.xg / self.shots if self.shots else 0.0

    @property
    def goals_minus_xg(self) -> float:
        return self.goals - self.xg

    @property
    def per90(self) -> float:
        return 90.0 / self.minutes if self.minutes > 0 else 0.0

    def rate(self, value: float) -> float:
        return value * self.per90


def _minutes_played(ds: Dataset, match: Match, player: str) -> float:
    """Minutes on pitch, from Starting XI positions and substitution events.

    StatsBomb reports ``substitution.replacement`` as a single object (not a
    list), so both shapes are handled.
    """
    start_min, end_min = 0.0, 90.0
    started = False
    for ev in match.raw_events:
        t = ev.get("type", {}).get("name")
        if t == "Starting XI" and ev.get("tactics"):
            for p in ev["tactics"].get("lineup", []):
                if p.get("player", {}).get("name") == player:
                    started = True
        if t == "Substitution":
            if ev.get("player", {}).get("name") == player:
                end_min = float(ev.get("minute", 90))
            rep = ev.get("substitution", {}).get("replacement")
            reps = rep if isinstance(rep, list) else ([rep] if rep else [])
            for r in reps:
                if isinstance(r, dict) and r.get("name") == player:
                    start_min = float(ev.get("minute", 0))
    if not started and start_min == 0.0:
        start_min = 0.0
    return max(end_min - start_min, 1.0)


def player_metrics(ds: Dataset, match: Match, team: str | None = None) -> dict[str, PlayerMetrics]:
    """Aggregate every :class:`PlayerMetrics` field for one match."""
    teams = [team] if team else list(match.teams)
    out: dict[str, PlayerMetrics] = {}

    for tname in teams:
        # --- shots ------------------------------------------------------- #
        for s in ds.shots(match, tname):
            m = out.setdefault(s.player, PlayerMetrics(player=s.player, team=tname))
            m.shots += 1
            m.xg += s.xg
            if "Penalty" not in s.technique and s.play_pattern != "Penalty":
                m.npxg += s.xg
            if s.is_goal:
                m.goals += 1

        # --- passes ------------------------------------------------------ #
        opp_positions = _team_positions(match, [t for t in match.teams if t != tname])
        for p in ds.passes(match, tname):
            m = out.setdefault(p.player, PlayerMetrics(player=p.player, team=tname))
            m.passes += 1
            if p.completed:
                m.passes_completed += 1
                if p.recipient:
                    m.pass_links[p.recipient] += 1
            if p.is_progressive:
                m.progressive_passes += 1
            if p.is_line_breaking:
                m.line_breaking_passes += 1
            gain = max(0.0, xthreat(p.end_x, p.end_y) - xthreat(p.x, p.y))
            if p.completed:
                m.xt += gain
                if p.end_x >= 102.0:  # pass into the box
                    m.key_passes += 1
            m.packing += opponents_bypassed(p, opp_positions.get(int(p.minute), np.empty((0, 2))))

        # --- carries ----------------------------------------------------- #
        for c in ds.carries(match, tname):
            m = out.setdefault(c.player, PlayerMetrics(player=c.player, team=tname))
            m.carry_distance += c.distance
            if c.is_progressive:
                m.progressive_carries += 1

        # --- defensive actions ------------------------------------------- #
        for d in ds.defensive_actions(match, tname):
            m = out.setdefault(d.player, PlayerMetrics(player=d.player, team=tname))
            if d.kind == "pressure":
                m.pressures += 1
            elif d.kind == "interception":
                m.interceptions += 1
            elif d.kind == "block":
                m.blocks += 1
            elif d.kind == "clearance":
                m.clearances += 1
            elif d.kind == "recovery":
                m.recoveries += 1
            elif d.kind == "duel":
                m.duels += 1
                if d.success:
                    m.duels_won += 1

        # --- territory touches ------------------------------------------- #
        for ev in match.raw_events:
            if ev.get("type", {}).get("name") not in {"Pass", "Carry", "Shot", "Dribble", "Ball Receipt*"}:
                continue
            if ev.get("team", {}).get("name") != tname:
                continue
            pname = ev.get("player", {}).get("name")
            if not pname:
                continue
            loc = ds._oriented(ev, match)
            if loc is None:
                continue
            m = out.setdefault(pname, PlayerMetrics(player=pname, team=tname))
            if loc[0] >= 80.0:
                m.touches_final_third += 1
            if loc[0] >= 102.0 and 18.0 <= loc[1] <= 62.0:
                m.touches_box += 1

    for m in out.values():
        m.minutes = _minutes_played(ds, match, m.player)
    return out


def _team_positions(match: Match, teams: list[str]) -> dict[int, np.ndarray]:
    """Opponent positions by minute, used for the packing metric."""
    by_min: dict[int, list] = defaultdict(list)
    for ev in match.raw_events:
        if ev.get("team", {}).get("name") not in teams:
            continue
        loc = ev.get("location")
        if loc:
            by_min[int(ev.get("minute", 0))].append(loc[:2])
    return {k: np.array(v, dtype=float) for k, v in by_min.items()}


# --------------------------------------------------------------------------- #
# Team metrics
# --------------------------------------------------------------------------- #
@dataclass
class TeamMetrics:
    team: str
    goals: int = 0
    xg: float = 0.0
    shots: int = 0
    passes: int = 0
    passes_completed: int = 0
    progressive_passes: int = 0
    final_third_entries: int = 0
    box_entries: int = 0
    xt: float = 0.0
    def_actions: int = 0
    pressures: int = 0
    high_turnovers: int = 0
    opponent_passes: int = 0

    @property
    def pass_completion(self) -> float:
        return self.passes_completed / self.passes if self.passes else 0.0

    @property
    def ppda(self) -> float:
        return self.opponent_passes / self.def_actions if self.def_actions else np.nan


def team_metrics(ds: Dataset, match: Match) -> dict[str, TeamMetrics]:
    """Aggregate :class:`TeamMetrics` for both teams in a match."""
    out: dict[str, TeamMetrics] = {t: TeamMetrics(team=t) for t in match.teams}

    for tname in match.teams:
        tm = out[tname]
        for s in ds.shots(match, tname):
            tm.shots += 1
            tm.xg += s.xg
            if s.is_goal:
                tm.goals += 1

        passes = ds.passes(match, tname)
        tm.passes = len(passes)
        tm.passes_completed = sum(p.completed for p in passes)
        tm.progressive_passes = sum(p.is_progressive for p in passes)
        tm.xt = sum(max(0.0, xthreat(p.end_x, p.end_y) - xthreat(p.x, p.y)) for p in passes if p.completed)
        tm.final_third_entries = sum(1 for p in passes if p.completed and p.x < 80.0 <= p.end_x)
        tm.box_entries = sum(1 for p in passes if p.completed and p.x < 102.0 <= p.end_x)

        acts = ds.defensive_actions(match, tname)
        tm.def_actions = len(acts)
        tm.pressures = sum(a.kind == "pressure" for a in acts)
        tm.high_turnovers = sum(
            a.kind in {"interception", "recovery"} and a.x >= 60.0 for a in acts
        )

    # PPDA needs each team's passes counted from the opponent's perspective.
    for tname in match.teams:
        other = [t for t in match.teams if t != tname][0]
        out[tname].opponent_passes = out[other].passes

    return out


#: Event types counted as a "touch" for territorial metrics. Sharing this
#: constant across field_tilt, zone_occupancy, and the figures is what keeps
#: "attacking-half touches" meaning one thing rather than three.
TOUCH_EVENT_TYPES = frozenset(
    {"Pass", "Carry", "Shot", "Dribble", "Ball Receipt*"}
)


def _touch_events(ds: Dataset, match: Match, team: str):
    """Yield oriented locations of every touch by ``team``."""
    for ev in match.raw_events:
        if ev.get("type", {}).get("name") not in TOUCH_EVENT_TYPES:
            continue
        if ev.get("team", {}).get("name") != team:
            continue
        loc = ds._oriented(ev, match)
        if loc is not None:
            yield loc


def field_tilt(ds: Dataset, match: Match) -> dict[str, float]:
    """Share of attacking-half touches per team (sums to 1.0)."""
    counts = Counter()
    for tname in match.teams:
        counts[tname] = sum(1 for loc in _touch_events(ds, match, tname) if loc[0] >= 60.0)
    total = sum(counts.values()) or 1
    return {k: v / total for k, v in counts.items()}


def attacking_half_touches(ds: Dataset, match: Match) -> dict[str, int]:
    """Raw attacking-half touch counts, on the same definition as ``field_tilt``."""
    return {t: sum(1 for loc in _touch_events(ds, match, t) if loc[0] >= 60.0)
            for t in match.teams}


def zone_occupancy(ds: Dataset, match: Match, team: str, n_x: int = 6, n_y: int = 4) -> np.ndarray:
    """Touch counts in a 6x4 grid over the attacking half, oriented per team."""
    grid = np.zeros((n_y, n_x))
    for loc in _touch_events(ds, match, team):
        if loc[0] < 60.0:
            continue
        i = min(n_x - 1, max(0, int((loc[0] - 60.0) / 60.0 * n_x)))
        j = min(n_y - 1, max(0, int(loc[1] / 80.0 * n_y)))
        grid[j, i] += 1
    return grid


def xg_race(ds: Dataset, match: Match) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    """Cumulative xG over match minutes for each team: {team: (minutes, cum_xg)}."""
    out = {}
    for tname in match.teams:
        shots = sorted(ds.shots(match, tname), key=lambda s: s.minute)
        mins = [0] + [s.minute for s in shots]
        cum = [0.0]
        for s in shots:
            cum.append(cum[-1] + s.xg)
        out[tname] = (np.array(mins, dtype=float), np.array(cum, dtype=float))
    return out


def rolling_form(ds: Dataset, match_ids: list[int], team: str, window: int = 5) -> dict:
    """Rolling xG / xGA / points across a sequence of matches.

    Used by the season-trend figures; matches are treated in the order given.
    """
    xg, xga, pts, labels = [], [], [], []
    for mid in match_ids:
        m = ds.match(mid)
        if team not in m.teams:
            continue
        tm = team_metrics(ds, m)
        other = [t for t in m.teams if t != team][0]
        xg.append(tm[team].xg)
        xga.append(tm[other].xg)
        gf, ga = tm[team].goals, tm[other].goals
        pts.append(3 if gf > ga else (1 if gf == ga else 0))
        labels.append(f"{m.home[:3]}-{m.away[:3]}")

    def roll(a):
        a = np.asarray(a, dtype=float)
        if len(a) < window:
            return a
        return np.convolve(a, np.ones(window) / window, mode="valid")

    return {
        "labels": labels, "xg": np.array(xg), "xga": np.array(xga), "points": np.array(pts),
        "xg_roll": roll(xg), "xga_roll": roll(xga), "window": window,
    }


def momentum(ds: Dataset, match: Match, bin_minutes: int = 5) -> dict[str, np.ndarray]:
    """Per-bin territorial momentum.

    Score per bin = (final-third entries + 2 * box entries + 3 * shots + 2 * xG)
    differential. Positive favours the home team.
    """
    home, away = match.teams
    nbins = int(np.ceil(95 / bin_minutes))
    h = np.zeros(nbins)
    a = np.zeros(nbins)
    for tname, arr in ((home, h), (away, a)):
        for p in ds.passes(match, tname):
            if p.completed and p.end_x >= 80.0:
                arr[min(nbins - 1, p.minute // bin_minutes)] += 1.0
            if p.completed and p.end_x >= 102.0:
                arr[min(nbins - 1, p.minute // bin_minutes)] += 2.0
        for s in ds.shots(match, tname):
            arr[min(nbins - 1, s.minute // bin_minutes)] += 3.0 + 2.0 * s.xg
    return {
        "bins": np.arange(nbins) * bin_minutes + bin_minutes / 2,
        "home": h, "away": a, "net": h - a, "home_team": home, "away_team": away,
    }
