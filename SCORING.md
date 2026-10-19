# How the points are calculated

Everything the leaderboard shows comes from one number repeated a lot: the
payoff of a single round. This document follows that number all the way up to
the final ranking — one round → one match → one tournament → the Monte Carlo
average — and then explains every column in the results table.

Notation used throughout: **C** = cooperate, **D** = defect (in the code,
`True` and `False`). `n` = number of agents, `T` = rounds per match (100),
`R` = number of Monte Carlo replications.

---

## 1. One round

Both agents choose C or D **simultaneously** — neither sees the other's current
move. The pair of moves pays out according to the standard prisoner's dilemma
matrix, which is the C# `{{3,0},{5,1}}` matrix written out:

| | opponent plays **C** | opponent plays **D** |
|---|---|---|
| **I play C** | I get **3** (Reward) | I get **0** (Sucker) |
| **I play D** | I get **5** (Temptation) | I get **1** (Punishment) |

In the usual `T > R > P > S` names: **T = 5, R = 3, P = 1, S = 0** (settable
with `--payoff T R P S`). The two conditions that make this a dilemma both
hold: `T > R > P > S`, so defecting is better whatever the opponent does; and
`2R > T + S`, so mutual cooperation beats taking turns exploiting each other.

The payoff is symmetric — both sides are paid from the same table, so one
round hands out `(3,3)`, `(0,5)`, `(5,0)` or `(1,1)`.

## 2. One match: 100 rounds with noisy observations

```
round 1 : both agents play whatever reset() returned
round t : each agent plays response(<its observation of the opponent's move
          in round t-1>), for t = 2 … 100
```

**The observation is noisy.** With probability 0.05, independently for each
agent and each round, what you are told the opponent did last round is the
*opposite* of what they actually did. Your own move is never corrupted, and
the payoff is always computed from the **true** moves — the noise is only in
what you know, never in what happened.

Every round is scored, including the first, so a match pays out exactly
`T = 100` rounds to each side. A match therefore produces two numbers: total
points for A and total points for B, each between 0 and 500.

### Worked example

Tit-for-tat against always-defect, no noise:

| round | TFT | ALLD | TFT gets | ALLD gets |
|---|---|---|---|---|
| 1 | C | D | 0 | 5 |
| 2 | D | D | 1 | 1 |
| … | D | D | 1 | 1 |
| 100 | D | D | 1 | 1 |

TFT scores `0 + 99×1 = 99`, ALLD scores `5 + 99×1 = 104`. (This exact pair is
one of the assertions in `test_engine.py`.)

Now the same pair *with* 5% noise, and the reason this homework is not the
1984 one: when two tit-for-tats meet, a single flipped observation makes one
of them "retaliate" against a cooperation that happened. The other retaliates
back, and they alternate C/D for the rest of the match: 0 and 5 in turn, so
**2.50** a round instead of 3.00 — and a further flip can drop them from the
alternation into permanent mutual defection at 1.00. Averaged over the mix,
two tit-for-tats score about **2.34** per round under 5% noise.

## 3. One tournament: the round-robin

Every pair of agents plays **one** match, and both sides are scored from it.
An agent does **not** play itself by default (matching `Program.cs`; turn it on
with `--self-play`). So with `n` agents, each one plays `n − 1` matches and
`T × (n − 1)` scored rounds.

The agent's raw points in one tournament are the sum over its opponents:

```
points_i  =  Σ_(j ≠ i)  (points agent i scored in its match against j)
```

### Beating your opponent is not the goal

Points are **accumulated, not won**. There is no bonus for out-scoring the
agent across the table, and the head-to-head record is not what is ranked.
This is Axelrod's whole point, and it shows up in the sample field shipped
with this code:

* `example_pure_bad` (always defect) out-scores **12 of its 12 opponents**
  head-to-head — and finishes **9th**, because it drags every match down to
  ~1 point a round.
* `tit_for_two_tats` out-scores **1 of its 12 opponents** — and finishes
  **3rd**, because it gets ~3 points a round out of everyone willing to
  cooperate.

A strategy that never loses a match can still lose the tournament by a mile.

## 4. The number on the leaderboard: points per round

Raw totals depend on how many students submitted, so they are normalised:

```
score_i  =  points_i / (T × (n − 1))          <- "score/round" in the table
```

This is the **mean payoff per round per opponent**, and it is directly
readable against the payoff constants:

| score/round | means |
|---|---|
| 3.00 | permanent mutual cooperation with everybody |
| 2.50 | the C/D alternation of an echo war (0 and 5 in turn) |
| 1.00 | permanent mutual defection with everybody |
| 5.00 | exploiting a field of pure cooperators every round |

The `per 100 rds` column is the same number ×100 — the points an average
100-round match brings in.

## 5. The Monte Carlo average

A tournament played once is **one sample**, not a measurement. The noise is
the only randomness, but it is powerful: run the C# program twice and the top
two can swap places. So the whole round-robin is replayed `R` times with
independent noise, and each replication `r` gives every agent a score
`score_i(r)`. The leaderboard ranks by the average:

