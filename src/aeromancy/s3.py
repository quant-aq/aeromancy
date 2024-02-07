"""Opinionated S3 interface which forces versioning and local caching.

Terminological note: We use the term "pseudodirectory" when describing portions
of S3 paths that look like directories, but aren't because S3 isn't actually a
filesystem. For example, in the key "a/b/c", we would say that "c" is the in
pseudodirectory "a/b".
"""

import hashlib
import os
import shutil
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import boto3
import humanize
import hyperlink
import msgspec
from loguru import logger

# Global S3 Client (used as default instance in from_env_variables())
_S3_CLIENT = None


def file_digest(filename: Path) -> str:
    """Compute the SHA1 hash of a file."""
    # TODO: replace with hashlib.file_digest in Python 3.11
    sha1 = hashlib.sha1(usedforsecurity=False)
    sha1.update(filename.open(mode="rb").read())
    return sha1.hexdigest()


class S3Bucket(msgspec.Struct, frozen=True):
    """Represents an S3 bucket.

    Attributes
    ----------
    bucket
        Name of an S3 bucket.
    """

    bucket: str

    def __str__(self):
        """Return the name of the bucket."""
        return str(self.bucket)

    def __getitem__(self, key: str) -> "S3Object":
        """Create an S3Object for this bucket with the specified key."""
        return S3Object(self.bucket, key)


class S3Object(msgspec.Struct, frozen=True, order=True):
    """Represents the path to an S3 object.

    Attributes
    ----------
    bucket
        Name of an S3 bucket.
    key
        Key for an object inside the S3 bucket `bucket`.
    """

    bucket: str
    key: str

    def __truediv__(self, suffix: str | Path) -> "S3Object":
        """Syntactic sugar to join a suffix to the key as if both are paths.

        This treats the existing key as a (pseudo)directory, so it will include a slash
        between the original key and new suffix if there wasn't one already.

        Example:
        -------
        >>> s = S3Object("bucket", "key")
        >>> s/"subkey"
        S3Object(bucket="bucket", key="key/subkey")
        """
        return self.joinpath(str(suffix))

    def joinpath(self, *pieces: str) -> "S3Object":
        """Add path pieces to the `key`.

        Params
        ------
            pieces
                Additional strings to include in the key.

        Returns
        -------
            A new S3Object with `pieces` appended to the key, joined with the
            default path separator.
        """
        if not pieces:
            raise ValueError(f"Must have at least one piece, got: {pieces!r}")

        # Make sure there's no initial slash in suffix since joining "/a" and
        # "/b" -> "/b" instead of "/a/b".
        sanitized_piece0 = pieces[0].removeprefix("/")
        pieces = (sanitized_piece0,) + pieces[1:]
        path = Path(self.key)
        new_key = path.joinpath(*pieces)
        return S3Object(self.bucket, str(new_key))

    def to_dict(self):
        """Convert to a dictionary of field names to field values."""
        return {f: getattr(self, f) for f in self.__struct_fields__}


class VersionedS3Object(S3Object, frozen=True):
    """Represents the path to an versioned S3 object."""

    version_id: str

    def to_aeromancy_uri(self):
        """Return an internal URLs, purely for Aeromancy tracking with W&B."""
        return hyperlink.URL(
            scheme="aeromancy",
            host=self.bucket,
            path=self.key.split("/"),
            fragment=self.version_id,
        )

    @classmethod
    def from_aeromancy_uri(cls, aeromancy_uri: hyperlink.URL | hyperlink.DecodedURL):
        """Create a corresponding `VersionedS3Object` from a URL."""
        return cls(
            bucket=aeromancy_uri.host,
            key="/".join(aeromancy_uri.path),
            version_id=aeromancy_uri.fragment,
        )


def version_iterator(s3_client, bucket, key):
    """Retrieve all versions of an object."""
    # Apparently the S3 paginator still requires a bit of work to decode.
    paginator = s3_client.get_paginator("list_object_versions")
    response_iterator = paginator.paginate(Bucket=bucket, Prefix=key)
    for response in response_iterator:
        for version in response["Versions"]:
            # Since we provided a prefix, we may get expansions of that prefix too.
            if version["Key"] != key:
                continue
            yield version


