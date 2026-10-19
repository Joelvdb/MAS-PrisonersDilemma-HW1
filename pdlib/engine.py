"""Match engine: one noisy iterated prisoner's dilemma game between two agents."""

from __future__ import annotations

import hashlib
import random
import signal
import struct
from contextlib import contextmanager
from dataclasses import dataclass, field


def make_payoff(T: float = 5, R: float = 3, P: float = 1, S: float = 0):
    """Payoff table.  Defaults match the C# matrix {{3,0},{5,1}}.

    Returns {(my_move, their_move): (my_payoff, their_payoff)} with True==C.
    Requires T > R > P > S and 2R > T + S for a proper prisoner's dilemma.
    """
    return {
        (True, True): (R, R),    # both cooperate  -> Reward
        (True, False): (S, T),   # I cooperate, they defect -> Sucker / Temptation
        (False, True): (T, S),
        (False, False): (P, P),  # both defect -> Punishment
    }


DEFAULT_PAYOFF = make_payoff()


# --------------------------------------------------------------------------
# calling untrusted student code safely
# --------------------------------------------------------------------------

class _Timeout(Exception):
    pass


@contextmanager
def _time_limit(seconds: float):
    """Wall-clock limit for a single call (POSIX main thread only)."""
    def _handler(signum, frame):
        raise _Timeout(f"move exceeded {seconds}s")

    old = signal.signal(signal.SIGALRM, _handler)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old)


@dataclass
class Health:
    """Per-agent bookkeeping for crashes / bad return values / timeouts."""
    faults: int = 0
    errors: list = field(default_factory=list)

    def record(self, msg: str) -> None:
        self.faults += 1
        if len(self.errors) < 5 and msg not in self.errors:
            self.errors.append(msg)


def safe_move(fn, arg, fallback: bool, health: Health, timeout: float | None) -> bool:
    """Call an agent method; never let it break the tournament.

    On any exception / timeout / non-boolean return we count a fault and fall
    back to repeating the agent's own previous move (the most neutral choice:
    it neither hands the opponent a free exploit nor lets a broken agent
    profit from defecting).
    """
    try:
        if timeout:
            with _time_limit(timeout):
                move = fn() if arg is None else fn(arg)
        else:
            move = fn() if arg is None else fn(arg)
    except BaseException as exc:  # noqa: BLE001 - student code may raise anything
        health.record(f"{type(exc).__name__}: {exc}")
        return fallback

    if move is True or move is False:
        return move
    if isinstance(move, (int, float)) and move in (0, 1):  # tolerate 0/1
        return bool(move)
    health.record(f"returned {move!r}, expected True/False")
    return fallback


# --------------------------------------------------------------------------
# integrity guard: catch an agent that patches the engine or the random module
# --------------------------------------------------------------------------
# Agents run in-process, so a determined one can reassign engine functions or
# random.random to tilt everyone else's matches.  We snapshot the originals,
# and after every replication check that nothing was swapped out -- restoring
# it and recording the event, which is reported loudly next to the results.

_ORIGINALS: dict = {}
TAMPER_EVENTS: list = []


def snapshot_integrity() -> None:
    _ORIGINALS.clear()
    _ORIGINALS["engine.safe_move"] = (globals(), "safe_move", safe_move)
    _ORIGINALS["random.random"] = (random.__dict__, "random", random.random)
    _ORIGINALS["random.seed"] = (random.__dict__, "seed", random.seed)
    TAMPER_EVENTS.clear()


def verify_integrity(restore: bool = True) -> list:
    """Return the names of anything that was swapped out, restoring each."""
    hit = []
    for label, (ns, attr, original) in _ORIGINALS.items():
        if ns.get(attr) is not original:
            hit.append(label)
            if restore:
                ns[attr] = original
    if hit:
        TAMPER_EVENTS.append(tuple(hit))
    return hit


# --------------------------------------------------------------------------
# reproducible per-match randomness
# --------------------------------------------------------------------------

def match_seed(base_seed: int, rep: int, name_a: str, name_b: str) -> int:
    """Deterministic seed for one (replication, pair) match.

    Derived from the *names*, not from positions in the agent list, so that
    adding or removing a submission does not change the noise any other pair
    sees.  This is what makes results reproducible and comparable across runs.
    """
    lo, hi = sorted((name_a, name_b))
    digest = hashlib.blake2b(
        f"{base_seed}|{rep}|{lo}|{hi}".encode("utf-8"), digest_size=8
    ).digest()
    return struct.unpack("<Q", digest)[0]


# --------------------------------------------------------------------------
# the match
# --------------------------------------------------------------------------

def play_match(
    agent_a,
    agent_b,
    rounds: int = 100,
    noise: float = 0.05,
    payoff=DEFAULT_PAYOFF,
    rng: random.Random | None = None,
    health_a: Health | None = None,
    health_b: Health | None = None,
    move_timeout: float | None = None,
    rounds_jitter: int = 0,
    trace: list | None = None,
):
    """Play one match and return (score_a, score_b).

    Timeline (one clean, unshifted round per scored round):

        round 1 : both agents play the move returned by reset()
        round t : each agent plays response(<noisy view of opponent's move
                  in round t-1>)

    Both noise draws are taken every round, in a fixed order, so that the
    random stream stays aligned no matter what the agents do.
    """
    rng = rng or random.Random()
    health_a = health_a or Health()
    health_b = health_b or Health()

    # Seed the *global* random module from the match seed, so that agents that
    # use random.random() stay reproducible while still behaving differently in
    # every match and every replication.  The engine's own noise stream is a
    # separate Random instance, so nothing an agent draws can shift it.
    random.seed(rng.getrandbits(64))

    if rounds_jitter:
        rounds = rng.randint(max(1, rounds - rounds_jitter), rounds + rounds_jitter)

    # bind locally: an agent that reassigns engine.safe_move mid-match cannot
    # change the function this match actually calls
    safe_move = globals()["safe_move"]

    a_move = safe_move(agent_a.reset, None, True, health_a, move_timeout)
    b_move = safe_move(agent_b.reset, None, True, health_b, move_timeout)

    score_a = score_b = 0.0
    for t in range(rounds):
        pa, pb = payoff[(a_move, b_move)]
        score_a += pa
        score_b += pb
        if trace is not None:
            trace.append((a_move, b_move, pa, pb))
        if t == rounds - 1:
            break

        # noisy observations (independent draws, exactly like the C# code)
        obs_a = b_move != (rng.random() < noise)   # flip with prob = noise
        obs_b = a_move != (rng.random() < noise)

        a_next = safe_move(agent_a.response, obs_a, a_move, health_a, move_timeout)
        b_next = safe_move(agent_b.response, obs_b, b_move, health_b, move_timeout)
        a_move, b_move = a_next, b_next

    return score_a, score_b, rounds
