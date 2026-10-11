# Scoring — how it works and why

This document is the rationale behind every number in `src/cwlbonus/config.py`. If you disagree with a weight, this is where to find out what it does before you change it.

All measurements below come from one real 7-round CWL season (104 attacks, 16 players), anonymised into `tests/fixtures/season_sample.json`.

---

## The formula

Per attack:

```
points = stars + (destruction / 100) + (difficulty × clamp(effective_enemy_TH − your_TH, −1, +3))
```

Total:

```
total = Σ attack_points + Σ missed_attacks × missed_attack_penalty
```

With the defaults (`difficulty = 0.5`, `missed_attack = −2.0`).

### What each term is for

| Term | Range per attack | What it decides |
|---|---|---|
| `stars` | 0 – 3 | Whether you broke the base. Dominant term. |
| `destruction / 100` | 0 – 1 | How close you got when you didn't. Separates a 99% two-star from a 40% two-star. |
| `difficulty × ΔTH` | −0.5 – +1.5 at weight 0.5 | Whether your job was harder than the next player's. Decides tight seasons. |
| `missed_attack` | −2.0 per attack | Participation. |

`stars + destruction` spans ~0–4 points. The difficulty term spans ~±0.9 at the default weight. **Stars dominate by design**: a clean three-star on a modest base should still beat a one-star hero attempt on a hard one. The difficulty term is a tiebreaker that can move you a few places and, in a close season, decide a bonus — but it cannot manufacture a result out of a bad attack.

Worked examples at weight 0.5, all 3-star / 100% attacks:

| Your TH | Their effective TH | ΔTH | Points |
|---|---|---|---|
| 17 | 17 (exact mirror) | 0 | 4.00 |
| 17 | 18 (one above) | +1 | 4.50 |
| 17 | 19 (two above) | +2 | 5.00 |
| 17 | 16 (one below) | −1 | 3.50 |
| 17 | 10 (six below) | −1 (clamped) | 3.50 |

### Why the clamp floor is −1, not something deeper

The floor is doing two jobs.

1. **Anti-farming.** Attacking far below your own level must not be attractive.
2. **Opponent-strength normalisation.** This is the subtle one. If your clan is simply stronger than the enemy clan, *every* player's mirror is below them. Without a floor, the whole clan would take a large, unavoidable penalty, and the season's ranking would be decided by how weak your opponents were rather than how well you played.

Measured on the sample season: **21 of 104 attacks are pinned to the −1 floor, and 0 ever reach the +3 ceiling.** The floor returns about **+68 town-hall-steps** of raw difficulty — that is the normalisation working. It is also why the difficulty term is nearly constant for a strong clan, which is what the next section is about.

### Why the default difficulty weight is 0.5 and not 0.3

The single most consequential number in the project. Measured on the sample season, changing only the weight and looking at who receives the 7 bonuses:

| Weight | Behaviour | Bonus recipients change vs weight 0? |
|---|---|---|
| `0.0` | pure stars | *(baseline)* |
| `0.3` | the old default | **No — identical recipients**, only the order changes |
| `0.5` | shipped default | Yes: one player who consistently took harder mirrors replaces one who did not |
| `0.75` – `1.0` | hard-target rewards | Yes: a second hard-target specialist moves in |
| `1.5` – `2.0` | difficulty-led | Several: the ranking stops resembling the stars table |

At `0.3` the term is **decorative**: it reorders the display without changing a single outcome. A clan that believes in rewarding hard targets and runs `0.3` is not actually rewarding them.

Concretely, at `0.5` the player who moves into the bonuses has the **lowest star count of the seven-round regulars** but was the **only player whose raw (unclamped) difficulty sum was not negative** — he was consistently matched against equal-or-stronger bases while everyone else was matched downward. That is exactly the contribution the term exists to recognise. Whether you want it to outweigh stars is a clan policy call, which is why it is a flag and not a constant.

`tests/test_fixture.py::test_the_difficulty_weight_decides_who_gets_a_bonus` fails if a future change makes the weight inert again.

---

## The rushed-base ("rusher") detector

```python
effective_th[i] = max(weakest_th_above_i, own_th − rusher_max_cut)
```

The CWL map is ordered by war weight. A base whose Town Hall is **higher** than the weakest Town Hall above it is carrying less weight than that weaker base — the game itself ranked it lower, which means it is rushed. Its effective TH becomes that weaker TH, which is what the map order already implies.

So a rushed TH18 sitting below a TH16 counts as a TH16, and attacking it earns no extra difficulty credit.

### Why this is safe in practice, measured

I originally worried this could backfire: a running minimum over the map means one misplaced weak base could drag every effective TH below it downwards and flatten the whole round's difficulty. So the sample season was checked for exactly that:

- **210 bases scanned** across all 14 sides of 7 wars.
- **0 of 14 sides were ordered ascending.** The map is sorted by weight, so the top is always a top base.
- **Position 1 was TH18 in 13 of 14 sides.** The exception is an entire clan of TH9–15, where a TH15 at slot 1 is simply correct.
- The detector **fired on 11 of 105 opponent bases (10%)**, median correction 1 level.

