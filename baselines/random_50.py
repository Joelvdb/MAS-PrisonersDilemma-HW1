"""Coin flip. The noise floor of the tournament."""
import random


class Random50:
    def reset(self):
        return random.random() < 0.5

    def response(self, last_action):
        return random.random() < 0.5
