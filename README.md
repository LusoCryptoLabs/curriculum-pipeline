# Curriculum Pipeline

A Claude Code skill that drafts course modules, and a deterministic validator
that decides whether they ship.

The model drafts. Code decides. Nothing half valid is written.

```bash
pip install -r requirements.txt
python -m pytest tests/ -q          # 23 tests, the validator's own suite
python -m pipeline.cli check modules
python -m pipeline.cli render modules
```

## The idea

You cannot guarantee that a language model produces valid output every time.
You can guarantee that invalid output never leaves the pipeline. The
guarantee lives in the gate, not in the model.

The largest single reduction in failure happens before any validation runs:
**the model is never asked for the file.** It returns structured JSON against
a schema; `pipeline/render.py` produces the Markdown and the YAML front
matter from the validated object. The model never touches the syntax, so the
model cannot break the syntax. Unbalanced fences, broken front matter
delimiters and quote characters that change what a YAML value means stop
being possible failures rather than becoming rarer ones.

Rendering is pure. Same object, same bytes, so regenerating a module produces
a diff a human can actually review.

## Four layers

| | Layer | What it decides |
|---|---|---|
| 1 | parse | The front matter is delimited and the YAML parses, using a real parser and never a regular expression |
| 2 | schema | Pydantic v2 with `extra="forbid"`, so an unexpected key is a failure and not a shrug |
| 3 | referential | Across the whole corpus: slugs unique, exercise ids unique, prerequisites resolve, keys not concentrated in one position |
| 4 | executable | Every code solution runs in a subprocess against its own hidden tests, with a timeout |

**Layer 4 is the one that gets skipped**, and it is where the real failures
live. A module can be perfect YAML, satisfy every schema rule, and ship a
solution that does not run.

**Layer 3 catches defects that do not exist in any single file.** The key
concentration check is there because my own published courses shipped 32
multiple choice items with every correct answer at index 0. Clicking the
first option eight times passed the course and issued a certificate. Nobody
complained, and nothing was wrong with any individual item: every one had a
defensible key and plausible distractors. The defect existed only in the
distribution, which is why it survived review and only showed up in the data.

## Validation is not evaluation

Code decides whether the artefact is well formed. It cannot decide whether it
is any good.

Decidable, so automated: fields present, identifiers unique, references
resolve, code runs, keys spread, no option far longer than the rest, key not
sitting in the stem.

Not decidable, so still human: whether a distractor is plausible to somebody
still learning, whether an item measures the skill or the wording, whether
the key is still correct after the library moved a version.

The point of automating the first list is to buy attention for the second.

## Fail closed

On failure the pipeline emits nothing and exits non-zero. `render` refuses to
write anything unless the whole corpus validates first, so one broken module
cannot half publish. The repair loop in the skill is bounded at three
attempts, because an unbounded loop on an impossible request spends money
until somebody notices the bill.

## The validator has its own tests

`tests/test_validation.py` holds one deliberately broken case per rule, and
each asserts on the reason for rejection rather than only on the failure.
Without that, a refactor turns a check into a no-op, every run stays green,
and nothing is being checked.

The suite includes a solution that is schema clean, plausible and wrong (it
forgets the attempt budget) to prove layer 4 catches it, and one that never
terminates to prove the timeout works.

## Layout

```
.claude/skills/course-module/   the skill: how to draft, and the repair loop
pipeline/schema.py              the contract, one definition, three consumers
pipeline/render.py              validated object to bytes, pure and deterministic
pipeline/validate.py            the four layers
pipeline/cli.py                 check and render, both fail closed
modules/*.json                  source of truth
modules/*.md                    build artefacts, never edited by hand
tests/                          the validator's own suite
.github/workflows/ci.yml        the gate
```

The CI job also re-renders and runs `git diff --exit-code`, so a hand edit to
a build artefact fails the merge.
