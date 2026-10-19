"""Forgiving Tit-for-Tat: punish an observed defection exactly once, then
return to cooperation no matter what the opponent did in the meantime.

Deterministic cousin of generous_tft.py.  It cannot enter an echo war,
because it never retaliates against the retaliation it provoked -- but it is
still fully exploitable by a permanent defector, which it meets with
alternating C/D (average 2.5 per round against ALLD's 2.5).
"""


class ForgivingTFT:
    def reset(self):
        self.punishing = False
        return True

    def response(self, last_action):
        if self.punishing:      # I just punished; forgive unconditionally
            self.punishing = False
            return True
        if not last_action:
            self.punishing = True
            return False
        return True
