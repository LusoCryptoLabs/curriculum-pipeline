"""
The schema is the contract, and it has exactly one definition.

Three consumers read this file: the Claude Code skill generates against it,
the validator checks against it, and CI gates on it. When those are three
separate definitions they drift inside a month, and the drift is invisible
until a learner hits it.

Strict throughout: `extra="forbid"` means an unexpected key is a failure and
not a shrug. A misspelled field that silently disappears is the failure mode
nobody notices.
"""

from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Strict = ConfigDict(extra="forbid", str_strip_whitespace=True)

SLUG = r"^[a-z0-9]+(-[a-z0-9]+)*$"

Track = Literal["data-science", "machine-learning", "data-engineering", "ai-engineering"]


# --------------------------------------------------------------------------
# Body blocks. The model returns these as data; the renderer produces the
# Markdown. The model never writes the file, so the model can never break the
# file: no unbalanced fences, no broken front matter delimiters, no smart
# quotes sneaking into YAML.
# --------------------------------------------------------------------------


class Paragraph(BaseModel):
    model_config = Strict
    kind: Literal["paragraph"]
    text: str = Field(min_length=40, max_length=1200)


class Heading(BaseModel):
    model_config = Strict
    kind: Literal["heading"]
    text: str = Field(min_length=3, max_length=90)


class CodeBlock(BaseModel):
    model_config = Strict
    kind: Literal["code"]
    language: Literal["python", "sql", "bash", "yaml", "json"]
    source: str = Field(min_length=1, max_length=4000)

    @field_validator("source")
    @classmethod
    def no_fence_in_source(cls, v: str) -> str:
        # A fence inside the source would terminate the block early and turn
        # the rest of the lesson into prose. Caught here rather than in review.
        if "```" in v:
            raise ValueError("code source must not contain a Markdown fence")
        return v


class Callout(BaseModel):
    model_config = Strict
    kind: Literal["callout"]
    title: str = Field(min_length=3, max_length=80)
    text: str = Field(min_length=20, max_length=600)


Block = Annotated[
    Union[Paragraph, Heading, CodeBlock, Callout],
    Field(discriminator="kind"),
]


# --------------------------------------------------------------------------
# Exercises
# --------------------------------------------------------------------------


class HiddenTest(BaseModel):
    """Never rendered into the file. The learner sees categories, not cases."""

    model_config = Strict
    call: str = Field(min_length=1, max_length=200)
    expected: Union[bool, int, float, str]


class MultipleChoice(BaseModel):
    model_config = Strict
    kind: Literal["multiple_choice"]
    id: str = Field(pattern=SLUG)
    stem: str = Field(min_length=15, max_length=400)
    options: list[str] = Field(min_length=3, max_length=5)
    key: int = Field(ge=0)
    explanation: str = Field(min_length=30, max_length=800)

    @model_validator(mode="after")
    def check_options(self) -> "MultipleChoice":
        if self.key >= len(self.options):
            raise ValueError(f"key {self.key} out of range for {len(self.options)} options")

        seen = [o.strip().lower() for o in self.options]
        if len(set(seen)) != len(seen):
            raise ValueError("two options are the same, so neither can be the key")

        # An option that is much longer than the rest is a giveaway: the key
        # usually needs a qualifier and the distractors do not, so learners
        # start counting words instead of reading.
        lengths = [len(o) for o in self.options]
        if max(lengths) > 2.5 * (sum(lengths) / len(lengths)):
            raise ValueError("one option is far longer than the others, which cues the answer")

        # The answer must not sit in the stem.
        key_text = self.options[self.key].strip().lower()
        if len(key_text) > 12 and key_text in self.stem.lower():
            raise ValueError("the stem contains the key verbatim")

        return self


class CodeExercise(BaseModel):
    model_config = Strict
    kind: Literal["code"]
    id: str = Field(pattern=SLUG)
    prompt: str = Field(min_length=30, max_length=800)
    function_name: str = Field(pattern=r"^[a-z_][a-z0-9_]*$")
    starter: str = Field(min_length=1, max_length=2000)
    solution: str = Field(min_length=1, max_length=2000)
    tests: list[HiddenTest] = Field(min_length=4, max_length=20)

    @model_validator(mode="after")
    def check_code(self) -> "CodeExercise":
        if f"def {self.function_name}" not in self.starter:
            raise ValueError(f"starter does not define {self.function_name}")
        if f"def {self.function_name}" not in self.solution:
            raise ValueError(f"solution does not define {self.function_name}")
        if self.starter.strip() == self.solution.strip():
            raise ValueError("starter and solution are identical, so nothing is being asked")
        for t in self.tests:
            if not t.call.startswith(f"{self.function_name}("):
                raise ValueError(f"test call {t.call!r} does not call {self.function_name}")
        return self


Exercise = Annotated[
    Union[MultipleChoice, CodeExercise],
    Field(discriminator="kind"),
]


# --------------------------------------------------------------------------
# The module
# --------------------------------------------------------------------------


class Module(BaseModel):
    model_config = Strict

    slug: str = Field(pattern=SLUG, max_length=60)
    title: str = Field(min_length=6, max_length=80)
    track: Track
    order: int = Field(ge=1, le=99)
    minutes: int = Field(ge=5, le=90)
    objectives: list[str] = Field(min_length=2, max_length=6)
    prerequisites: list[str] = Field(default_factory=list, max_length=6)
    body: list[Block] = Field(min_length=3)
    exercises: list[Exercise] = Field(min_length=1, max_length=8)

    @field_validator("objectives")
    @classmethod
    def objectives_are_observable(cls, v: list[str]) -> list[str]:
        # "Understand X" cannot be assessed, so it cannot be an objective of a
        # module that ends in an assessment.
        banned = ("understand", "learn about", "be aware", "know about", "familiar")
        for o in v:
            low = o.strip().lower()
            if any(low.startswith(b) for b in banned):
                raise ValueError(f"objective is not observable: {o!r}")
        return v

    @field_validator("prerequisites")
    @classmethod
    def prerequisites_are_slugs(cls, v: list[str]) -> list[str]:
        import re

        for p in v:
            if not re.match(SLUG, p):
                raise ValueError(f"prerequisite is not a slug: {p!r}")
        return v

    @model_validator(mode="after")
    def check_module(self) -> "Module":
        ids = [e.id for e in self.exercises]
        if len(set(ids)) != len(ids):
            raise ValueError("duplicate exercise id within the module")
        if self.slug in self.prerequisites:
            raise ValueError("a module cannot be its own prerequisite")
        return self
