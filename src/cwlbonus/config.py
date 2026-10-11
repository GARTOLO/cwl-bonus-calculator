"""Scoring weights and presets.

Every number that decides the ranking lives here, so a clan can tune the tool
without editing the maths. See docs/SCORING.md for why the defaults are what
they are.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

# Preset names are CLI-facing, so they are not translated.
PRESET_STARS = "stars"
PRESET_BALANCED = "balanced"
PRESET_HARD_TARGET = "hard-target"


@dataclass
class Weights:
    """All tunables, with the values this project ships as defaults."""

    # --- attack difficulty -------------------------------------------------
    # Points per Town Hall level of difficulty, applied per attack.
    # 0.5 is the default: it is large enough that consistently taking harder
    # targets than your mirror can actually move you into the bonuses, which
    # 0.3 was measured not to do. See docs/SCORING.md.
    difficulty: float = 0.5

    # How far the difficulty correction may reach. The floor doubles as
    # opponent-strength normalisation: against a much weaker clan everyone is
    # charged the same, instead of a deep penalty no player could avoid.
    difficulty_clamp: tuple[float, float] = (-1.0, 3.0)

    # --- rushed-base (rusher) detector -------------------------------------
    # A base whose TH is higher than the weakest TH above it on the enemy map
    # is treated as rushed, and counted down to that weaker TH. This caps how
    # many levels the correction may remove, so a pathological lineup can never
    # collapse a whole map's difficulty.
    rusher_max_cut: int = 2

    # --- missed attacks ----------------------------------------------------
    # One attack per war in CWL. Charged per attack not used and never clipped
    # away by the total floor, so a no-show can never tie with an honest zero.
    missed_attack: float = -2.0

    # --- optional lineup drift --------------------------------------------
    # Attacking below your own mirror (in lineup slots) is farm-avoidance.
    # Default 0 because in practice CWL is mirror-based and this would be a
    # no-op; exposed for clans that want to discourage it.
    lineup_drift: float = 0.0

    # --- optional defense --------------------------------------------------
    # Off by default: exposure is partly a compliment in CWL (opponents spend
    # attacks on bases they need to break), so it is a policy choice.
    use_defense: bool = False
    defense_per_star: float = 1.0
    defense_th_bonus: float = 0.10
    # neutral -> nobody attacked you, you get nothing
    # min     -> you get the worst per-defense score observed this season
    # max     -> you get credit as if you had never conceded a star
    no_defense_policy: str = "neutral"

    # --- presentation ------------------------------------------------------
    # Display floor only. Keeps a heavy penalty visible instead of clipping it
    # to 0 (which is what made a no-show tie with an honest zero).
    total_floor: float | None = -10.0

    # --- eligibility -------------------------------------------------------
    min_wars: int = 0
    bonuses: int = 7

    def __post_init__(self) -> None:
        self.difficulty_clamp = (float(self.difficulty_clamp[0]),
                                 float(self.difficulty_clamp[1]))
        if self.no_defense_policy not in ("neutral", "min", "max"):
            raise ValueError(
                f"no_defense_policy must be neutral|min|max, got {self.no_defense_policy!r}")

    def to_dict(self) -> dict:
        d = asdict(self)
        d["difficulty_clamp"] = list(d["difficulty_clamp"])
        return d

    @staticmethod
    def from_dict(data: dict) -> "Weights":
        known = {f.name for f in fields(Weights)}
        clean = {k: v for k, v in data.items() if k in known and not k.startswith("_")}
        if "difficulty_clamp" in clean:
            clean["difficulty_clamp"] = tuple(clean["difficulty_clamp"])
        return Weights(**clean)


PRESETS: dict[str, Weights] = {
    PRESET_STARS: Weights(difficulty=0.0),
    PRESET_BALANCED: Weights(difficulty=0.5),
    PRESET_HARD_TARGET: Weights(difficulty=1.0),
}


def resolve_weights(preset: str | None = None, config_path: str | None = None,
                    overrides: dict | None = None) -> Weights:
    """Builds the effective weights: preset, then JSON config, then CLI overrides."""
    weights = PRESETS.get(preset or PRESET_BALANCED, PRESETS[PRESET_BALANCED])
    weights = Weights.from_dict(weights.to_dict())

    if config_path:
        payload = json.loads(Path(config_path).read_text(encoding="utf-8"))
        payload.pop("$schema", None)
        weights = Weights.from_dict({**weights.to_dict(), **payload})

    if overrides:
        clean = {k: v for k, v in overrides.items() if v is not None}
        if clean:
            weights = Weights.from_dict({**weights.to_dict(), **clean})
    return weights
