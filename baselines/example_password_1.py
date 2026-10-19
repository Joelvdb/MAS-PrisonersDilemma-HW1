"""Port of PasswordBaseStategy1.cs.

Handshake strategy: play a fixed 5-move "password" and check that the
opponent plays the same one.  A twin is recognised and cooperated with
forever; anybody else is defected against forever.

Under 5% observation noise the handshake is only seen intact with
probability 0.95**5 ~= 0.77, so twins mislabel each other as enemies about a
quarter of the time -- a good illustration of why unforgiving recognition
schemes break in a noisy environment.
"""


class PasswordBaseStrategy1:
    PASSWORD = [False, True, True, False, True]

    def __init__(self):
        self.turn = 0
        self.is_enemy = False

    def reset(self):
        self.turn = 0
        self.is_enemy = False
        return self.PASSWORD[0]

    def response(self, last_action):
        if self.is_enemy:
            return False
        if self.turn >= len(self.PASSWORD):
            return True
        if last_action != self.PASSWORD[self.turn]:
            self.is_enemy = True
        self.turn += 1
        if self.is_enemy:
            return False
        if self.turn >= len(self.PASSWORD):
            return True
        return self.PASSWORD[self.turn]