It is therefore a no-op on a normally ordered map and only fires on genuine anomalies.

### Why the correction is capped

`rusher_max_cut` (default 2) bounds how many levels may be removed. The running minimum compares against the *weakest* TH above, not the tier immediately above, so a TH18 at the last slot can in principle be counted as a TH15. Capping keeps a single strange lineup from collapsing the difficulty of an entire map.

On the sample season the cap changes **nothing** — the correction was already at most 2 levels. It is insurance, and `tests/test_scoring.py::test_one_odd_base_cannot_collapse_the_whole_maps_difficulty` pins the behaviour.

Set `--rusher-cap 0` to disable the correction entirely.

---

## Missed attacks

In CWL each player gets exactly one attack per war. Verified on the sample season: **105 player-war instances, zero with more than one attack.** So

```
missed = wars_played − attacks_used
```

is arithmetically sound.

- A player **benched** for a round is not on the roster for that war, so `wars_played` does not count it and they are not charged. Verified.
- A **late substitute** who played one war and missed their only attack *is* charged. Also correct, and verified.
- The penalty is charged but the total is **never clipped up to zero**. The original tool did `clip(lower=0)`, which meant a no-show with a −6 penalty scored `0.00` — exactly the same as a player who attacked three times and achieved nothing. The penalty now stays visible, with `total_floor` (−10) acting only as a display floor so absurd penalties do not wreck the axis. `penalty_points` is always reported separately and unfloored.

---

## Defence (optional, off by default)

The original defence formula was:

```
points = (3 × defences − stars_conceded) × (0.5 + ΔTH × 0.10)
```

Two problems, both measured:

1. **A player nobody attacked scored `0.00` — identical to being 3-starred every round.** Being ignored is not the same as being breached.
2. **Points grew with exposure.** `(3 × n − stars)` scales with the number of defences received, so being attacked more was worth more. Measured correlation between how often a player was attacked and their defensive score: **r = +0.36**.

This project instead computes **stars saved per defence**:

```
per_defence = mean(3 − stars_conceded)
points = per_defence × (defense_per_star + max(0, mean_attacker_TH − your_TH) × defense_th_bonus)
```

Deliberately **not multiplied by the number of defences**, so six attacks are not automatically worth six times one attack.

Measured on the sample season:

| Player | Attacked | Stars conceded | Stars saved / defence | Old formula | New formula |
|---|---|---|---|---|---|
| Best regular | 5 | 9 | **1.20** | 3.00 | 1.20 |
| … | 6 | 12 | 1.00 | 3.00 | 1.00 |
| … | 5 | 13 | 0.40 | 1.00 | 0.40 |
| Worst | 6 | 17 | **0.17** | 0.50 | 0.18 |

The old formula barely separated the best defender from the worst. The new one does.

### `no_defense_policy`

What a never-attacked player gets is an explicit policy, never a silent zero:

| Policy | Meaning |
|---|---|
| `neutral` *(default)* | No credit. The defence count is still reported so the omission is visible. |
| `min` | The worst per-defence score observed this season. |
| `max` | As if they had never conceded a star. |

**Why defence stays off by default:** in CWL, being attacked repeatedly is partly a compliment — opponents spend attacks on the bases they need to break. So neither "reward volume" nor "reward pure efficiency" is unambiguously right. The tool measures efficiency, reports the count, and leaves the policy to the clan.

---

## Ties

The original sorted on a float, so two players on identical scores were shown as e.g. 3rd and 4th in whatever order the rows arrived from the API. Verified by permuting the input.

Two consequences, both fixed:

- **Equal scores now share a rank.** The sample season has such a tie, and both players are labelled `(tie)` rather than being split arbitrarily.
- **A tie on the bonus cut is reported, not resolved.** `build_ranking` detects when the last bonus recipient and the first excluded player have the same score, fills `Ranking.cut_tie`, prints a prominent warning, retitles the chart's cut annotation, and **exits with a non-zero status** — because awarding a bonus by coin flip is not a decision a tool should make for a clan. Order is deterministic (`(−total, name)`), so even the display is reproducible.

---

## Deliberately not implemented

Things that were considered and rejected, so nobody re-litigates them by accident:

- **Average score instead of total.** A cumulative score already means a late joiner cannot out-rank a regular, and `--min-wars` makes that explicit when a clan wants it enforced. Silently switching to averages would surprise more people than it helps.
- **A lineup-drift penalty.** Measured on a real season: **101 of 104 attacks were exact lineup mirrors, 103 within one slot.** CWL is mirror-based, so a drift penalty would be a no-op — it is exposed as `lineup_drift` for clans whose policy differs, but defaults to 0.
- **Rewarding stars-per-attack differently from raw stars.** `attacks_used / wars_played` is displayed, and missed attacks are charged directly; a second, softer efficiency term would double-count.
- **Reading past seasons.** The official API does not expose historical league groups. This is a platform limit, not a design choice.
