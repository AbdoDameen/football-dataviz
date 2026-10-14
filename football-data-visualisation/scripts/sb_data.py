"""Football data access layer over the StatsBomb open-data JSON cache.

Everything in this module is dependency-light (stdlib + numpy) so the figure code
stays portable. Coordinates are normalised to a **single attacking direction**
(team always attacks left-to-right) and kept in StatsBomb's 120x80 yard pitch
space, which is what every pitch helper in :mod:`football_style` draws into.

    from sb_data import Dataset
    ds = Dataset.load()
    final = ds.match(3869685)
    shots = ds.shots(final)

Attribution: "Data provided by StatsBomb".
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "data" / "cache"

PITCH_LENGTH = 120.0
PITCH_WIDTH = 80.0

#: Goal centre and geometry in StatsBomb coordinates (120x80).
GOAL_CENTRE = np.array([120.0, 40.0])
GOAL_HALF_WIDTH = 4.0  # 8-yard goal
GOAL_HEIGHT = 2.67  # metres, for goal-mouth plots


# --------------------------------------------------------------------------- #
# Small helpers
# --------------------------------------------------------------------------- #
def _nested(d: dict | None, *keys: str, default=None):
    """Walk nested dicts: ``_nested(ev, 'shot', 'statsbomb_xg')``."""
    cur = d
    for k in keys:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur


def _loc(ev: dict) -> np.ndarray | None:
    loc = ev.get("location")
    if not loc:
        return None
    return np.array([float(loc[0]), float(loc[1])])


def is_shootout(ev: dict) -> bool:
    """True for penalty-shootout events, which must not count as goals or xG.

    StatsBomb flags shootout attempts with ``period == 5``; they inflate goal
    counts and carry a flat 0.78 xG that distorts team totals.
    """
    return int(ev.get("period", 0)) >= 5


def mirror(points: np.ndarray) -> np.ndarray:
    """Flip StatsBomb coords to the opposite attacking direction."""
    pts = np.atleast_2d(np.asarray(points, dtype=float))
    return np.column_stack([PITCH_LENGTH - pts[:, 0], PITCH_WIDTH - pts[:, 1]])


# --------------------------------------------------------------------------- #
# Records
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Shot:
    """One shot, normalised so the shooter always attacks left-to-right."""

    match_id: int
    team: str
    player: str
    x: float
    y: float
    xg: float
    outcome: str
    body_part: str
    technique: str
    minute: int
    end_x: float | None = None
    end_y: float | None = None
    end_z: float | None = None
    first_time: bool = False
    under_pressure: bool = False
    play_pattern: str = ""

    @property
    def is_goal(self) -> bool:
        return self.outcome.lower() in {"goal", "won"}

    @property
    def distance(self) -> float:
        return float(np.hypot(self.x - GOAL_CENTRE[0], self.y - GOAL_CENTRE[1]))

    @property
    def angle(self) -> float:
        """Opening angle subtended by the goal posts, in degrees."""
        a = np.array([GOAL_CENTRE[0], GOAL_CENTRE[1] - GOAL_HALF_WIDTH]) - np.array([self.x, self.y])
        b = np.array([GOAL_CENTRE[0], GOAL_CENTRE[1] + GOAL_HALF_WIDTH]) - np.array([self.x, self.y])
        cosang = float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))
        return math.degrees(math.acos(max(-1.0, min(1.0, cosang))))


@dataclass(frozen=True)
class Pass:
    """One pass with its origin, destination, and progression value."""

    match_id: int
    team: str
    player: str
    recipient: str | None
    x: float
    y: float
    end_x: float
    end_y: float
    minute: int
    completed: bool
    pass_type: str
    height: str
    length: float = 0.0
    is_progressive: bool = False
    is_line_breaking: bool = False
    xthreat: float = 0.0
    under_pressure: bool = False

    def start(self) -> np.ndarray:
        return np.array([self.x, self.y])

    def end(self) -> np.ndarray:
        return np.array([self.end_x, self.end_y])


@dataclass(frozen=True)
class DefAction:
    """A defensive action: pressure, tackle, interception, block, clearance, duel."""

    match_id: int
    team: str
    player: str
    kind: str
    x: float
    y: float
    minute: int
    success: bool = True


@dataclass(frozen=True)
class Carry:
    """A ball carry (progressive if it advances the ball enough)."""

    match_id: int
    team: str
    player: str
    x: float
    y: float
    end_x: float
    end_y: float
    minute: int
    distance: float = 0.0
    is_progressive: bool = False


@dataclass(frozen=True)
class Frame:
    """A 360 freeze-frame: visible players at the moment of one event."""

    event_uuid: str
    x: float
    y: float
    teammates: np.ndarray
    opponents: np.ndarray
    actor: bool = False
    keeper: np.ndarray | None = None

    def all_players(self) -> np.ndarray:
        parts = [self.teammates, self.opponents]
        if self.keeper is not None and len(self.keeper):
            parts.append(self.keeper)
        return np.vstack([p for p in parts if len(p)])


@dataclass
class Match:
    """A single match: metadata plus normalised event streams."""

    match_id: int
    home: str
    away: str
    home_score: int
    away_score: int
    competition: str
    season: str
    date: str
    raw_events: list[dict] = field(default_factory=list)
    raw_frames: list[dict] = field(default_factory=list)
    _direction_cache: dict = field(default_factory=dict, repr=False, compare=False)

    @property
    def teams(self) -> tuple[str, str]:
        return (self.home, self.away)

    @property
    def scoreline(self) -> str:
        return f"{self.home} {self.home_score}-{self.away_score} {self.away}"

    def events_for(self, team: str) -> list[dict]:
        return [e for e in self.raw_events if _nested(e, "team", "name") == team]

    def attacking_direction(self, team: str) -> int:
        """+1 if ``team`` attacks toward x=120 for most of the match, else -1.

        Derived from shot locations, so it needs no hard-coded per-match
        knowledge. Cached: this is called once per event during extraction, and
        recomputing it would dominate runtime.
        """
        if team in self._direction_cache:
            return self._direction_cache[team]
        shots = [e for e in self.raw_events if e.get("type", {}).get("name") == "Shot"
                 and _nested(e, "team", "name", default="") == team
                 and not is_shootout(e)]
        if not shots:
            direction = 1
        else:
            xs = [_loc(e)[0] for e in shots if _loc(e) is not None]
            direction = 1 if float(np.mean(xs)) > PITCH_LENGTH / 2 else -1
        self._direction_cache[team] = direction
        return direction


# --------------------------------------------------------------------------- #
# Dataset
# --------------------------------------------------------------------------- #
class Dataset:
    """Lazy reader over the local StatsBomb cache."""

    def __init__(self, cache: Path = CACHE):
        self.cache = Path(cache)
        self._fixtures: dict[tuple[int, int], list[dict]] = {}
        self._matches: dict[int, Match] = {}

    # -- construction ------------------------------------------------------ #
    @classmethod
    def load(cls, cache: Path = CACHE) -> "Dataset":
        ds = cls(cache)
        if not (cache / "competitions.json").exists():
            raise FileNotFoundError(
                f"No StatsBomb cache at {cache}.\n"
                "Run:  python football-data-visualisation/scripts/fetch_statsbomb.py --core"
            )
        return ds

    # -- fixtures ---------------------------------------------------------- #
    def fixtures(self, competition_id: int, season_id: int) -> list[dict]:
        key = (competition_id, season_id)
        if key not in self._fixtures:
            path = self.cache / "matches" / str(competition_id) / f"{season_id}.json"
            self._fixtures[key] = json.loads(path.read_text()) if path.exists() else []
        return self._fixtures[key]

    def find_match(self, needle: str) -> dict | None:
        """Search every cached season for a fixture whose teams/include ``needle``.

        ``needle`` is matched case-insensitively against "Home vs Away".
        """
        needle = needle.lower()
        for (comp_id, season_id) in self._season_files():
            for m in self.fixtures(comp_id, season_id):
                home = m["home_team"]["home_team_name"]
                away = m["away_team"]["away_team_name"]
                if needle in f"{home} vs {away}".lower():
                    return m
        return None

    def _season_files(self) -> list[tuple[int, int]]:
        out = []
        base = self.cache / "matches"
        if not base.exists():
            return out
        for comp_dir in sorted(base.iterdir()):
            if not comp_dir.is_dir():
                continue
            for f in sorted(comp_dir.glob("*.json")):
                out.append((int(comp_dir.name), int(f.stem)))
        return out

    # -- matches ----------------------------------------------------------- #
    def cached_match_ids(self, with_frames: bool = True) -> list[int]:
        events = {int(p.stem) for p in (self.cache / "events").glob("*.json")}
        if not with_frames:
            return sorted(events)
        frames = {int(p.stem) for p in (self.cache / "three-sixty").glob("*.json")}
        return sorted(events & frames) or sorted(events)

    def match(self, match_id: int) -> Match:
        if match_id in self._matches:
            return self._matches[match_id]

        ev_path = self.cache / "events" / f"{match_id}.json"
        if not ev_path.exists():
            raise FileNotFoundError(
                f"events/{match_id}.json not cached. "
                f"Run:  python football-data-visualisation/scripts/fetch_statsbomb.py --matches {match_id}"
            )
        events = json.loads(ev_path.read_text())

        fr_path = self.cache / "three-sixty" / f"{match_id}.json"
        frames = json.loads(fr_path.read_text()) if fr_path.exists() else []

        meta = self._fixture_meta(match_id, events)
        m = Match(raw_events=events, raw_frames=frames, **meta)
        self._matches[match_id] = m
        return m

    def _fixture_meta(self, match_id: int, events: list[dict]) -> dict:
        for (comp_id, season_id) in self._season_files():
            for fx in self.fixtures(comp_id, season_id):
                if fx["match_id"] != match_id:
                    continue
                return {
                    "match_id": match_id,
                    "home": fx["home_team"]["home_team_name"],
                    "away": fx["away_team"]["away_team_name"],
                    "home_score": fx["home_score"],
                    "away_score": fx["away_score"],
                    "competition": _nested(fx, "competition", "competition_name", default=""),
                    "season": _nested(fx, "season", "season_name", default=""),
                    "date": fx.get("match_date", ""),
                }
        # Fall back to the event stream itself.
        first = events[0] if events else {}
        return {
            "match_id": match_id,
            "home": _nested(first, "home_team", "home_team_name", default="Home"),
            "away": _nested(first, "away_team", "away_team_name", default="Away"),
            "home_score": _nested(first, "home_score", default=0),
            "away_score": _nested(first, "away_score", default=0),
            "competition": _nested(first, "competition", "competition_name", default=""),
            "season": _nested(first, "season", "season_name", default=""),
            "date": first.get("match_date", ""),
        }

    # -- event extraction -------------------------------------------------- #
    def _oriented(self, ev: dict, match: Match) -> np.ndarray | None:
        """Event location, flipped so the acting team always attacks left-to-right."""
        loc = _loc(ev)
        if loc is None:
            return None
        team = _nested(ev, "team", "name", default="")
        if match.attacking_direction(team) < 0:
            loc = mirror(loc)[0]
        return loc

    def shots(self, match: Match, team: str | None = None,
              include_shootout: bool = False) -> list[Shot]:
        """Shots, oriented so the shooting team attacks left-to-right.

        Penalty-shootout attempts are excluded by default (see :func:`is_shootout`).
        """
        out: list[Shot] = []
        for ev in match.raw_events:
            if ev.get("type", {}).get("name") != "Shot":
                continue
            if not include_shootout and is_shootout(ev):
                continue
            tname = _nested(ev, "team", "name", default="")
            if team and tname != team:
                continue
            loc = self._oriented(ev, match)
            if loc is None:
                continue
            end = _nested(ev, "shot", "end_location")
            if end is not None and match.attacking_direction(tname) < 0:
                end = mirror(np.array(end[:2], dtype=float))[0].tolist() + list(end[2:])
            out.append(Shot(
                match_id=match.match_id,
                team=tname,
                player=_nested(ev, "player", "name", default="Unknown"),
                x=float(loc[0]), y=float(loc[1]),
                xg=float(_nested(ev, "shot", "statsbomb_xg", default=0.0) or 0.0),
                outcome=_nested(ev, "shot", "outcome", "name", default="Unknown"),
                body_part=_nested(ev, "shot", "body_part", "name", default="Unknown"),
                technique=_nested(ev, "shot", "technique", "name", default="Unknown"),
                minute=int(ev.get("minute", 0)),
                end_x=float(end[0]) if end else None,
                end_y=float(end[1]) if end else None,
                end_z=float(end[2]) if end and len(end) > 2 else None,
                first_time=bool(_nested(ev, "shot", "first_time", default=False)),
                under_pressure=bool(ev.get("under_pressure", False)),
                play_pattern=_nested(ev, "play_pattern", "name", default=""),
            ))
        return out

    def passes(self, match: Match, team: str | None = None) -> list[Pass]:
        out: list[Pass] = []
        for ev in match.raw_events:
            if ev.get("type", {}).get("name") != "Pass":
                continue
            tname = _nested(ev, "team", "name", default="")
            if team and tname != team:
                continue
            loc = self._oriented(ev, match)
            end = _nested(ev, "pass", "end_location")
            if loc is None or end is None:
                continue
            end_xy = np.array(end[:2], dtype=float)
            if match.attacking_direction(tname) < 0:
                end_xy = mirror(end_xy)[0]
            dx = end_xy[0] - loc[0]
            length = float(np.hypot(dx, end_xy[1] - loc[1]))
            out.append(Pass(
                match_id=match.match_id,
                team=tname,
                player=_nested(ev, "player", "name", default="Unknown"),
                recipient=_nested(ev, "pass", "recipient", "name"),
                x=float(loc[0]), y=float(loc[1]),
                end_x=float(end_xy[0]), end_y=float(end_xy[1]),
                minute=int(ev.get("minute", 0)),
                completed=not bool(_nested(ev, "pass", "outcome")),
                pass_type=_nested(ev, "pass", "type", "name", default="Regular"),
                height=_nested(ev, "pass", "height", "name", default="Ground Pass"),
                length=length,
                is_progressive=dx >= 10.0 and float(loc[0]) < 80.0,
                is_line_breaking=dx >= 20.0,
                under_pressure=bool(ev.get("under_pressure", False)),
            ))
        return out

    def defensive_actions(self, match: Match, team: str | None = None) -> list[DefAction]:
        kinds = {
            "Pressure": "pressure",
            "Duel": "duel",
            "Interception": "interception",
            "Block": "block",
            "Clearance": "clearance",
            "Ball Recovery": "recovery",
        }
        out: list[DefAction] = []
        for ev in match.raw_events:
            tname = _nested(ev, "team", "name", default="")
            if team and tname != team:
                continue
            kind = kinds.get(ev.get("type", {}).get("name", ""))
            if kind is None:
                continue
            loc = self._oriented(ev, match)
            if loc is None:
                continue
            outcome = _nested(ev, kind, "outcome", "name", default="")
            out.append(DefAction(
                match_id=match.match_id,
                team=tname,
                player=_nested(ev, "player", "name", default="Unknown"),
                kind=kind,
                x=float(loc[0]), y=float(loc[1]),
                minute=int(ev.get("minute", 0)),
                success=outcome in {"Success", "Won", "Success In Play", "Success Out", ""},
            ))
        return out

    def carries(self, match: Match, team: str | None = None) -> list[Carry]:
        out: list[Carry] = []
        for ev in match.raw_events:
            if ev.get("type", {}).get("name") != "Carry":
                continue
            tname = _nested(ev, "team", "name", default="")
            if team and tname != team:
                continue
            loc = self._oriented(ev, match)
            end = _nested(ev, "carry", "end_location")
            if loc is None or end is None:
                continue
            end_xy = np.array(end[:2], dtype=float)
            if match.attacking_direction(tname) < 0:
                end_xy = mirror(end_xy)[0]
            dx = end_xy[0] - loc[0]
            out.append(Carry(
                match_id=match.match_id,
                team=tname,
                player=_nested(ev, "player", "name", default="Unknown"),
                x=float(loc[0]), y=float(loc[1]),
                end_x=float(end_xy[0]), end_y=float(end_xy[1]),
                minute=int(ev.get("minute", 0)),
                distance=float(np.hypot(dx, end_xy[1] - loc[1])),
                is_progressive=dx >= 5.0,
            ))
        return out

    # -- 360 freeze frames -------------------------------------------------- #
    def frames(self, match: Match, team: str | None = None) -> list[Frame]:
        """Convert raw 360 frames into oriented :class:`Frame` objects.

        Frame ``teammates``/``opponents`` are relative to the event's acting team,
        so after orientation they describe the team in possession. Team is not
        encoded per player in the 360 feed; the acting team is the only signal.
        """
        if not match.raw_frames:
            return []
        by_uuid = {e["id"]: e for e in match.raw_events}
        out: list[Frame] = []
        for fr in match.raw_frames:
            ev = by_uuid.get(fr.get("event_uuid"))
            if ev is None:
                continue
            tname = _nested(ev, "team", "name", default="")
            if team and tname != team:
                continue
            loc = self._oriented(ev, match)
            if loc is None:
                continue
            flip = match.attacking_direction(tname) < 0

            mates, opps = [], []
            actor_xy = None
            for p in fr.get("freeze_frame", []):
                xy = np.array(p["location"][:2], dtype=float)
                if flip:
                    xy = mirror(xy)[0]
                if p.get("actor"):
                    actor_xy = xy
                (mates if p.get("teammate") else opps).append(xy)

            out.append(Frame(
                event_uuid=fr["event_uuid"],
                x=float(loc[0]), y=float(loc[1]),
                teammates=np.array(mates, dtype=float).reshape(-1, 2),
                opponents=np.array(opps, dtype=float).reshape(-1, 2),
                actor=actor_xy is not None,
                keeper=actor_xy.reshape(1, 2) if actor_xy is not None else None,
            ))
        return out

    # -- aggregate helpers -------------------------------------------------- #
    def season_players(self, competition_id: int, season_id: int) -> list[dict]:
        """Player dictionary (id -> name/team) for a season from its events."""
        players: dict[str, dict] = {}
        for fx in self.fixtures(competition_id, season_id):
            mid = fx["match_id"]
            if not (self.cache / "events" / f"{mid}.json").exists():
                continue
            for ev in json.loads((self.cache / "events" / f"{mid}.json").read_text()):
                p = ev.get("player")
                if not p:
                    continue
                team = _nested(ev, "team", "name", default="")
                players.setdefault(f"{team}|{p['name']}", {
                    "player": p["name"], "team": team, "match_id": mid,
                })
        return list(players.values())


# --------------------------------------------------------------------------- #
# xThreat: a compact, well-documented possession-value grid
# --------------------------------------------------------------------------- #
@lru_cache(maxsize=1)
def xthreat_grid() -> np.ndarray:
    """A 12x8 xThreat surface over the 120x80 pitch.

    Values rise monotonically toward the opponent goal and peak in the central
    corridor. This is a **stylised** model in the spirit of Karun Singh's
    xT (https://karun.in/blog/expected-threat.html) - good enough to rank pass
    value, not a fitted model.
    """
    nx, ny = 12, 8
    grid = np.zeros((ny, nx))
    for i in range(nx):
        fx = (i + 0.5) / nx
        for j in range(ny):
            fy = (j + 0.5) / ny
            centrality = 1.0 - abs(fy - 0.5) * 1.6
            grid[j, i] = (fx ** 3.1) * (0.35 + 0.65 * max(centrality, 0.0))
    grid /= grid.max()
    return grid


def xthreat(x: float, y: float) -> float:
    """Look up the xThreat value for a pitch coordinate."""
    grid = xthreat_grid()
    ny, nx = grid.shape
    i = min(nx - 1, max(0, int(x / PITCH_LENGTH * nx)))
    j = min(ny - 1, max(0, int(y / PITCH_WIDTH * ny)))
    return float(grid[j, i])


def progressive_value(p: Pass) -> float:
    """xThreat gained by a pass (positive = ball moved into a better zone)."""
    return xthreat(p.end_x, p.end_y) - xthreat(p.x, p.y)
