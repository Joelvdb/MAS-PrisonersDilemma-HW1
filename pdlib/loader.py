"""Discover and import student submissions from .py files or submission zips.

A submission file may be named anything (e.g. `123456789-987654321.py`, which
is not a legal module name) -- files are loaded by path, so that is fine.

Students submit `ID.zip` (also accepts `ID1-ID2.zip`): the agent .py plus a
write-up.
The team id is read from the zip name, the agent from the one .py inside it
(see load_zip).

Rules:
  * one agent class per file;
  * an agent class is any class DEFINED IN THAT FILE that has callable
    `reset` and `response` attributes (subclassing `pdlib.Agent` is optional);
  * if a file defines several, set `SUBMISSION = MyAgent` at module level, or
    mark the class with `submit = True`, to disambiguate.
"""

from __future__ import annotations

import ast
import importlib.util
import inspect
import re
import shutil
import sys
import zipfile
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

from .agent import Agent

# don't litter the submission folders with __pycache__ directories
sys.dont_write_bytecode = True

# A legitimate agent needs nothing but the standard data-structure and math
# helpers.  Anything else is a heads-up for the instructor -- see scan_source.
ALLOWED_IMPORTS = {
    "random", "math", "collections", "itertools", "functools", "statistics",
    "heapq", "bisect", "typing", "dataclasses", "enum", "abc", "string",
    "operator", "copy", "array", "numbers", "fractions", "decimal", "re",
    "__future__",
}

# Attribute names that only appear when code is reaching for another object's
# internals, the running frames, or the import machinery.  Flagged wherever
# they are used, so building a module name out of string pieces does not help.
DANGEROUS_ATTRS = {
    "f_back", "f_locals", "f_globals", "f_code", "f_builtins",
    "gi_frame", "cr_frame", "gi_code", "cr_code",
    "_getframe", "currentframe", "getouterframes",
    "settrace", "setprofile", "f_trace",
    "get_objects", "get_referrers", "get_referents",
    "__globals__", "__code__", "__closure__", "__subclasses__", "__bases__",
    "__mro__", "__dict__", "__class__", "__self__", "__func__", "__module__",
    "modules", "__builtins__", "__loader__", "__spec__",
}

# Bare names whose mere use is worth a look.
DANGEROUS_NAMES = {
    "eval", "exec", "compile", "__import__", "globals", "vars",
    "open", "setattr", "delattr", "memoryview", "breakpoint",
}

# Kept for the self-check: the old text patterns still match the obvious cases.
SUSPICIOUS = [
    (r"\b__import__\s*\(", "dynamic import"),
    (r"\b(eval|exec|compile)\s*\(", "dynamic code execution"),
    (r"sys\._getframe|inspect\.(stack|currentframe)", "reading the caller's frame"),
]


# --------------------------------------------------------------------------
# team names from file names
# --------------------------------------------------------------------------
# Students never name files the way the spec says.  Everything below is
# accepted and normalised to the same team id "<smaller>-<larger>":
#
#   123456789-987654321.py        the spec
#   123456789_987654321.py        underscore instead of dash
#   ID123456789-ID987654321.py    "ID" prefixes, any case
#   123456789 - 987654321.py      spaces around the separator
#   987654321-123456789.py        the two ids in the other order
#   123456789-987654321 (1).py    the copy your mail client made
#   123456789-987654321_final.py  trailing junk: final / copy / v2 / submission
#
# A file whose name does not look like a pair of ids keeps its stem as its
# name, so `example_tit_for_tat.py` and the baselines still work.

TEAM_RE = re.compile(
    r"""^\s*
        (?:id[\s._-]*)? (?P<a>\d{3,12}) \s*
        [-_.\s]+ \s*
        (?:id[\s._-]*)? (?P<b>\d{3,12})
        (?:[\s._-]*(?:\(\d+\)|copy|final|fixed|new|last|v\d+|submission|hw\d*))*
        \s*$""",
    re.IGNORECASE | re.VERBOSE,
)

