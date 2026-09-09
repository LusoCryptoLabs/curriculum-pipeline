---
slug: validating-llm-output
title: Validating Non-Deterministic Output
track: ai-engineering
order: 1
minutes: 25
objectives:
- Explain why the guarantee lives in the gate rather than in the model
- Write a Pydantic model that rejects unexpected keys as well as missing ones
- Decide when a pipeline should fail closed rather than pass the output through
prerequisites: []
---

# Validating Non-Deterministic Output

A language model is a probabilistic component sitting inside a system that has to be reliable. You cannot make the model produce valid output every single time, and any design that depends on it doing so is a design waiting to page you at three in the morning. What you can do is guarantee that invalid output never leaves the pipeline.

## Do not ask the model for the file

The single largest reduction in failure comes before any validation runs. Ask the model for the data, not the formatted artefact. Have it return structured JSON against a schema, validate that object, and then render the Markdown or the YAML yourself from the validated result. The model never touches the syntax, so the model can never break the syntax: no unbalanced code fences, no broken front matter delimiters, no quote that silently changes what a YAML value means.

```python
from pydantic import BaseModel, ConfigDict, Field

class Lesson(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slug: str = Field(pattern=r"^[a-z0-9-]+$")
    minutes: int = Field(ge=5, le=90)
    objectives: list[str] = Field(min_length=2)
```

> **extra="forbid" is the part people miss**
>
> Without it, a misspelled field is simply dropped and the object still validates. The lesson ships with no objectives and nothing anywhere reports a problem. Rejecting unexpected keys catches the failure that is otherwise invisible.

## Fail closed, with a budget

When validation fails, feed the validator error back to the model and try again, but bound the number of attempts. Without a limit, a repair loop on a genuinely impossible request will spend money until somebody notices the bill. After the budget is exhausted the pipeline emits nothing at all. Publishing nothing is a recoverable state; publishing something wrong is not.

## Exercises

### why-render-yourself

Why does having code produce the Markdown, rather than the model, remove a whole class of failure?

1. Because deterministic code runs considerably faster than a model call does

2. Because the model never writes syntax, so it cannot produce broken syntax

3. Because the resulting files end up smaller and cheaper to store at scale

4. Because it removes any need to validate the object that the model returned

### forbid-extra-keys

A schema accepts unexpected keys. A field is misspelled in the generated object. What happens?

1. Validation fails and the offending field name is reported clearly

2. Validation fails but the error message points at the wrong field entirely

3. It validates, the field is dropped, and nothing anywhere reports it

4. It validates and the misspelled key is preserved in the final artefact

### retry-policy

Write should_retry(status_code, attempt, max_attempts). Retry on 429 and on any 5xx, because those are transient. Never retry on any other 4xx, because the request itself is the problem and repeating it just costs money. Stop once attempt has reached max_attempts.

```python
def should_retry(status_code, attempt, max_attempts):
    # attempt is zero based: 0 is the first try
    pass
```
