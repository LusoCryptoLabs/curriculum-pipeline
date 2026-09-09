"""
Four layers, in this order, and the order matters.

  1. parse        the front matter is delimited and the YAML parses, with a
                  real parser and never a regular expression
  2. schema       Pydantic, strict, unexpected keys are failures
  3. referential  across the whole corpus: slugs unique, exercise ids unique,
                  prerequisites resolve, and the keys are not all in the same
                  position
  4. executable   the solution actually runs and actually passes its own
                  hidden tests

Layer 4 is the one that gets skipped, and it is where the real failures are.
A module can be perfect YAML, pass every schema rule, and ship a solution
that does not run.

The whole thing fails closed. Nothing half-valid is written and the exit
code is non-zero, because a pipeline that emits a warning and continues is a
pipeline that ships the warning.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from pydantic import ValidationError

from pipeline.render import render
from pipeline.schema import Module

EXEC_TIMEOUT_SECONDS = 5

# Above this share of keys in one position, the winning strategy stops being
# "know the answer" and starts being "always click the same one". Written
# because my own courses shipped 32 items with every key at index 0.
KEY_CONCENTRATION_LIMIT = 0.45
KEY_CHECK_MIN_ITEMS = 8


@dataclass
class Report:
    errors: list[str] = field(default_factory=list)
    checked: int = 0

    @property
    def ok(self) -> bool:
        return not self.errors

    def fail(self, where: str, message: str) -> None:
        self.errors.append(f"{where}: {message}")


# --------------------------------------------------------------------------
# Layer 1 and 2
# --------------------------------------------------------------------------


def parse_front_matter(text: str) -> dict:
    """Delimiters first, then a real YAML parser. Never a regex."""
    if not text.startswith("---\n"):
        raise ValueError("file does not open with a front matter delimiter")
    end = text.find("\n---\n", 4)
    if end == -1:
        raise ValueError("front matter is never closed")
    block = text[4:end]
    loaded = yaml.safe_load(block)
    if not isinstance(loaded, dict):
        raise ValueError("front matter is not a mapping")
    return loaded


def load_module(data: dict) -> Module:
    return Module.model_validate(data)


# --------------------------------------------------------------------------
# Layer 4
# --------------------------------------------------------------------------


def run_hidden_tests(module: Module, report: Report) -> None:
    for ex in module.exercises:
        if ex.kind != "code":
            continue
        lines = [ex.solution, ""]
        for i, t in enumerate(ex.tests):
            lines.append(f"_actual = {t.call}")
            lines.append(f"_expected = {t.expected!r}")
            lines.append(
                "assert _actual == _expected, "
                f"'test {i}: {t.call} gave ' + repr(_actual) + ' expected ' + repr(_expected)"
            )
        script = "\n".join(lines)

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "check.py"
            path.write_text(script, encoding="utf-8")
            try:
                proc = subprocess.run(
                    [sys.executable, str(path)],
                    capture_output=True,
                    text=True,
                    timeout=EXEC_TIMEOUT_SECONDS,
                )
            except subprocess.TimeoutExpired:
                report.fail(ex.id, f"solution did not finish in {EXEC_TIMEOUT_SECONDS}s")
                continue

        if proc.returncode != 0:
            last = (proc.stderr or "").strip().splitlines()
            detail = last[-1] if last else "no stderr"
            report.fail(ex.id, f"solution fails its own hidden tests: {detail}")


# --------------------------------------------------------------------------
# Layer 3, which needs the whole corpus and not one file
# --------------------------------------------------------------------------


def check_corpus(modules: list[Module], report: Report) -> None:
    slugs = [m.slug for m in modules]
    for slug, n in Counter(slugs).items():
        if n > 1:
            report.fail("corpus", f"slug {slug!r} used by {n} modules")

    known = set(slugs)
    for m in modules:
        for p in m.prerequisites:
            if p not in known:
                report.fail(m.slug, f"prerequisite {p!r} does not resolve to a module")

    ids: list[tuple[str, str]] = [(e.id, m.slug) for m in modules for e in m.exercises]
    seen: dict[str, str] = {}
    for ex_id, slug in ids:
        if ex_id in seen:
            report.fail("corpus", f"exercise id {ex_id!r} in both {seen[ex_id]!r} and {slug!r}")
        else:
            seen[ex_id] = slug

    keys = [e.key for m in modules for e in m.exercises if e.kind == "multiple_choice"]
    if len(keys) >= KEY_CHECK_MIN_ITEMS:
        counts = Counter(keys)
        position, n = counts.most_common(1)[0]
        share = n / len(keys)
        if share > KEY_CONCENTRATION_LIMIT:
            report.fail(
                "corpus",
                f"{share:.0%} of keys sit at position {position} across {len(keys)} items "
                f"(limit {KEY_CONCENTRATION_LIMIT:.0%}); the winning strategy is to always "
                "pick the same option",
            )


# --------------------------------------------------------------------------
# Entry points
# --------------------------------------------------------------------------


def validate_source(path: Path, report: Report) -> Module | None:
    """One module, from its JSON source of truth."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        report.fail(path.name, f"not valid JSON: {exc}")
        return None

    try:
        module = load_module(raw)
    except ValidationError as exc:
        for err in exc.errors():
            loc = ".".join(str(p) for p in err["loc"]) or "(root)"
            report.fail(path.name, f"{loc}: {err['msg']}")
        return None

    run_hidden_tests(module, report)
    return module


def check_rendered_is_current(module: Module, md_path: Path, report: Report) -> None:
    """The .md is a build artefact. If someone edited it by hand, say so."""
    if not md_path.exists():
        report.fail(module.slug, "rendered file is missing; run the renderer")
        return
    if md_path.read_text(encoding="utf-8") != render(module):
        report.fail(module.slug, "rendered file is stale or was edited by hand")


def validate_directory(directory: Path) -> Report:
    report = Report()
    modules: list[Module] = []

    for src in sorted(directory.glob("*.json")):
        report.checked += 1
        module = validate_source(src, report)
        if module is None:
            continue
        modules.append(module)
        check_rendered_is_current(module, src.with_suffix(".md"), report)

    check_corpus(modules, report)
    return report
