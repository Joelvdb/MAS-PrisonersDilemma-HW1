"""Pavlov / Win-Stay-Lose-Shift.

Repeat the last move if it earned a good payoff (T or R), switch otherwise.
Self-correcting after mistakes, but exploitable by ALLD.
"""


class Pavlov:
    def __init__(self):
        self.my_last = True

    def reset(self):
        self.my_last = True
        return True

    def response(self, last_action):
        good = last_action                 # opponent cooperated -> I got T or R
        self.my_last = self.my_last if good else (not self.my_last)
        return self.my_last