```
mean_i  =  (1/R) · Σ_r score_i(r)                    <- the ranking key
sd_i    =  sample standard deviation of score_i(r) over the R replications
sem_i   =  sd_i / √R                                 <- standard error
95% CI  =  mean_i ± 1.96 · sem_i                     <- the "±" column
```

The CI is the honest width of the estimate: with `sd ≈ 0.05–0.12` per
replication, the half-width is roughly `0.2/√R` — about ±0.009 at 500
replications, ±0.0045 at 2000, ±0.0014 at 20000.

Three details make the comparison fair rather than merely repeated:

1. **Common random numbers.** The noise seed of a match is
   `blake2b(seed, replication, the two agent names)` — derived from the names,
   not from positions in the list. Every agent therefore meets the *same* noise
   realisations in replication `r`; the comparison between two agents is
   **paired**; and adding or removing a submission leaves every other pair's
   numbers bit-identical.
2. **A fresh instance per match.** `__init__` and `reset()` both run at the
   start of every match, so state can never leak from one match into the next.
3. **The normalisation above**, so the numbers do not move when the class size
   does.

## 6. The other columns

| column | what it is |
|---|---|
| `score/round` | `mean_i` — **this is what the ranking uses** |
| `95% CI` | `1.96 · sem_i`, the half-width of the interval |
| `interval` | `[mean − CI, mean + CI]` |
| `per 100 rds` | `mean_i × 100`, points per average match |
| `win%` | share of the `R` replications in which this agent finished **1st** in the complete round-robin (ties split the credit) |
| `avg rank` | mean finishing position over the replications (1 = first); ties get the average of the positions they share |
| `sd` | spread of this agent's score between replications — how much the noise moves it |
| `faults` | exceptions, timeouts and non-boolean returns from this agent's code (see §8) |

`win%` and `score/round` answer different questions and can disagree: an agent
with a slightly lower mean but a fatter upper tail can win more individual
tournaments than the agent with the higher mean. The ranking uses the mean;
`win%` is there to show how much of the outcome is still luck.

`head_to_head.csv` gives the same per-round normalisation for every ordered
pair: cell `(row, column)` is the row agent's mean payoff per round in its
matches against the column agent.

## 7. Deciding first place, and ties

More replications shrink the CI but never to zero, so "who won" is a
statistical question. After each batch the runner compares the leader with the
runner-up on the **paired** per-replication difference:

```
d_r  =  score_leader(r) − score_runnerup(r)
z    =  mean(d) / ( sd(d)/√R )
```

Pairing matters: both agents met the same noise in replication `r`, so the
shared noise cancels in `d_r` and `sd(d)` is far smaller than either agent's
own `sd`. That is what makes a few hundred replications enough.

The run stops early when `z > 3`, not at the nominal 95% (`z > 1.96`). The
test is applied after every batch, and a 95% test repeated fifty times fires
on pure noise more often than not; `z > 3` is a constant boundary that keeps
the overall false-stop rate near 5%. You can watch the difference with the two
*identical* `example_password_*` agents in the sample field: at `1.96` the
runner "separates" the twins and crowns one of them; at `3` it runs to the cap
and reports **TOP TWO ARE TIED on this evidence**, which is the truth.

If the header says the top two are tied, they are tied — the point estimates
are not a tie-break. Two submissions implementing the same idea cannot be
separated at any number of replications.

## 8. Broken code, and things that are not scored

* **A fault** — an exception, a timeout, or a return value that is not
  `True`/`False` — is caught. The move falls back to *repeating that agent's
  own previous move* (the most neutral substitute: it neither hands the
  opponent a free exploit nor lets a broken agent profit from defecting), and
  the fault is counted. The match still finishes, and the totals still count,
  so a faulty agent gets a score — but the `faults` column is not zero, and
  that is a grading matter, not a scoring one.
* **A file that does not import** (syntax error, two agent classes, a
  duplicate of another submission) never enters the tournament at all. It is
  listed under `FAILED TO LOAD` and has no score.
* **Nothing else is scored by the program.** The written explanation of the
  strategy that the assignment asks for, and any judgement about a submission
  that games the tournament rather than plays it, are the instructor's.

## 9. The score is relative to the field

An agent's score is not an absolute property of the strategy. Exploiting naive
cooperators pays exactly as much as the class submitted naive cooperators, and
a handshake strategy is worth having exactly when a twin is present. Two
consequences:

* fix the field **before** the graded run — decide whether `baselines/` is in
  or out, and whether `--self-play` is on — and use the same field for
  everybody;
* the same submission, run against a different field, gets a different number.
  That is a property of the game, not a bug in the scoring.

## 10. Reproducing any number

Every run is determined by `--seed` (default `20260810`) together with the
list of agent names, so the whole tournament replays exactly:

```bash
python3 run_tournament.py --dirs submissions --reps 2000 --seed 20260810
python3 inspect_match.py <agent A> <agent B> --rep 0     # round-by-round replay
```

`results/replications.csv` holds the raw `R × n` sample if you want to redo the
statistics yourself; `results/tournament_charts.html` plots the running mean
against the number of replications, so you can see the ranking settle.
