"""Round-robin tournament + Monte Carlo driver.

Monte Carlo design
------------------
One *replication* = one full round-robin (every unordered pair plays one
match).  The only randomness is the 5% observation noise, so a single
tournament is a single draw from a fairly wide distribution -- with 100
rounds a match, two runs of the same code can easily swap the top two places.
We therefore repeat the whole tournament R times and rank by the *mean*
per-round payoff, reported with a 95% confidence interval.

Three variance-reduction / fairness choices:

1. Common random numbers.  The noise seed of a match is derived from
   (base_seed, replication, the two agent names) -- not from list positions.
   So every strategy meets the same noise realisations in replication r, the
   comparison between two agents is *paired*, and adding a late submission
   does not perturb anybody else's result.
2. Fresh instances.  Every match constructs new objects, so an agent that
   forgets to clear state in reset() cannot leak information between matches.
3. Score normalisation.  Scores are reported as payoff per round per
   opponent, which makes them independent of the number of submissions and
   directly comparable to the payoff constants (3.0 = mutual cooperation).

Stopping rule: replications are run in batches until the leader is separated
from the runner-up at 95% on the *paired* difference, or `max_reps` is hit.
"""

from __future__ import annotations

import os
import random
from dataclasses import dataclass, field, asdict

from . import engine
from .engine import Health, make_payoff, match_seed, play_match
from .loader import load_file
from .stats import separated, summarize


@dataclass
class Config:
    rounds: int = 100
    noise: float = 0.05
    payoff: tuple = (5, 3, 1, 0)   # T, R, P, S
    seed: int = 20260810
    self_play: bool = False
    move_timeout: float | None = None
    rounds_jitter: int = 0

    def table(self):
        T, R, P, S = self.payoff
        return make_payoff(T, R, P, S)


# --------------------------------------------------------------------------
# core: one replication
# --------------------------------------------------------------------------

def pairs_of(n: int, self_play: bool):
    for i in range(n):
        for j in range(i if self_play else i + 1, n):
            yield i, j


def run_replication(contestants, cfg: Config, rep: int, health=None):
    """Play one full round-robin.  Returns (per_round_scores, pair_totals)."""
    n = len(contestants)
    payoff = cfg.table()
    totals = [0.0] * n
    rounds_played = [0] * n
    pair_totals = {}
    health = health if health is not None else [Health() for _ in range(n)]

    for i, j in pairs_of(n, cfg.self_play):
        engine.verify_integrity()   # a patch from the last match cannot carry over
        a_c, b_c = contestants[i], contestants[j]
        rng = random.Random(match_seed(cfg.seed, rep, a_c.name, b_c.name))
        sa, sb, r = play_match(
            a_c.new(), b_c.new(),
            rounds=cfg.rounds, noise=cfg.noise, payoff=payoff, rng=rng,
            health_a=health[i], health_b=health[j],
            move_timeout=cfg.move_timeout, rounds_jitter=cfg.rounds_jitter,
        )
        totals[i] += sa
        totals[j] += sb
        rounds_played[i] += r
        rounds_played[j] += r
        acc = pair_totals.setdefault((i, j), [0.0, 0.0, 0])
        acc[0] += sa
        acc[1] += sb
        acc[2] += r

    engine.verify_integrity()   # catch/undo any patch to the engine or random

    per_round = [
        totals[i] / rounds_played[i] if rounds_played[i] else 0.0 for i in range(n)
    ]
    return per_round, pair_totals


# --------------------------------------------------------------------------
# worker plumbing (multiprocessing)
# --------------------------------------------------------------------------

_W: dict = {}


def _init_worker(paths, cfg_dict):
    cfg = Config(**cfg_dict)
    contestants = [load_file(p, scan=False) for p in paths]
    _W["contestants"] = contestants
    _W["cfg"] = cfg
    engine.snapshot_integrity()


def _run_batch(rep_range):
    contestants, cfg = _W["contestants"], _W["cfg"]
    health = [Health() for _ in contestants]  # per-batch, so counts can be summed
    rows, pair_acc = [], {}
    for rep in rep_range:
        per_round, pair_totals = run_replication(contestants, cfg, rep, health)
        rows.append(per_round)
        for k, v in pair_totals.items():
            acc = pair_acc.setdefault(k, [0.0, 0.0, 0])
            acc[0] += v[0]
            acc[1] += v[1]
            acc[2] += v[2]
    faults = [(h.faults, h.errors) for h in health]
    tamper = list(engine.TAMPER_EVENTS)
    engine.TAMPER_EVENTS.clear()
    return rows, pair_acc, faults, tamper