def list_objects_iterator(s3_client, bucket, prefix):
    """Retrieve all objects that match a prefix in a bucket."""
    paginator = s3_client.get_paginator("list_objects_v2")
    response_iterator = paginator.paginate(Bucket=bucket, Prefix=prefix)
    for response in response_iterator:
        contents = response.get("Contents")
        if not contents:
            raise FileNotFoundError(f"No files matched for {bucket!r} and {prefix!r}")
        for entry in contents:
            key: str = entry["Key"]
            yield key


class CacheEntry(msgspec.Struct, order=True):
    """Single S3 cache entry.

    The format of this should not be relied on and subject to change.
    """

    s3_object: S3Object
    cached_filename: str
    checksum_sha1: str


class Cache:
    """Interface to local cache of S3 objects."""

    def __init__(self, cache_root: Path):
        """Create the cache interface.

        Parameters
        ----------
        cache_root
            Top level directory for the cache.
        """
        self._cache_root = cache_root.expanduser().resolve()
        self._checksum_path = self._cache_root / "checksums.json"
        self._cacheentry_by_checksum = self._load_checksums()

    def _load_checksums(self) -> dict[str, list[CacheEntry]]:
        if not self._checksum_path.exists():
            return defaultdict(list)

        checksum_bytes = self._checksum_path.read_bytes()
        cache_entries = msgspec.json.decode(checksum_bytes, type=list[CacheEntry])

        # There may be multiple CacheEntry objects for a single checksum.
        # Hash collisions are quite possible with identical files.
        entries_by_checksum = defaultdict(list)
        for entry in cache_entries:
            entries_by_checksum[entry.checksum_sha1].append(entry)

        return entries_by_checksum

    def _save_checksums(self) -> None:
        all_entries = []
        for entries in self._cacheentry_by_checksum.values():
            all_entries.extend(entries)
        # Sort by repr() since entries can be mixed between S3Object and
        # VersionedS3Object which don't compare with each other. This is purely
        # to improve human readability of the resulting JSON -- nothing relies
        # on this ordering.
        all_entries.sort(key=lambda entry: repr(entry))
        jsonified = msgspec.json.encode(all_entries)

        self._cache_root.mkdir(parents=True, exist_ok=True)
        with self._checksum_path.open("wb") as checksums:
            checksums.write(jsonified)

    def get_path(
        self,
        s3_object: S3Object | VersionedS3Object,
        create_parents: bool = True,
    ) -> Path:
        """Return storage location in our local cache for an object."""
        path_pieces = [s3_object.bucket, s3_object.key]
        if isinstance(s3_object, VersionedS3Object):
            path_pieces.append(s3_object.version_id)

        cached_filename: Path = self._cache_root.joinpath(*path_pieces)
        if create_parents:
            cached_filename.parent.mkdir(parents=True, exist_ok=True)
        return cached_filename

    def get_version(self, s3_object: S3Object, sha1: str) -> str | None:
        """Check if a specific SHA1 checksum for an `S3Object` is already in the cache.

        Parameters
        ----------
        s3_object
            The S3 object in question.
        sha1
            Checksum for an object to check.

        Returns
        -------
            Returns the S3 version as a string if the checksum was found for
            that S3 object, otherwise None.
        """
        entries: list[CacheEntry] = self._cacheentry_by_checksum.get(sha1, [])
        for entry in entries:
            if entry.s3_object != s3_object:
                continue

            # We've found the CacheEntry which matches checksum for this
            # s3_object. Last part of a cached filename is the version_id
            # (except when allow_unversioned=True, but these objects should
            # never use this code path and allow_unversioned is not supported
            # for other uses).
            return Path(entry.cached_filename).parts[-1]

        # No matching entries found.
        return None

    def finalize_adding_file(
        self,
        cached_filename: Path,
        s3_object: S3Object,
        last_modified: datetime | None = None,
        sha1: str | None = None,
    ):
        """Must be called whenever an item is added to the cache.

        Optionally helps you set its modification time.
        sha1 can be provided if already calculated.
        """
        if last_modified:
            last_modified_tuple = time.mktime(last_modified.timetuple())
            os.utime(cached_filename, (last_modified_tuple, last_modified_tuple))

        # Make cache files read only.
        cached_filename.chmod(0o400)

        self._make_cacheentry(
            cached_filename=cached_filename,
            s3_object=s3_object,
            sha1=sha1,
        )
        self._save_checksums()

    def _make_cacheentry(
        self,
        cached_filename: Path,
        s3_object: S3Object,
        sha1: str | None = None,
    ):
        if sha1 is None:
            sha1 = file_digest(cached_filename)

        entry = CacheEntry(
            s3_object=s3_object,
            checksum_sha1=sha1,
            cached_filename=str(cached_filename),
        )
        self._cacheentry_by_checksum[sha1].append(entry)

    def repair(self) -> None:
        """Delete and regenerate the checksum cache."""
        self._cacheentry_by_checksum.clear()
        for filename in sorted(self._cache_root.glob("**/*")):
            # Skip files in the root of the cache directory (these are cache
            # metadata).
            if not filename.is_file() or filename.parent == self._cache_root:
                continue
            logger.info(f"Checksumming {str(filename)!r}")
            relative_filename = Path(str(filename).replace(f"{self._cache_root}/", ""))
            [bucket, *key_parts, version_id] = relative_filename.parts
            key = "/".join(key_parts)
            self._make_cacheentry(
                cached_filename=filename,
                s3_object=S3Object(bucket=bucket, key=key),
            )
        self._save_checksums()


