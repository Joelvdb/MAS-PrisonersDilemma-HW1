#!/usr/bin/env python3
"""Test your agent before you submit it.

    python3 practice.py                # your agent vs. all reference strategies
    python3 practice.py --reps 1000    # tighter numbers
    python3 practice.py --noise 0      # how you do without noise
    python3 practice.py --vs generous_tft --trace   # replay one match move by move
    python3 practice.py 123456789.zip               # check the zip you will submit

It loads every .py file sitting next to it (that is your submission) -- or,
given a zip, the agent inside that zip -- plus
everything in baselines/, plays the same Monte Carlo tournament the real
contest uses, and prints the same leaderboard -- plus your head-to-head row,
so you can see exactly which strategies you gain and lose points against.

If your agent crashes, returns something that is not True/False, or is too
slow, this tells you here rather than on results day.
"""

from __future__ import annotations

import argparse
import random
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from pdlib.engine import Health, make_payoff, match_seed, play_match, safe_move
from pdlib.loader import describe_failure, load_dirs, load_file, load_zip
from pdlib.stats import summarize
from pdlib.tournament import Config, run_montecarlo

SKIP = {"practice.py"}


def load_mine(scan=True):
    mine, failures = [], []
    for path in sorted(HERE.glob("*.py")):
        if path.name in SKIP or path.name.startswith((".", "_")):
            continue
        try:
            mine.append(load_file(path, scan=scan))
        except BaseException as exc:  # noqa: BLE001
            failures.append((path, describe_failure(path, exc)))
    return mine, failures


def load_submission_zip(zpath, scan=True):
    """Load the agent from the zip, and check the zip the way grading will."""
    zpath = Path(zpath)
    if not zpath.is_file():
        return [], [(zpath, "no such file")]
    try:
        c = load_zip(zpath, into=HERE / ".unzipped", scan=scan)
    except BaseException as exc:  # noqa: BLE001
        return [], [(zpath, str(exc))]
    problems = []
    if not re.fullmatch(r"\d+", c.name):
        problems.append(f"the zip must be named with your ID number, e.g. "
                        f"123456789.zip -- not '{zpath.name}'")
    if any("NO WRITE-UP" in n for n in c.notes):
        problems.append("there is no write-up in the zip -- add report.pdf")
    print(f"zip {zpath.name}: team {c.name}, " + "; ".join(c.notes))
    for msg in problems:
        print(f"!! {msg}")
    if not problems:
        print("   the zip looks right.")
    print()
    return [c], []


