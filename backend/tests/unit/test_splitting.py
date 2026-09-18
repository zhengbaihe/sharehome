from itertools import permutations

import pytest

from app.domain.splitting import SplitValidationError, split_equal


@pytest.mark.parametrize(
    ("amount_minor", "participant_ids", "expected"),
    [
        (10000, ["a", "b"], {"a": 5000, "b": 5000}),
        (10000, ["a", "b", "c"], {"a": 3334, "b": 3333, "c": 3333}),
        (1, ["a", "b", "c"], {"a": 1, "b": 0, "c": 0}),
        (5, ["c", "a", "b"], {"a": 2, "b": 2, "c": 1}),
        (10000, ["a"], {"a": 10000}),
    ],
)
def test_equal_split_examples(amount_minor, participant_ids, expected):
    assert split_equal(amount_minor, participant_ids) == expected


@pytest.mark.parametrize("participant_ids", list(permutations(["a", "b", "c"])))
def test_remainder_is_independent_of_input_order(participant_ids):
    result = split_equal(10000, participant_ids)
    assert result == {"a": 3334, "b": 3333, "c": 3333}
    assert list(result) == ["a", "b", "c"]


@pytest.mark.parametrize("amount_minor", [1, 2, 7, 100, 10000, 10**30 + 1])
@pytest.mark.parametrize("participant_count", [1, 2, 3, 7, 20])
def test_allocations_preserve_total_and_are_balanced(amount_minor, participant_count):
    participant_ids = [f"member-{index}" for index in range(participant_count)]
    result = split_equal(amount_minor, participant_ids)
    assert set(result) == set(participant_ids)
    assert sum(result.values()) == amount_minor
    assert all(type(share) is int and share >= 0 for share in result.values())
    assert max(result.values()) - min(result.values()) <= 1


@pytest.mark.parametrize(
    ("amount_minor", "participant_ids", "message"),
    [
        (100, [], "cannot be empty"),
        (100, ["a", "a"], "must be unique"),
        (0, ["a"], "greater than 0"),
        (-1, ["a"], "greater than 0"),
        (1.5, ["a"], "must be an integer"),
        ("100", ["a"], "must be an integer"),
        (True, ["a"], "must be an integer"),
        (None, ["a"], "must be an integer"),
        (100, "ab", "must be a sequence"),
        (100, None, "must be a sequence"),
        (100, [""], "nonempty strings"),
        (100, ["a", 1], "nonempty strings"),
        (100, [["a"]], "nonempty strings"),
    ],
)
def test_invalid_inputs_raise_domain_exception(amount_minor, participant_ids, message):
    with pytest.raises(SplitValidationError, match=message):
        split_equal(amount_minor, participant_ids)


def test_input_is_not_mutated_and_results_are_independent():
    participant_ids = ["c", "a", "b"]
    first_result = split_equal(10000, participant_ids)
    assert participant_ids == ["c", "a", "b"]
    first_result["a"] = 0
    assert split_equal(10000, participant_ids) == {"a": 3334, "b": 3333, "c": 3333}