class S3Client:
    """An S3 client that is version-aware and caches objects to disk."""

    def __init__(
        self,
        region_name,
        endpoint_url,
        aws_access_key_id,
        aws_secret_access_key,
        cache_root="~/Cache/",
    ):
        """Create a client for working with S3 storage.

        region_name, endpoint_url, aws_access_key_id, aws_secret_access_key are passed
        directly to boto3.client.

        cache_root is where our bucket cache should live on disk. By default, it
        persists in your home directory.
        """
        self._s3_client = boto3.client(
            "s3",
            region_name=region_name,
            endpoint_url=endpoint_url,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
        )
        self.cache = Cache(Path(cache_root))

    @classmethod
    def from_env_variables(cls):
        """Construct an instance from environment variables.

        If one has already been constructed, we will reuse it (assumes that
        environment variables don't change).
        """
        global _S3_CLIENT
        if not _S3_CLIENT:
            _S3_CLIENT = cls(
                aws_access_key_id=os.environ["AEROMANCY_AWS_ACCESS_KEY_ID"],
                aws_secret_access_key=os.environ["AEROMANCY_AWS_SECRET_ACCESS_KEY"],
                region_name=os.environ["AEROMANCY_AWS_REGION"],
                endpoint_url=os.environ["AEROMANCY_AWS_S3_ENDPOINT_URL"],
            )
        return _S3_CLIENT

    def latest_version(self, s3_object: S3Object) -> str:
        """Return the latest version ID for an object.

        Raises a TypeError if s3_object doesn't have a version.
        """
        response = self._s3_client.get_object(
            Bucket=s3_object.bucket,
            Key=s3_object.key,
        )
        try:
            return response["VersionId"]
        except KeyError as err:
            raise TypeError(
                f"s3_object has no version information: {s3_object!r}",
            ) from err

    def fetch(self, s3_object: S3Object, allow_unversioned=False) -> Path:
        """Return the path to a local copy of an object from a bucket.

        If the object is not already in our cache, we'll download it.

        CAUTION: You can fetch unversioned S3Objects with allow_unversioned=True
        but this should be avoided whenever possible and assumes you know what
        you're doing. These will not be redownloaded unless manually deleted.

        Returns the path to the cached filename.
        """
        versioned = isinstance(s3_object, VersionedS3Object)
        if not versioned and not allow_unversioned:
            raise ValueError(
                f"Won't fetch an unversioned S3Object ({s3_object}) unless "
                "allow_unversioned=True (use caution!)",
            )

        # Determine where it should live in the cache. Note the key will
        # actually become a directory here so we can group all its versions
        # together.
        cached_filename: Path = self.cache.get_path(s3_object)
        if cached_filename.exists():
            return cached_filename

        logger.info(f"Fetching and caching {s3_object!r}")

        # Actually download the file.
        download_kwargs = {}
        if versioned:
            download_kwargs["ExtraArgs"] = {"VersionId": s3_object.version_id}
        self._s3_client.download_file(
            s3_object.bucket,
            s3_object.key,
            cached_filename,
            **download_kwargs,
        )

        # Set modification (and access) time to S3's modification time. This
        # helps with debugging and also means they'll sort by version easily
        # with tools like "ls -lt".
        get_object_kwargs = {}
        if versioned:
            get_object_kwargs["VersionId"] = s3_object.version_id
        response = self._s3_client.get_object(
            Bucket=s3_object.bucket,
            Key=s3_object.key,
            **get_object_kwargs,
        )
        last_modified: datetime = response["LastModified"]

        self.cache.finalize_adding_file(
            cached_filename=cached_filename,
            s3_object=s3_object,
            last_modified=last_modified,
        )
        return cached_filename

    def put(
        self,
        local_filename: Path,
        s3_object: S3Object,
    ) -> VersionedS3Object:
        """Upload a local file to S3 and stores it in the cache.

        Returns a versioned copy of s3_object.
        """
        # Check if we already have this file.
        sha1 = file_digest(local_filename)
        size = humanize.naturalsize(local_filename.stat().st_size)
        existing_version_id = self.cache.get_version(s3_object=s3_object, sha1=sha1)
        if existing_version_id is None:
            logger.info(f"Storing {str(local_filename)!r} ({size}) to {s3_object}")
            self._s3_client.upload_file(local_filename, s3_object.bucket, s3_object.key)
            # TODO: there's a potential race condition here if two uploads of the same
            # file happens simultaneously.
            version_id = self.latest_version(s3_object)
        else:
            logger.info(
                f"Cache hit for {str(local_filename)!r} ({size}), skipping upload to "
                f"{s3_object}",
            )
            version_id = existing_version_id

        versioned_s3_object = VersionedS3Object(
            **s3_object.to_dict(),
            version_id=version_id,
        )

        # Transfer it to the cache if it's not already there.
        if not existing_version_id:
            cached_filename = self.cache.get_path(versioned_s3_object)
            shutil.copy(local_filename, cached_filename)

            self.cache.finalize_adding_file(
                s3_object=s3_object,
                cached_filename=cached_filename,
                sha1=sha1,
            )

        return versioned_s3_object

    def list_versions(self, s3_object: VersionedS3Object) -> list[str]:
        """Return a list of all versions of a specific key in a bucket.

        Versions are sorted from oldest to newest (according to S3).
        """
        version_iter = version_iterator(
            self._s3_client,
            s3_object.bucket,
            s3_object.key,
        )
        mtime_and_versions: list[tuple[datetime, str]] = [
            (version["LastModified"], version["VersionId"]) for version in version_iter
        ]
        return [version_id for _, version_id in sorted(mtime_and_versions)]

    def list_objects(
        self,
        bucket: S3Bucket | str,
        pseudodirectory: str,
    ) -> list[S3Object]:
        """Return a list of all keys that match a prefix in a bucket.

        This assumes that prefix is a (pseudo)directory and will only include
        "children" of that directory and not the directory itself.

        Keys are sorted by standard Python string ordering.
        """
        if not pseudodirectory.endswith("/"):
            pseudodirectory += "/"

        all_keys = sorted(
            list_objects_iterator(self._s3_client, str(bucket), pseudodirectory),
        )
        return [
            S3Object(str(bucket), key) for key in all_keys if key != pseudodirectory
        ]

    def ensure_object_versioning(self, bucket: S3Bucket | str) -> None:
        """Make sure that a bucket has object versioning enabled.

        This only needs to be run once per bucket.
        """
        self._s3_client.put_bucket_versioning(
            Bucket=str(bucket),
            VersioningConfiguration={
                "Status": "Enabled",
            },
        )


if __name__ == "__main__":
    import sys

    # TODO: simple function for now -- will likely grow to include other S3 debug
    # operations
    print("Repairing S3 cache checksums")
    cache_paths = sys.argv[1:] or ["~/FakeCache", "~/Cache"]
    print(f"{cache_paths=}")
    for cache_path in cache_paths:
        cache_path = Path(cache_path).expanduser()
        if not cache_path.exists():
            continue

        try:
            cache = Cache(cache_path)
        except msgspec.ValidationError:
            # This happens with older databases, so nuke the checksums and
            # retry (repair is going to rebuild them anyway).
            checksum_path = cache_path / "checksums.json"
            checksum_path.unlink()
            cache = Cache(cache_path)

        cache.repair()
