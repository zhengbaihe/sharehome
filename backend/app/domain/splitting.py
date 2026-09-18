from collections.abc import Sequence


class SplitValidationError(ValueError):
    """The amount or participants cannot form a valid expense split."""


def split_equal(amount_minor: int, participant_ids: Sequence[str]) -> dict[str, int]:
    """Split positive integer minor units among unique, nonempty string IDs.

    IDs are sorted lexicographically (case-sensitive). The first IDs receive
    any remaining minor units. Inputs are not modified; zero shares are allowed.
    """
    if isinstance(amount_minor, bool) or not isinstance(amount_minor, int):
        raise SplitValidationError("amount_minor must be an integer number of minor units")
    if amount_minor <= 0:
        raise SplitValidationError("amount_minor must be greater than 0")
    if isinstance(participant_ids, (str, bytes)) or not isinstance(participant_ids, Sequence):
        raise SplitValidationError("participant_ids must be a sequence of string IDs")
    if not participant_ids:
        raise SplitValidationError("participant_ids cannot be empty")
    if any(
        not isinstance(participant_id, str) or not participant_id
        for participant_id in participant_ids
    ):
        raise SplitValidationError("participant IDs must be nonempty strings")
    if len(set(participant_ids)) != len(participant_ids):
        raise SplitValidationError("participant IDs must be unique")

    ordered_ids = sorted(participant_ids)
    base_share, remainder = divmod(amount_minor, len(ordered_ids))
    return {
        participant_id: base_share + (1 if index < remainder else 0)
        for index, participant_id in enumerate(ordered_ids)
    }
