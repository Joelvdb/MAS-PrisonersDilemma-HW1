"""Agent API -- the Python port of the C# `interface Agent`.

    bool Response(bool last_action);   ->   def response(self, last_action: bool) -> bool
    bool Reset();                      ->   def reset(self) -> bool

Convention (identical to the C# support code):

    True  == COOPERATE   ("C")
    False == DEFECT      ("D")

`reset()` is called once at the start of every match: it must put the agent
back into its initial state AND return its first move.

`response(last_action)` is called once per round after the first one.
`last_action` is the *observed* previous move of the opponent -- with
probability `noise` (0.05 by default) this observation is FLIPPED, so it is
not necessarily what the opponent really played.  Your own move is never
noisy; only your perception of the opponent is.

A submission may subclass `Agent`, but it does not have to: any class with
`reset()` and `response()` methods is accepted by the loader.
"""

COOPERATE = True
DEFECT = False

# short aliases, handy inside strategies
C = COOPERATE
D = DEFECT


class Agent:
    """Optional base class for a submission."""

    #: optional pretty name; the loader falls back to the file/class name
    name = None

    def reset(self) -> bool:
        """Prepare for a new match and return the first move."""
        raise NotImplementedError

    def response(self, last_action: bool) -> bool:
        """Return this round's move given the (noisy) observed opponent move."""
        raise NotImplementedError

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        return f"<{type(self).__name__}>"
