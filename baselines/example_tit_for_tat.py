"""Port of Tit_for_tat.cs -- cooperate first, then copy what you saw."""


class TitForTat:
    def reset(self):
        return True

    def response(self, last_action):
        return last_action