# the template, submitted without being renamed
TEMPLATE_RE = re.compile(
    r"^_*(?:template[\s._-]*)?id[\s._-]*[xyz12ab]?[-_.\s]+id[\s._-]*[xyz12ab]?"
    r"(?:[\s._-]*template)?\s*$",
    re.IGNORECASE,
)


# a single id, for someone who submits alone: 123456789.zip
SINGLE_RE = re.compile(
    r"""^\s*(?:id[\s._-]*)? (?P<a>\d{5,12})
        (?:[\s._-]*(?:\(\d+\)|copy|final|fixed|new|last|v\d+|submission|hw\d*))*
        \s*$""",
    re.IGNORECASE | re.VERBOSE,
)


def team_name(stem: str) -> tuple[str, list]:
    """Map a file stem to (display name, notes).

    The display name is what appears on the leaderboard and what duplicate
    detection compares, so two spellings of the same pair collapse into one.
    """
    notes = []
    if TEMPLATE_RE.match(stem):
        notes.append("looks like the unrenamed template file")
        return stem.strip(), notes

    m = TEAM_RE.match(stem)
    if not m:
        single = SINGLE_RE.match(stem)
        if single:
            canonical = single.group("a")
            if canonical != stem.strip():
                notes.append(f"file name '{stem}' read as team {canonical}")
            return canonical, notes
        if re.search(r"\d{3,12}[-_.\s]+\d{3,12}", stem):
            notes.append(f"non-standard file name '{stem}' -- expected ID1-ID2")
        return stem.strip(), notes

    a, b = m.group("a"), m.group("b")
    if int(a) > int(b):
        a, b = b, a
    canonical = f"{a}-{b}"
    if canonical != stem.strip():
        notes.append(f"file name '{stem}' read as team {canonical}")
    return canonical, notes


@dataclass
class Contestant:
    """A loaded submission: how to build fresh instances of it, plus its id."""
    name: str                 # display name -> normalised team id (see team_name)
    cls: type                 # the agent class
    path: Path
    warnings: list = field(default_factory=list)
    notes: list = field(default_factory=list)   # file-name remarks, not problems
    source: Path | None = None  # the submitted zip, when `path` came out of one

    @property
    def submitted(self) -> Path:
        return self.source or self.path

    def new(self):
        return self.cls()


