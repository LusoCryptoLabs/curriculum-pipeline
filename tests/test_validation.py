"""
One deliberately broken fixture per rule, and each has to be rejected for the
right reason.

This file exists because a validator with no failing test is a validator that
quietly stopped validating. A refactor turns a check into a no-op, every run
stays green, and nothing is being checked. Asserting on the message, not just
on the failure, is what catches that.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from pipeline.render import render
from pipeline.schema import Module
from pipeline.validate import (
    Report,
    check_corpus,
    parse_front_matter,
    run_hidden_tests,
    validate_directory,
)

MODULES = Path(__file__).resolve().parent.parent / "modules"


@pytest.fixture
def valid() -> dict:
    return json.loads((MODULES / "validating-llm-output.json").read_text(encoding="utf-8"))


def broken(base: dict, **changes) -> dict:
    out = copy.deepcopy(base)
    out.update(changes)
    return out


def message_of(exc: ValidationError) -> str:
    return " | ".join(e["msg"] for e in exc.errors())


# --------------------------------------------------------------------------
# The corpus as shipped must pass every layer, or the rest of this file is
# testing nothing.
# --------------------------------------------------------------------------


def test_shipped_corpus_passes():
    report = validate_directory(MODULES)
    assert report.ok, report.errors
    assert report.checked >= 2


# --------------------------------------------------------------------------
# Layer 2, schema
# --------------------------------------------------------------------------


def test_unexpected_key_is_rejected(valid):
    with pytest.raises(ValidationError) as exc:
        Module.model_validate(broken(valid, difficulty="hard"))
    assert "Extra inputs are not permitted" in message_of(exc.value)


def test_misspelled_field_does_not_silently_pass(valid):
    data = copy.deepcopy(valid)
    data["objectivs"] = data.pop("objectives")
    with pytest.raises(ValidationError):
        Module.model_validate(data)


def test_unobservable_objective_is_rejected(valid):
    data = broken(valid, objectives=["Understand retries", "Write a retry policy"])
    with pytest.raises(ValidationError) as exc:
        Module.model_validate(data)
    assert "not observable" in message_of(exc.value)


def test_key_out_of_range_is_rejected(valid):
    data = copy.deepcopy(valid)
    data["exercises"][0]["key"] = 9
    with pytest.raises(ValidationError) as exc:
        Module.model_validate(data)
    assert "out of range" in message_of(exc.value)


def test_duplicate_options_are_rejected(valid):
    data = copy.deepcopy(valid)
    data["exercises"][0]["options"][2] = data["exercises"][0]["options"][0]
    with pytest.raises(ValidationError) as exc:
        Module.model_validate(data)
    assert "the same" in message_of(exc.value)


def test_one_very_long_option_is_rejected(valid):
    data = copy.deepcopy(valid)
    data["exercises"][0]["options"][1] = "Because " + ("the model never writes syntax " * 12)
    with pytest.raises(ValidationError) as exc:
        Module.model_validate(data)
    assert "longer than the others" in message_of(exc.value)


def test_key_present_in_the_stem_is_rejected(valid):
    data = copy.deepcopy(valid)
    ex = data["exercises"][0]
    ex["stem"] = f"Which is true: {ex['options'][ex['key']]}?"
    with pytest.raises(ValidationError) as exc:
        Module.model_validate(data)
    assert "contains the key" in message_of(exc.value)


def test_fence_inside_a_code_block_is_rejected(valid):
    data = copy.deepcopy(valid)
    for block in data["body"]:
        if block["kind"] == "code":
            block["source"] = "x = 1\n```\nnot code any more"
            break
    with pytest.raises(ValidationError) as exc:
        Module.model_validate(data)
    assert "Markdown fence" in message_of(exc.value)


def test_starter_identical_to_solution_is_rejected(valid):
    data = copy.deepcopy(valid)
    code = next(e for e in data["exercises"] if e["kind"] == "code")
    code["starter"] = code["solution"]
    with pytest.raises(ValidationError) as exc:
        Module.model_validate(data)
    assert "nothing is being asked" in message_of(exc.value)


def test_test_calling_the_wrong_function_is_rejected(valid):
    data = copy.deepcopy(valid)
    code = next(e for e in data["exercises"] if e["kind"] == "code")
    code["tests"][0]["call"] = "some_other_function(1, 2, 3)"
    with pytest.raises(ValidationError) as exc:
        Module.model_validate(data)
    assert "does not call" in message_of(exc.value)


def test_self_prerequisite_is_rejected(valid):
    data = broken(valid, prerequisites=[valid["slug"]])
    with pytest.raises(ValidationError) as exc:
        Module.model_validate(data)
    assert "own prerequisite" in message_of(exc.value)


# --------------------------------------------------------------------------
# Layer 4, executable. The layer everyone skips.
# --------------------------------------------------------------------------


def test_solution_that_does_not_pass_its_own_tests_is_caught(valid):
    data = copy.deepcopy(valid)
    code = next(e for e in data["exercises"] if e["kind"] == "code")
    # Plausible, schema clean, and wrong: it forgets the attempt budget.
    code["solution"] = (
        "def should_retry(status_code, attempt, max_attempts):\n"
        "    return status_code == 429 or 500 <= status_code < 600"
    )
    module = Module.model_validate(data)

    report = Report()
    run_hidden_tests(module, report)

    assert not report.ok
    assert "fails its own hidden tests" in report.errors[0]


def test_solution_that_never_terminates_is_killed(valid):
    data = copy.deepcopy(valid)
    code = next(e for e in data["exercises"] if e["kind"] == "code")
    code["solution"] = (
        "def should_retry(status_code, attempt, max_attempts):\n"
        "    while True:\n"
        "        pass"
    )
    module = Module.model_validate(data)

    report = Report()
    run_hidden_tests(module, report)

    assert not report.ok
    assert "did not finish" in report.errors[0]


# --------------------------------------------------------------------------
# Layer 3, corpus. The defects that do not exist in any single file.
# --------------------------------------------------------------------------


def test_keys_all_in_one_position_are_rejected(valid):
    """The defect my own courses shipped: 32 items, every key at index 0."""
    modules = []
    for i in range(4):
        data = copy.deepcopy(valid)
        data["slug"] = f"module-{i}"
        data["exercises"] = [e for e in data["exercises"] if e["kind"] == "multiple_choice"]
        for j, ex in enumerate(data["exercises"]):
            ex["id"] = f"item-{i}-{j}"
            ex["key"] = 0
            ex["stem"] = "Which of these statements about retry policy is correct here?"
        modules.append(Module.model_validate(data))

    report = Report()
    check_corpus(modules, report)

    assert not report.ok
    assert "always" in report.errors[0] and "same option" in report.errors[0]


def test_spread_keys_are_accepted(valid):
    modules = []
    for i in range(4):
        data = copy.deepcopy(valid)
        data["slug"] = f"module-{i}"
        data["exercises"] = [e for e in data["exercises"] if e["kind"] == "multiple_choice"]
        for j, ex in enumerate(data["exercises"]):
            ex["id"] = f"item-{i}-{j}"
            ex["key"] = (i + j) % 4
            ex["stem"] = "Which of these statements about retry policy is correct here?"
        modules.append(Module.model_validate(data))

    report = Report()
    check_corpus(modules, report)

    assert report.ok, report.errors


def test_duplicate_exercise_id_across_modules_is_rejected(valid):
    a = Module.model_validate(broken(valid, slug="module-a"))
    b = Module.model_validate(broken(valid, slug="module-b"))

    report = Report()
    check_corpus([a, b], report)

    assert not report.ok
    assert any("exercise id" in e for e in report.errors)


def test_unresolvable_prerequisite_is_rejected(valid):
    data = broken(valid, prerequisites=["a-module-that-does-not-exist"])
    report = Report()
    check_corpus([Module.model_validate(data)], report)

    assert not report.ok
    assert "does not resolve" in report.errors[0]


# --------------------------------------------------------------------------
# Layer 1, and the rendering contract
# --------------------------------------------------------------------------


def test_front_matter_must_be_closed():
    with pytest.raises(ValueError, match="never closed"):
        parse_front_matter("---\ntitle: x\n\nsome body\n")


def test_front_matter_must_open_the_file():
    with pytest.raises(ValueError, match="does not open"):
        parse_front_matter("# A heading\n\n---\ntitle: x\n---\n")


def test_render_is_deterministic(valid):
    module = Module.model_validate(valid)
    assert render(module) == render(module)


def test_render_round_trips_through_a_real_yaml_parser(valid):
    module = Module.model_validate(valid)
    front = parse_front_matter(render(module))
    assert front["slug"] == module.slug
    assert front["objectives"] == module.objectives


def test_rendered_file_never_contains_the_answers(valid):
    module = Module.model_validate(valid)
    out = render(module)
    for ex in module.exercises:
        if ex.kind == "code":
            assert ex.solution not in out
            for t in ex.tests:
                assert t.call not in out
        else:
            assert ex.explanation not in out
