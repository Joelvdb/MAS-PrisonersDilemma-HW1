"""
my_agent.py -- your Prisoner's Dilemma agent
============================================
Write your strategy in the class below, test it with `python3 practice.py`,
then submit a zip named with your ID (TZ) number:

    123456789.zip
    |-- my_agent.py                this file
    `-- report.pdf                 your write-up (see the assignment PDF)

The file inside the zip can keep this name -- the zip name is what identifies
you. One agent file per zip.

Rules
-----
* True  == COOPERATE ("C"),  False == DEFECT ("D").
* `reset()`  : called once at the start of every match. Clear all your state
               and return your FIRST move.
* `response(last_action)` : called once per round after the first one.
               `last_action` is your NOISY observation of the opponent's move
               in the previous round -- with probability 0.05 it is flipped.
               Return your move for this round.
* Standard library only. No file, network or process access. Do not try to
  inspect the tournament engine or the opponent object.
* Keep it fast: your two methods are called millions of times across the
  Monte Carlo replications. No sleeping, no heavy computation.
* One agent class per file. The `SUBMISSION = ...` line at the bottom says
  which class plays -- if you rename the class, rename it there too.
"""


class MyAgent:  # rename freely -- but update SUBMISSION at the bottom too
    def __init__(self):
        # __init__ runs once per match too, but do your state setup in reset()
        self.history = []      # what I saw the opponent do
        self.my_moves = []     # what I actually played

    def reset(self):
        """New match: wipe state and return the first move."""
        self.history = []
        self.my_moves = []
        first = True           # start by cooperating
        self.my_moves.append(first)
        return first

    def response(self, last_action):
        """`last_action` = noisy observation of the opponent's previous move."""
        self.history.append(last_action)

        move = last_action     # <-- replace with your strategy

        self.my_moves.append(move)
        return move


# Which class the tournament should run.  Keep this pointing at your agent:
# if you rename `MyAgent` above, change the name here as well.
SUBMISSION = MyAgent