def smoke(contestant, noise, payoff):
    """Crash / bad-return / speed check against a tit-for-tat probe."""
    h = Health()
    rng = random.Random(4242)
    agent = contestant.new()
    t0 = time.perf_counter()
    move = safe_move(agent.reset, None, True, h, None)
    for _ in range(400):
        obs = move != (rng.random() < 0.1)
        move = safe_move(agent.response, obs, move, h, None)
        if h.faults >= 5:
            break
    us = (time.perf_counter() - t0) * 1e6 / 401
    return h, us


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--reps", type=int, default=300, help="Monte Carlo replications")
    ap.add_argument("--rounds", type=int, default=100)
    ap.add_argument("--noise", type=float, default=0.05)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--vs", default=None, help="replay one match against this agent")
    ap.add_argument("--trace", action="store_true", help="print every round of --vs")
    ap.add_argument("zip", nargs="?", default=None,
                    help="your submission zip, to check it and play its agent")
    args = ap.parse_args(argv)

    if args.zip:
        mine, failures = load_submission_zip(args.zip)
    else:
        mine, failures = load_mine()
    for path, err in failures:
        print(f"!! {path.name} does not load: {err}")
    if not mine:
        print("\nNo agent found. Put your my_agent.py next to practice.py "
              "(it needs a class with reset() and response()).")
        return 1

    others, _ = load_dirs([HERE / "baselines"], scan=False)
    print(f"your agent(s): " + ", ".join(f"{c.name} ({c.cls.__name__})" for c in mine))
    for c in mine:
        if c.notes:
            print("   note: " + "; ".join(c.notes))
        if c.warnings:
            print("   !! not allowed in a submission: " + ", ".join(c.warnings))
    print(f"reference strategies: {len(others)}\n")

    payoff = make_payoff()
    ok = True
    for c in mine:
        h, us = smoke(c, args.noise, payoff)
        if h.faults:
            ok = False
            print(f"!! {c.name}: {h.faults}+ faults -- " + "; ".join(h.errors[:3]))
        elif us > 200:
            print(f"!! {c.name}: slow, {us:.0f} microseconds per move")
    if not ok:
        print("   (fix this: in the real tournament every fault is recorded "
              "next to your name)\n")

    contestants = mine + others

    # --- one match, round by round -----------------------------------------
    if args.vs:
        by_name = {c.name: c for c in contestants}
        if args.vs not in by_name:
            print(f"unknown agent '{args.vs}'. available: "
                  + ", ".join(sorted(by_name)))
            return 1
        a, b = mine[0], by_name[args.vs]
        trace = [] if args.trace else None
        rng = random.Random(match_seed(args.seed, 0, a.name, b.name))
        sa, sb, rounds = play_match(a.new(), b.new(), rounds=args.rounds,
                                    noise=args.noise, payoff=payoff, rng=rng,
                                    trace=trace)
        if trace is not None:
            print(f"{'rnd':>4}  {a.name[:16]:>16}  {b.name[:16]:>16}   payoff")
            for i, (ma, mb, pa, pb) in enumerate(trace, 1):
                print(f"{i:>4}  {'C' if ma else 'D':>16}  {'C' if mb else 'D':>16}"
                      f"   {pa:.0f}/{pb:.0f}")
        both = sum(1 for ma, mb, _, _ in (trace or []) if ma and mb)
        print(f"\n{a.name}: {sa:.0f} ({sa / rounds:.3f} per round)")
        print(f"{b.name}: {sb:.0f} ({sb / rounds:.3f} per round)")
        if trace:
            print(f"mutual cooperation in {both / len(trace):.0%} of rounds")
        return 0

    # --- the practice tournament -------------------------------------------
    cfg = Config(rounds=args.rounds, noise=args.noise, seed=args.seed)
    t0 = time.time()
    result = run_montecarlo(contestants, cfg, reps=args.reps, workers=1)
    summaries = summarize(result.names, result.per_rep, result.faults)

    print(f"{len(contestants)} agents, {args.rounds} rounds per match, "
          f"{args.noise:.0%} noise, {result.reps} replications "
          f"({time.time() - t0:.1f}s)\n")
    mine_names = {c.name for c in mine}
    print(f"{'#':>3}  {'agent':<24}{'score/round':>12}{'95% CI':>10}"
          f"{'win%':>8}{'faults':>8}")
    print("-" * 65)
    for r, s in enumerate(summaries, 1):
        mark = " <-- you" if s.name in mine_names else ""
        print(f"{r:>3}  {s.name[:24]:<24}{s.mean:>12.4f}{s.ci:>10.4f}"
              f"{s.win_rate * 100:>7.1f}%{s.faults or '':>8}{mark}")
    print("\n3.00 = permanent mutual cooperation, 1.00 = permanent mutual "
          "defection,\n2.50 = an endless C/D echo war, 5.00 = exploiting pure "
          "cooperators every round.")

    # --- your head-to-head row ---------------------------------------------
    m = result.pair_matrix()
    for c in mine:
        i = result.names.index(c.name)
        row = sorted(((m[i][j], result.names[j]) for j in range(len(result.names))
                      if j != i), reverse=True)
        print(f"\n{c.name}: mean payoff per round against each opponent")
        for val, name in row:
            them = m[result.names.index(name)][i]
            bar = "#" * int(round(val * 8))
            print(f"   {name[:24]:<26}{val:6.2f}   (they get {them:5.2f})  {bar}")
    print("\nRemember: the tournament ranks on TOTAL points, not on how many "
          "opponents you out-score.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
