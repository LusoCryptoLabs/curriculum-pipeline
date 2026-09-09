"""
Command line entry point. Two verbs and both fail closed.

    python -m pipeline.cli render modules/    write the .md for every source
    python -m pipeline.cli check  modules/    validate everything, exit 1 on any error

`check` is what CI runs. `render` refuses to write anything unless the whole
corpus validates first, so a broken module cannot half-publish.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pipeline.render import render
from pipeline.validate import validate_directory, validate_source, Report


def cmd_check(directory: Path) -> int:
    report = validate_directory(directory)
    if report.ok:
        print(f"ok: {report.checked} modules, every layer passed")
        return 0
    print(f"FAILED: {len(report.errors)} problem(s) across {report.checked} module(s)\n")
    for e in report.errors:
        print(f"  {e}")
    return 1


def cmd_render(directory: Path) -> int:
    report = validate_directory(directory)
    schema_errors = [e for e in report.errors if "stale or was edited" not in e and "is missing" not in e]
    if schema_errors:
        print("refusing to render: the corpus does not validate\n")
        for e in schema_errors:
            print(f"  {e}")
        return 1

    written = 0
    for src in sorted(directory.glob("*.json")):
        module = validate_source(src, Report())
        if module is None:
            continue
        src.with_suffix(".md").write_text(render(module), encoding="utf-8")
        written += 1
    print(f"rendered {written} module(s)")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pipeline")
    parser.add_argument("command", choices=["check", "render"])
    parser.add_argument("directory", type=Path)
    args = parser.parse_args(argv)

    if not args.directory.is_dir():
        print(f"not a directory: {args.directory}")
        return 2

    return cmd_check(args.directory) if args.command == "check" else cmd_render(args.directory)


if __name__ == "__main__":
    sys.exit(main())
