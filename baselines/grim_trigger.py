"""Grim Trigger: cooperate until one defection is observed, then defect forever.

Included as a control: with 5% noise it is triggered by an illusion within
the first few rounds almost every match, so it should score badly.
"""


class GrimTrigger:
    def __init__(self):
        self.triggered = False

    def reset(self):
        self.triggered = False
        return True

    def response(self, last_action):
        if not last_action:
            self.triggered = True
        return not self.triggered