# --------------------------------------------------------------------------
# Monte Carlo driver
# --------------------------------------------------------------------------

@dataclass
class MCResult:
    names: list
    per_rep: list                     # [rep][agent] -> payoff per round
    pair_totals: dict                 # (i, j) -> [score_i, score_j, rounds]
    faults: dict = field(default_factory=dict)
    fault_msgs: dict = field(default_factory=dict)
    reps: int = 0
    stop_reason: str = ""
    gap_note: str = ""
    cfg: dict = field(default_factory=dict)
    tamper: list = field(default_factory=list)

    def summaries(self):
        return summarize(self.names, self.per_rep, self.faults)

    def pair_matrix(self):
        """m[i][j] = agent i's average payoff per round against agent j."""
        n = len(self.names)
        m = [[None] * n for _ in range(n)]
        for (i, j), (si, sj, r) in self.pair_totals.items():
            if r:
                m[i][j] = si / r
                m[j][i] = sj / r
        return m


def run_montecarlo(
    contestants,
    cfg: Config,
    reps: int = 500,
    max_reps: int | None = None,
    batch: int = 100,
    workers: int | None = None,
    progress=None,
    z_stop: float = 3.0,
) -> MCResult:
    """Run `reps` replications, extending up to `max_reps` until the leader
    is statistically separated from the runner-up."""
    names = [c.name for c in contestants]
    max_reps = max(max_reps or reps, reps)
    workers = workers if workers is not None else min(os.cpu_count() or 1, 8)
    if len(contestants) < 2:
        raise SystemExit("need at least 2 contestants")

    per_rep: list = []
    pair_acc: dict = {}
    faults = {n_: 0 for n_ in names}
    fault_msgs: dict = {}
    stop_reason = ""
    gap_note = ""
    early = False

    tamper_events: list = []

    def absorb(chunk):
        rows, pacc, fl, tamper = chunk
        tamper_events.extend(tamper)
        per_rep.extend(rows)
        for k, v in pacc.items():
            acc = pair_acc.setdefault(k, [0.0, 0.0, 0])
            acc[0] += v[0]
            acc[1] += v[1]
            acc[2] += v[2]
        for idx, (cnt, msgs) in enumerate(fl):
            if cnt:
                faults[names[idx]] += cnt
                fault_msgs.setdefault(names[idx], msgs)

    pool = None
    if workers > 1:
        from concurrent.futures import ProcessPoolExecutor
        pool = ProcessPoolExecutor(
            max_workers=workers,
            initializer=_init_worker,
            initargs=([str(c.path) for c in contestants], asdict(cfg)),
        )
    else:
        _init_worker([str(c.path) for c in contestants], asdict(cfg))

    try:
        done = 0
        while done < max_reps:
            target = min(reps if done == 0 else done + batch, max_reps)
            todo = list(range(done, target))
            if not todo:
                break
            if pool:
                k = max(1, len(todo) // workers + 1)
                chunks = [todo[x:x + k] for x in range(0, len(todo), k)]
                for chunk in pool.map(_run_batch, chunks):
                    absorb(chunk)
            else:
                absorb(_run_batch(todo))
            done = target
            if progress:
                progress(done, max_reps)
            ok, gap_note = separated(per_rep, names, z_stop=z_stop)
            if ok and done >= reps:
                stop_reason = f"leader separated (paired z > {z_stop})"
                early = True
                break
    finally:
        if pool:
            pool.shutdown()

    if not early:
        ok, gap_note = separated(per_rep, names, z_stop=z_stop)
        stop_reason = ("budget of replications used up; "
                       + ("leader is clear" if ok else
                          "TOP TWO ARE TIED on this evidence"))

    if tamper_events:
        stop_reason += ("  [!] ENGINE TAMPERING DETECTED and reverted: "
                        + "; ".join(sorted({x for ev in tamper_events for x in ev})))

    return MCResult(
        names=names, per_rep=per_rep, pair_totals=pair_acc,
        faults=faults, fault_msgs=fault_msgs, reps=len(per_rep),
        stop_reason=stop_reason, gap_note=gap_note, cfg=asdict(cfg),
        tamper=sorted({x for ev in tamper_events for x in ev}),
    )
