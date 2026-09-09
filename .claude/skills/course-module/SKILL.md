---
name: course-module
description: Draft a course module for this curriculum. Use when asked to write, generate, draft or extend a lesson, module or chapter, or to add exercises to an existing one. Produces validated JSON, never Markdown.
---

# Drafting a course module

You are drafting a module for a technical curriculum. The pipeline in this
repository turns your output into a published file. You do not write that
file, and the reason matters: if you never touch the syntax, you can never
break the syntax.

## The one rule that governs everything else

**Return data, not Markdown.** Write a JSON object to `modules/<slug>.json`
that satisfies `pipeline/schema.py`. The renderer produces the `.md`. Do not
write, edit or format a `.md` file at any point. Those files are build
artefacts and a hand edit to one is a validation failure.

Read `pipeline/schema.py` before drafting. It is the only definition of what
is acceptable, and it is stricter than it looks.

## The loop

1. Read `pipeline/schema.py`. Read one existing module in `modules/` to see
   the register and the depth expected.
2. Write `modules/<slug>.json`.
3. Run `python -m pipeline.cli check modules`.
4. If it fails, read the errors, fix the JSON, and run it again.
5. Stop after **three** failed attempts and report what is blocking. Do not
   keep looping: an unbounded repair loop on an impossible request spends
   money until somebody notices the bill.
6. When it passes, run `python -m pipeline.cli render modules`.

Never edit the validator to make your draft pass. If a rule is genuinely
wrong, say so and explain why, and let a human decide. Weakening the check to
fit the output is how a pipeline starts producing well formed rubbish.

## What the validator will reject, so write for it from the start

**Objectives have to be observable.** "Understand retries" cannot be assessed
and is rejected. Write what the learner will be able to do: "Write a retry
policy that stops after a fixed budget".

**Distractors must be wrong for a reason somebody would believe.** An option
that is obviously absurd is not an option, it is filler, and a four option
question with two absurd options is a two option question with inflated
guessing odds. Take your distractors from mistakes learners actually make:
the confusion between two similar things, the step everyone forgets, the
answer that was correct in an earlier version.

**Keep the options a similar length.** The key usually needs a qualifier and
the distractors do not, so an unusually long option teaches people to count
words. The validator rejects an option far longer than the others.

**The key must not appear in the stem.** Rejected automatically.

**Spread the keys.** Across the corpus, no single position may hold more than
45% of the correct answers. This is checked across all modules, not within
one, so consult the existing corpus before choosing. A dominant position is a
winning strategy that requires no knowledge at all.

**Code exercises must actually run.** The validator executes your solution
against your own hidden tests in a subprocess. A solution that does not pass
its own tests fails the build, and so does one that does not terminate.
Give at least four tests and include the boundary cases, not only the happy
path.

**Hidden tests are never rendered.** Neither are keys or explanations. Do not
duplicate them into the body "so the learner can check", because that is the
same as publishing the answer key.

**Never test a function whose solution appears in the body of the same
module.** The learner scrolls up, copies, and passes in ten seconds. If the
lesson demonstrates a function, the exercise asks for a different one that
needs the same reasoning.

## Register

Plain, direct, and concrete. No academic throat clearing, no "in today's fast
paced world". Prefer a real example over an abstract description. If a
paragraph does not tell the reader something they can act on, cut it.

Do not use the long dash anywhere. Use commas, colons or brackets.
