"""Contrite Tit-for-Tat (Boyd 1989; Wu & Axelrod 1995), standing version.

Each player is in "good standing" unless it defected while the other one was
in good standing.  Contrite TFT defects only against an opponent in bad
standing, and cooperates to restore its own standing after it has been at
fault.

Teaching point: contrition is the classic fix for *action* noise (my move is
executed wrongly, and I know it, so I apologise).  In THIS tournament the
noise is on *observation*: when I retaliate against a defection that never
happened, I sincerely believe I was provoked, so I never consider myself at
fault and the apology never fires.  Expect this agent to behave almost like
plain tit-for-tat here -- which is exactly why the interesting answers to
observation noise are the forgiving ones (generous_tft.py, tit_for_two_tats.py,
forgiving_tft.py).
"""


class ContriteTFT:
    def reset(self):
        self.my_last = True
        self.my_standing = True
        self.their_standing = True
        return True

    def response(self, last_action):
        prev_mine, prev_theirs = self.my_standing, self.their_standing

        # they defected while I was in good standing -> they are at fault
        if not last_action and prev_mine:
            self.their_standing = False
        elif last_action:
            self.their_standing = True

        # I defected while they were in good standing -> I am at fault
        if not self.my_last and prev_theirs:
            self.my_standing = False
        elif self.my_last:
            self.my_standing = True

        move = self.their_standing or not self.my_standing
        self.my_last = move
        return move
