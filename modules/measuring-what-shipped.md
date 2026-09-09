---
slug: measuring-what-shipped
title: Measuring What Actually Shipped
track: ai-engineering
order: 2
minutes: 20
objectives:
- Distinguish structural validation from quality evaluation
- Choose a metric that moves when the system gets worse
- Design a check that runs in CI and blocks a merge
prerequisites:
- validating-llm-output
---

# Measuring What Actually Shipped

Validation and evaluation get used as if they were the same word, and treating them as one thing is how pipelines end up producing well formed rubbish at scale. A schema check tells you the artefact is structurally sound. It cannot tell you the artefact is any good, and no amount of stricter typing will change that.

## What code can decide, and what it cannot

Code can decide whether every field is present, whether the identifiers are unique across the corpus, whether the referenced module exists, and whether the code in the lesson actually runs. All of those are decidable, none of them need judgement, and a program does not get tired at the thirtieth item, which is exactly when a human reviewer starts approving things out of fatigue.

Code cannot decide whether a distractor is plausible to somebody who is still learning the material, whether a question measures the skill or merely the reading of a convoluted sentence, or whether the answer is still correct after the library moved a version. Those stay human, and the entire point of automating the first list is to buy time for the second.

> **A validator with no failing test is not validating**
>
> Keep fixtures that are deliberately broken, one per rule, and assert that each is rejected for the right reason. Without them a refactor can quietly turn a check into a no-op and every run stays green while nothing is being checked.

## Exercises

### validation-versus-evaluation

Which of these can a deterministic script decide on its own, with no human judgement involved?

1. Whether a wrong option is plausible to somebody learning the topic

2. Whether the question measures the skill or the wording of the sentence

3. Whether the answer is still correct after the library changed version

4. Whether every identifier in the corpus is used exactly once

### key-position-drift

Across a course, most correct answers sit in the same position. Why does that matter beyond being untidy?

1. It makes the rendered files noticeably harder to review in a diff

2. It means a learner can pass without knowing any of the material

3. It slows the pipeline down whenever the corpus grows past a point

4. It makes the explanations read repetitively when taken together
