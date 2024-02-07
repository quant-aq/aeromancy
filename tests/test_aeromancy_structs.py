"""Tests for working with `AeromancyStruct`s."""

import msgspec
import pytest

from aeromancy.struct import AeromancyStruct


class BogusStruct(AeromancyStruct):
    """Simple structure for testing `AeromancyStruct`s."""

    a: float
    b: str
    c: list[int]


@pytest.mark.parametrize(
    ("format", "expected"),
    [
        ("json", b'{"a":3.14,"b":"test","c":[4,5,6]}'),
        ("yaml", b"a: 3.14\nb: test\nc:\n- 4\n- 5\n- 6\n"),
    ],
)
def test_encode(format: str, expected: bytes) -> None:
    """Basic test for `encode` method."""
    bogus_struct = BogusStruct(a=3.14, b="test", c=[4, 5, 6])
    encoded = bogus_struct.encode(format=format)
    assert encoded == expected


@pytest.mark.parametrize(
    ("format", "input_bytes"),
    [
        ("json", b'{"a":3.14,"b":"test","c":[4,5,6]}'),
        ("yaml", b"a: 3.14\nb: test\nc:\n- 4\n- 5\n- 6\n"),
    ],
)
def test_decode(format: str, input_bytes: bytes) -> None:
    """Basic test for `decode` method."""
    bogus_struct = BogusStruct.decode(input_bytes, format=format)
    assert bogus_struct == BogusStruct(a=3.14, b="test", c=[4, 5, 6])


def test_as_json_obj_basic() -> None:
    """Basic test for `as_json_objects` method."""
    bogus_struct = BogusStruct(a=3.14, b="test", c=[4, 5, 6])
    json_obj = bogus_struct.as_json_objects()
    assert json_obj == {"a": 3.14, "b": "test", "c": [4, 5, 6]}


def test_validate_with_valid_input() -> None:
    """Make sure `validate` method accepts valid input."""
    bogus_struct = BogusStruct(a=3.14, b="test", c=[4, 5, 6])
    bogus_struct.validate()


def test_validate_fails_with_invalid_input() -> None:
    """Make sure `validate` method rejects invalid input."""
    bogus_struct = BogusStruct(a="not a float", b="test", c=[4, 5, 6])  # type: ignore
    with pytest.raises(msgspec.ValidationError):
        bogus_struct.validate()


def test_validate_fails_with_invalid_input_after_change() -> None:
    """Make sure `validate` method rejects invalid input."""
    bogus_struct = BogusStruct(a=3.14, b="test", c=[4, 5, 6])
    # It was valid, but let's make it invalid now:
    bogus_struct.a = "not a float"  # type: ignore
    with pytest.raises(msgspec.ValidationError):
        bogus_struct.validate()
