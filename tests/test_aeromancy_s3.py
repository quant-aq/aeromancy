"""Tests for S3 structures."""

from aeromancy.s3 import S3Bucket, S3Object


def test_s3bucket_str() -> None:
    """Basic test for `S3Bucket.__str__` method."""
    s3_bucket = S3Bucket("bucket-name")
    assert str(s3_bucket) == "bucket-name"


def test_s3bucket_getitem() -> None:
    """Basic test for `S3Bucket.__getitem__` method."""
    s3_bucket = S3Bucket("bucket-name")
    child = s3_bucket["key"]
    assert child == S3Object("bucket-name", "key")


def test_s3object_truediv() -> None:
    """Basic test for `S3Object.__truediv__` method."""
    s3_object = S3Object("bucket-name", "key")
    child = s3_object / "subkey"
    assert child == S3Object("bucket-name", "key/subkey")


def test_s3object_truediv_with_initial_slash() -> None:
    """Test for `S3Object.__truediv__` method with initial slashes in them."""
    s3_object = S3Object("bucket-name", "key")
    # "/subkey" looks like an absolute path but we don't want to treat it that way
    child = s3_object / "/subkey"
    assert child == S3Object("bucket-name", "key/subkey")


def test_s3object_truediv_with_multiple_slashes() -> None:
    """Test `S3Object.__truediv__` method with non-initial slashes in the RHS."""
    s3_object = S3Object("bucket-name", "key")
    child = s3_object / "subkey/subsubkey"
    assert child == S3Object("bucket-name", "key/subkey/subsubkey")


def test_s3object_truediv_with_trailing_slash() -> None:
    """Test `S3Object.__truediv__` method strips trailing slashes in the RHS."""
    s3_object = S3Object("bucket-name", "key")
    child = s3_object / "subkey/"
    assert child == S3Object("bucket-name", "key/subkey")


def test_s3object_joinpath() -> None:
    """Basic test for `S3Object.joinpath` method."""
    s3_object = S3Object("bucket-name", "key")
    child = s3_object.joinpath("subkey")
    assert child == S3Object("bucket-name", "key/subkey")


def test_s3object_joinpath_with_initial_slash() -> None:
    """Test for `S3Object.joinpath` method with initial slashes in them."""
    s3_object = S3Object("bucket-name", "key")
    # "/subkey" looks like an absolute path but we don't want to treat it that way
    child = s3_object.joinpath("/subkey")
    assert child == S3Object("bucket-name", "key/subkey")


def test_s3object_joinpath_with_internal_slashes() -> None:
    """Test `S3Object.joinpath` method with non-initial slashes in the RHS."""
    s3_object = S3Object("bucket-name", "key")
    child = s3_object.joinpath("subkey", "subsubkey")
    assert child == S3Object("bucket-name", "key/subkey/subsubkey")


def test_s3object_joinpath_with_trailing_slash() -> None:
    """Test `S3Object.joinpath` method strips trailing slashes in the RHS."""
    s3_object = S3Object("bucket-name", "key")
    child = s3_object.joinpath("subkey", "subsubkey/")
    assert child == S3Object("bucket-name", "key/subkey/subsubkey")


def test_s3object_to_dict() -> None:
    """Basic test for `S3Object.to_dict` method."""
    s3_object = S3Object("bucket-name", "key")
    expected = {"bucket": "bucket-name", "key": "key"}
    assert s3_object.to_dict() == expected
