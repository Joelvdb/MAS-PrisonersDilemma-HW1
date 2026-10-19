# Prisoner's Dilemma Competition (Python)

Write an agent for the iterated prisoner's dilemma with **noisy observations**:
100 rounds per match, and with probability 0.05 you are told the opposite of
what your opponent really did. Every pair of agents plays one match. The highest
total score wins.

The full assignment is in **`Prisoners_Dilemma_Assignment.pdf`**.

**Get the code:** on this page click **Code → Download ZIP** and unzip it (or
`git clone` this repository). Open a terminal in that folder for the commands
below.

## 1. Write your agent

Open `my_agent.py` and fill in two methods:

```python
class MyAgent:
    def reset(self):                   # start of every match
        return True                    # your first move

    def response(self, last_action):   # every round after the first
        return last_action             # noisy view of the opponent's last move
```

`True` = cooperate, `False` = defect. Standard library only, no packages.

## 2. Test it

```bash
python3 practice.py
```

You need Python 3.9 or newer, and nothing else. On Windows, type `python`
(or `py`) instead of `python3`. This plays your agent against
the reference strategies in `baselines/` using the real tournament engine. It
also tells you if your agent crashes or is too slow.

## 3. Write the report

Write `report.pdf`, in English or Hebrew:

1. Is tit-for-tat a good strategy when observations are noisy? Why?
2. Describe your agent's strategy in a few paragraphs.
3. Evaluate your agent empirically, using the results from `practice.py`.

## 4. Submit `ID.zip`, named with your ID number

```
123456789.zip                <- your ID (TZ) number
├── my_agent.py
└── report.pdf
```

Make the zip from inside the folder:

```bash
zip 123456789.zip my_agent.py report.pdf
```

(or select the two files and choose *Compress* on macOS, or *Send to →
Compressed (zipped) folder* on Windows, then rename the zip to your ID).

Check the zip before you upload it:

```bash
python3 practice.py 123456789.zip
```

Then upload the zip to **Moodle**.

## What's in this folder

| | |
|---|---|
| `Prisoners_Dilemma_Assignment.pdf` | the assignment |
| `my_agent.py` | your agent: fill this in |
| `practice.py` | test runner |
| `baselines/` | reference strategies to play against (worth reading) |
| `pdlib/` | the tournament engine (don't edit it) |
| `SCORING.md` | how the scores are computed |
