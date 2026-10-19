"""Generous Tit-for-Tat: retaliate, but forgive a seen defection with prob p.

The classic answer to noise. Pure TFT locked against a twin by one flipped
observation echoes the mistake forever (an "echo war"); random forgiveness
breaks the echo. p ~= 0.1-0.3 is a good range for 5% noise.
"""
import random


class GenerousTFT:
    FORGIVE = 0.2

    def reset(self):
        return True

    def response(self, last_action):
        if last_action:
            return True
        return random.random() < self.FORGIVE