def scan_source(path: Path) -> list[str]:
    """Flag code that reaches outside a plain strategy -- for a human to read.

    This is a heads-up list, not a sandbox: a submission still runs.  The scan
    walks the parse tree rather than the raw text, so splitting a name into
    string pieces (``__import__("g" + "c")``) does not hide it -- the
    ``__import__`` call, the frame/gc attributes and the module monkey-patch
    are all visible in the AST.
    """
    src = path.read_text(encoding="utf-8", errors="replace")
    try:
        tree = ast.parse(src)
    except SyntaxError:
        # won't import either; the regex fallback still names the obvious ones
        return sorted({why for pat, why in SUSPICIOUS if re.search(pat, src)})

    reasons: set[str] = set()
    imported: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                root = a.name.split(".")[0]
                imported.add(a.asname or root)
                if root not in ALLOWED_IMPORTS:
                    reasons.add(f"imports '{a.name}' (only random/math/... are expected)")
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".")[0]
            if root and root not in ALLOWED_IMPORTS:
                reasons.add(f"imports from '{node.module}'")
        elif isinstance(node, ast.Attribute):
            if node.attr in DANGEROUS_ATTRS:
                reasons.add(f"touches '.{node.attr}' (object/frame/import internals)")
        elif isinstance(node, ast.Name):
            if node.id in DANGEROUS_NAMES:
                reasons.add(f"uses '{node.id}'")
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            if node.value in DANGEROUS_ATTRS or node.value in DANGEROUS_NAMES:
                reasons.add(f"string literal '{node.value}' (name built to dodge the scan?)")

    # assigning to <imported module>.<attr>, or to any .response/.reset/.random,
    # is monkey-patching -- the one thing a strategy never needs to do
    for node in ast.walk(tree):
        if isinstance(node, (ast.Assign, ast.AugAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for t in targets:
                if isinstance(t, ast.Attribute):
                    root = t.value
                    while isinstance(root, ast.Attribute):
                        root = root.value
                    base = root.id if isinstance(root, ast.Name) else "?"
                    if base in imported or t.attr in {"response", "reset", "random", "seed"}:
                        reasons.add(f"reassigns '{base}.{t.attr}' (monkey-patching)")
    return sorted(reasons)


def _looks_like_agent(obj) -> bool:
    return (
        inspect.isclass(obj)
        and obj is not Agent
        and callable(getattr(obj, "reset", None))
        and callable(getattr(obj, "response", None))
    )


def load_file(path: Path, scan: bool = True) -> Contestant:
    path = Path(path).resolve()
    mod_name = "submission_" + re.sub(r"\W", "_", path.stem)
    spec = importlib.util.spec_from_file_location(mod_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = module
    spec.loader.exec_module(module)  # may raise -- caller reports it

    explicit = getattr(module, "SUBMISSION", None)
    if _looks_like_agent(explicit):
        cls = explicit
    else:
        found = [
            obj for _, obj in vars(module).items()
            if _looks_like_agent(obj) and obj.__module__ == mod_name
        ]
        marked = [c for c in found if getattr(c, "submit", False)]
        if marked:
            found = marked
        if not found:
            raise ImportError(
                f"{path.name}: no class with reset()/response() found"
            )
        if len(found) > 1:
            names = ", ".join(c.__name__ for c in found)
            raise ImportError(
                f"{path.name}: {len(found)} agent classes ({names}); "
                "set SUBMISSION = <class> at module level to pick one"
            )
        cls = found[0]

    name, notes = team_name(path.stem)
    return Contestant(
        name=name,
        cls=cls,
        path=path,
        warnings=scan_source(path) if scan else [],
        notes=notes,
    )


def describe_failure(path: Path, exc: BaseException) -> str:
    """A load error plus, where we can guess it, the fix.

    The commonest one by far: a pair renames the agent class in the template
    and forgets the `SUBMISSION = ...` line at the bottom, so the module dies
    at import with a bare NameError and the submission never plays.
    """
    msg = f"{type(exc).__name__}: {exc}"
    try:
        src = Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return msg
    if isinstance(exc, NameError) and re.search(r"^\s*SUBMISSION\s*=", src, re.M):
        msg += ("  -- the 'SUBMISSION = ...' line names a class that does not "
                "exist; it must match the agent class in this file")
    elif isinstance(exc, (SyntaxError, IndentationError)):
        msg += "  -- the file is not valid Python, so nothing in it ran"
    return msg


# --------------------------------------------------------------------------
# submission zips
# --------------------------------------------------------------------------
# Inside a zip we want exactly one agent .py.  Students often zip the whole
# pack folder, so the pack's own files are ignored rather than counted.

UNZIP_DIR = ".unzipped"
ZIP_IGNORE_PARTS = {"pdlib", "baselines", "__MACOSX", "__pycache__"}
ZIP_IGNORE_NAMES = {"practice.py"}
WRITEUP_EXT = {".pdf", ".docx", ".doc", ".odt", ".md", ".txt"}
WRITEUP_IGNORE = {"readme.md", "scoring.md"}
MAX_AGENT_BYTES = 1 << 20


def _zip_members(z: zipfile.ZipFile):
    for info in z.infolist():
        if info.is_dir():
            continue
        parts = PurePosixPath(info.filename).parts
        if any(p in ZIP_IGNORE_PARTS or p.startswith((".", "_")) for p in parts):
            continue
        yield info, PurePosixPath(info.filename).name


def unpack_zip(zpath: Path, into: Path) -> tuple[Path, list]:
    """Write the one agent file in a submission zip to `into/<zip stem>.py`.

    Naming the copy after the zip keeps the team id coming from the zip name,
    including in the worker processes, which reload agents by path.  Only
    that one file is written, never to a path taken from the archive.
    """
    notes = []
    with zipfile.ZipFile(zpath) as z:
        members = list(_zip_members(z))
        agents = [i for i, name in members
                  if name.lower().endswith(".py") and name not in ZIP_IGNORE_NAMES]
        writeups = [name for i, name in members
                    if PurePosixPath(name).suffix.lower() in WRITEUP_EXT
                    and name.lower() not in WRITEUP_IGNORE]
        if not agents:
            hint = ""
            if any(name.lower().endswith(".zip") for _, name in members):
                hint = (" -- it contains zips: if this is a bulk download, "
                        "extract it into this folder first")
            raise ImportError(f"{zpath.name}: no agent .py file inside the zip{hint}")
        if len(agents) > 1:
            names = ", ".join(i.filename for i in agents)
            raise ImportError(f"{zpath.name}: {len(agents)} .py files ({names}); "
                              "the zip must hold exactly one agent file")
        info = agents[0]
        if info.file_size > MAX_AGENT_BYTES:
            raise ImportError(f"{zpath.name}: {info.filename} is "
                              f"{info.file_size // 1024} KB, too big for an agent")
        data = z.read(info)
    into.mkdir(parents=True, exist_ok=True)
    out = into / (zpath.stem + ".py")
    out.write_bytes(data)
    notes.append(f"agent '{info.filename}' from {zpath.name}")
    if not writeups:
        notes.append("NO WRITE-UP in the zip (expected report.pdf)")
    return out, notes


def load_zip(zpath: Path, into: Path | None = None, scan: bool = True) -> Contestant:
    """Load the agent out of a submission zip; the team id is the zip name."""
    zpath = Path(zpath).resolve()
    into = into or zpath.parent / UNZIP_DIR
    out, notes = unpack_zip(zpath, into)
    try:
        c = load_file(out, scan=scan)
    except BaseException as exc:  # noqa: BLE001 -- name the zip, explain the .py
        raise ImportError(describe_failure(out, exc)) from exc
    c.source = zpath
    c.notes = notes + c.notes
    return c


def load_dirs(dirs, scan: bool = True):
    """Load every .py and submission .zip in the given directories.

    Zips are also picked up one folder down, which is how a Moodle "download
    all submissions" unpacks (one folder per student).

    Returns (contestants, failures) where failures is [(path, error_string)].
    Two files that resolve to the same team id (say `123-456.py` and
    `456_123 (1).py`) are a duplicate submission: the first one plays and the
    second is reported, so nobody quietly enters the tournament twice.
    """
    contestants, failures = [], []
    seen = {}
    for d in dirs:
        d = Path(d)
        if not d.is_dir():
            continue
        unzipped = d / UNZIP_DIR
        if unzipped.is_dir():
            shutil.rmtree(unzipped)  # never play a stale copy
        zips = sorted(d.glob("*.zip")) + sorted(d.glob("*/*.zip"))
        for path in zips + sorted(d.glob("*.py")):  # a zip beats a stray .py
            rel = path.relative_to(d).parts
            if any(p.startswith(("_", ".")) for p in rel):
                continue
            try:
                if path.suffix == ".zip":
                    c = load_zip(path, into=unzipped, scan=scan)
                else:
                    c = load_file(path, scan=scan)
            except BaseException as exc:  # noqa: BLE001
                failures.append((path, str(exc) if path.suffix == ".zip"
                                 else describe_failure(path, exc)))
                continue
            key = c.name.casefold()
            if key in seen:
                failures.append((path, f"duplicate of '{seen[key].name}' "
                                       f"({seen[key].submitted.name}) -- same team id"))
                continue
            seen[key] = c
            contestants.append(c)
    return contestants, failures
