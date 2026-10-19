"""Monte Carlo statistics: means, confidence intervals, ranks."""

from __future__ import annotations

import math
from dataclasses import dataclass

Z95 = 1.959963984540054


@dataclass
class Summary:
    name: str
    mean: float          # mean payoff per round (per opponent)
    sd: float
    sem: float           # standard error of the mean over replications
    ci: float            # 95% CI half-width
    lo: float
    hi: float
    win_rate: float      # share of replications finished 1st (ties shared)
    mean_rank: float
    best: float
    worst: float
    reps: int
    faults: int = 0


def mean_sd(xs):
    n = len(xs)
    if n == 0:
        return 0.0, 0.0
    m = sum(xs) / n
    if n < 2:
        return m, 0.0
    var = sum((x - m) ** 2 for x in xs) / (n - 1)
    return m, math.sqrt(var)


def summarize(names, per_rep_scores, faults=None):
    """per_rep_scores: list over replications of list over agents (per-round payoff)."""
    faults = faults or {}
    reps = len(per_rep_scores)
    n = len(names)

    wins = [0.0] * n
    rank_sum = [0.0] * n
    for row in per_rep_scores:
        top = max(row)
        winners = [i for i, v in enumerate(row) if v == top]
        for i in winners:
            wins[i] += 1.0 / len(winners)
        # average rank, ties share the average of the tied positions
        order = sorted(range(n), key=lambda i: -row[i])
        pos = 0
        while pos < n:
            end = pos
            while end + 1 < n and row[order[end + 1]] == row[order[pos]]:
                end += 1
            avg_rank = (pos + end) / 2 + 1
            for k in range(pos, end + 1):
                rank_sum[order[k]] += avg_rank
            pos = end + 1

    out = []
    for i, name in enumerate(names):
        col = [row[i] for row in per_rep_scores]
        m, sd = mean_sd(col)
        sem = sd / math.sqrt(reps) if reps else 0.0
        ci = Z95 * sem
        out.append(Summary(
            name=name, mean=m, sd=sd, sem=sem, ci=ci, lo=m - ci, hi=m + ci,
            win_rate=wins[i] / reps if reps else 0.0,
            mean_rank=rank_sum[i] / reps if reps else 0.0,
            best=max(col) if col else 0.0, worst=min(col) if col else 0.0,
            reps=reps, faults=faults.get(name, 0),
        ))
    out.sort(key=lambda s: -s.mean)
    return out


def paired_gap(per_rep_scores, i, j):
    """Paired difference agent_i - agent_j across replications.

    Because every replication uses the *same* noise seeds for both agents'
    matches, the paired difference has far lower variance than the difference
    of the two independent means -- this is what lets us separate the top two
    with a few hundred replications instead of tens of thousands.
    """
    d = [row[i] - row[j] for row in per_rep_scores]
    m, sd = mean_sd(d)
    sem = sd / math.sqrt(len(d)) if d else 0.0
    return m, sem, Z95 * sem


def separated(per_rep_scores, names, z_stop: float = 3.0) -> tuple[bool, str]:
    """Is the leader clearly ahead of the runner-up on the paired difference?

    The significance is looked at after every batch, so a plain 95% test would
    fire on noise sooner or later (checking 50 times at alpha=5% is not a 5%
    test).  The stopping boundary is therefore `z_stop` standard errors --
    3.0 by default, a Pocock-style constant boundary that keeps the overall
    false-stop rate near 5% over a few dozen looks.  The reported interval is
    still the ordinary 95% one.
    """
    if len(names) < 2 or not per_rep_scores:
        return True, "only one contestant"
    n = len(names)
    reps = len(per_rep_scores)
    means = [sum(row[i] for row in per_rep_scores) / reps for i in range(n)]
    order = sorted(range(n), key=lambda i: -means[i])
    i, j = order[0], order[1]
    gap, sem, ci = paired_gap(per_rep_scores, i, j)
    ok = sem > 0 and gap > z_stop * sem
    z = gap / sem if sem > 0 else 0.0
    msg = (f"{names[i]} - {names[j]} = {gap:+.4f} +/- {ci:.4f} (95% CI), "
           f"z = {z:.2f}; "
           + ("clear at the z>%.1f stopping boundary" % z_stop if ok
              else "NOT separated (needs z > %.1f with repeated looks)" % z_stop))
    return ok, msg
