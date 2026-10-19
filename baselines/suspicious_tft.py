"""Suspicious Tit-for-Tat: same as TFT but opens with a defection."""


class SuspiciousTFT:
    def reset(self):
        return False

    def response(self, last_action):
        return last_action
