"""Port of Pure_bad.cs -- always defect (ALLD)."""


class PureBad:
    def reset(self):
        return False

    def response(self, last_action):
        return False
