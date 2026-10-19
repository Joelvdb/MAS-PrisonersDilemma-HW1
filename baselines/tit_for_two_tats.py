"""Tit-for-Two-Tats: defect only after two defections in a row.

Noise-tolerant by construction -- a single flipped observation is ignored,
and two consecutive flips happen only 0.25% of the time.
"""


class TitForTwoTats:
    def __init__(self):
        self.prev = True

    def reset(self):
        self.prev = True
        return True

    def response(self, last_action):
        move = True if (last_action or self.prev) else False
        self.prev = last_action
        return move
