"""
Deterministic rendering: a validated Module in, the exact same bytes out,
every time.

This is the layer that makes the whole thing work, and it is the one people
skip. The model is never asked for Markdown or YAML. It returns data, this
renders the file, and so an entire class of failure stops existing:
unbalanced fences, broken front matter delimiters, indentation drift, a
quote that turns a YAML string into something else.

The other reason to render rather than generate: the diff. Regenerating a
module changes only what actually changed, so a human reviewer can see it.
"""

from __future__ import annotations

import yaml

from pipeline.schema import Callout, CodeBlock, Heading, Module, Paragraph

FRONT_MATTER_KEYS = ("slug", "title", "track", "order", "minutes", "objectives", "prerequisites")


def _front_matter(module: Module) -> str:
    data = {
        "slug": module.slug,
        "title": module.title,
        "track": module.track,
        "order": module.order,
        "minutes": module.minutes,
        "objectives": list(module.objectives),
        "prerequisites": list(module.prerequisites),
    }
    body = yaml.safe_dump(
        data,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
        width=100,
    )
    return f"---\n{body}---\n"


def _block(b: Paragraph | Heading | CodeBlock | Callout) -> str:
    if b.kind == "paragraph":
        return b.text
    if b.kind == "heading":
        return f"## {b.text}"
    if b.kind == "code":
        return f"```{b.language}\n{b.source.rstrip()}\n```"
    if b.kind == "callout":
        return f"> **{b.title}**\n>\n> {b.text}"
    raise AssertionError(f"unhandled block kind: {b.kind!r}")


def _exercises(module: Module) -> str:
    out: list[str] = ["## Exercises"]
    for e in module.exercises:
        if e.kind == "multiple_choice":
            out.append(f"### {e.id}")
            out.append(e.stem)
            for i, opt in enumerate(e.options):
                out.append(f"{i + 1}. {opt}")
        else:
            out.append(f"### {e.id}")
            out.append(e.prompt)
            out.append(f"```python\n{e.starter.rstrip()}\n```")
    return "\n\n".join(out)


def render(module: Module) -> str:
    """Module to file contents. Pure: no clock, no randomness, no I/O.

    Keys and hidden tests are deliberately NOT rendered. A file that carries
    the answers is a file that leaks them the moment it is shared, and the
    published artefact is the thing learners can see.
    """
    parts = [_front_matter(module).rstrip(), f"# {module.title}"]
    parts.extend(_block(b) for b in module.body)
    parts.append(_exercises(module))
    return "\n\n".join(parts).rstrip() + "\n"
