"""Fake Tracker for fast development.

This should close enough to the Weights and Biases Tracker to run `Action`s,
etc. but doesn't actually track anything. It is the default Tracker for `--dev`
mode and intended for testing features in a faster edit-run-debug loop than
Aeromancy normally supports.

Limitations:
    - Only supports a single version of each artifact, so these get clobbered by
      default.
    - Since it's not connected with Weights and Biases, it only knows about artifacts
      that were produced in `--dev` mode (or manually transferred to its cache).
"""

import datetime
import shutil
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import humanize
import msgspec
from loguru import logger
from rich.console import Console
from typing_extensions import override

from .artifacts import (
    AeromancyArtifact,
    WandbArtifactName,
)
from .runtime_environment import get_runtime_environment
from .s3 import Cache, S3Object, VersionedS3Object, file_digest
from .tracker import Tracker

console = Console()

FAKE_ENTITY = "FAKE_ENTITY"
FAKE_VERSION = "FAKE_VERSION"


class _BailoutError(Exception):
    """Indicates an expected exit which should avoid extended traces.

    This can be used in `--dev` mode to immediately exit Aeromancy, avoiding the
    extensive tracebacks we normally show. If raised outside of `--dev` mode, it
    will be treated as a normal exception.
    """


def bailout():
    """Exit Aeromancy immediately (for quick debugging).

    This is primarily intended for `--dev` mode where it will avoid the
    extensive tracebacks we normally show. If run outside of `--dev` mode, it
    will still exit Aeromancy (but consider a more descriptive error).
    """
    raise _BailoutError


class FakeArtifactMapping(msgspec.Struct):
    """Structure to record and persist AeromancyArtifact names.

    Attributes
    ----------
    artifacts_by_name
        Mappping from artifact name to actual artifact.
    """

    artifacts_by_name: dict[str, AeromancyArtifact]


class FakeTracker(Tracker):
    """Fake Tracker for fast development.

    This includes a local cache for artifacts, but doesn't actually use S3 or
    Weights and Biases for storage. Artifact names follow W&B conventions so
    that real artifacts can be transferred over for more realistic development.
    """

    @override
    def __init__(
        self,
        project_name: str,
        config: dict | None = None,
        job_type: str | None = None,
        job_group: str | None = None,
        tags: set[str] | None = None,
    ):
        Tracker.__init__(
            self,
            project_name=project_name,
            config=config,
            job_type=job_type,
            job_group=job_group,
            tags=tags,
        )

        self.cache_root_path = Path("~/FakeCache").expanduser().resolve()
        self.cache = Cache(cache_root=self.cache_root_path)
        self.mapping_path = self.cache_root_path / "artifact_mapping.json"
        self._read_artifact_mapping()

    def _read_artifact_mapping(self):
        if self.mapping_path.exists():
            with self.mapping_path.open() as mapping_file:
                mapping_json = mapping_file.read()
            mapping = msgspec.json.decode(mapping_json, type=FakeArtifactMapping)
        else:
            mapping = FakeArtifactMapping({})

        self.artifact_mapping = mapping

    def _set_artifact_mapping(self, name, artifact):
        self.artifact_mapping.artifacts_by_name[str(name)] = artifact

        # Save to disk.
        jsonified = msgspec.json.encode(self.artifact_mapping)
        self.cache_root_path.mkdir(parents=True, exist_ok=True)
        with self.mapping_path.open("wb") as checksums:
            checksums.write(jsonified)

    @override
    def __enter__(self):
        params = dict(self.__dict__)
        params.pop("cache")
        params.pop("artifact_mapping")
        console.log("Started FakeTracker:", params)
        self._start_time = datetime.datetime.now(tz=datetime.timezone.utc)

        return self

    @override
    def __exit__(self, exctype, excinst, exctb) -> bool:
        duration = datetime.datetime.now(tz=datetime.timezone.utc) - self._start_time
        console.log(
            f"FakeTracker exited after {humanize.precisedelta(duration)}",
        )

        if exctype is not None:
            if exctype is _BailoutError:
                # Exit immediately without all the logging.
                console.log("Bailout requested, exiting.")
                raise SystemExit

            if get_runtime_environment().debug_mode:
                logger.exception("Exception!")
                console.print_exception(show_locals=True, suppress=[])
            else:
                logger.exception(
                    "Exception! (see more details with --debug)",
                )

        return False

    @override
    def declare_output(
        self,
        name: str,
        local_filenames: Sequence[Path],
        s3_destination: S3Object,
        artifact_type: str,
        strip_prefix: Path | None = None,
        metadata: dict | None = None,
    ) -> AeromancyArtifact:
        console.log(f"FakeTracker output filenames: {local_filenames!r}")
        if metadata:
            console.log(f"FakeTracker output metadata: {metadata!r}")

        # Convert each file to a fake VersionedS3Object.
        s3_objects = []
        for local_filename in local_filenames:
            new_path = local_filename
            if strip_prefix:
                # Need a trailing slash since otherwise we end up with an absolute path.
                new_path = str(new_path).removeprefix(str(strip_prefix) + "/")
            versioned_s3_object = VersionedS3Object(
                s3_destination.bucket,
                (s3_destination / new_path).key,
                FAKE_VERSION,  # TODO: support multiple versions
            )
            s3_objects.append(versioned_s3_object)

            # Actually store the files in the fake cache (if not already
            # present). In this weird case, we already know the version, but we
            # can use get_version() to find out if there's an existing cache
            # entry.
            sha1 = file_digest(local_filename)
            existing_version_id = self.cache.get_version(
                s3_object=versioned_s3_object,
                sha1=sha1,
            )
            if existing_version_id is None:
                console.log(
                    f"[OFFLINE] Pretending to store {str(local_filename)!r} to "
                    f"{versioned_s3_object}",
                )
                cached_path = self.cache.get_path(versioned_s3_object)
                if cached_path.exists():
                    # Temporarily make it writable again since
                    # finalize_adding_file should have locked it down when it
                    # was last added.
                    cached_path.chmod(0o700)
                shutil.copy(local_filename, cached_path)

                self.cache.finalize_adding_file(
                    cached_filename=cached_path,
                    s3_object=versioned_s3_object,
                    sha1=sha1,
                )
            else:
                console.log(f"Cache hit for {str(local_filename)!r})")

        # We now have enough to make an AeromancyArtifact.
        aero_artifact = AeromancyArtifact(
            name=name,
            artifact_type=artifact_type,
            s3=s3_objects,
        )
        artifact_name = WandbArtifactName(
            entity=FAKE_ENTITY,
            project=self.project_name,
            artifact_name=name,
            version=FAKE_VERSION,
        )
        self._set_artifact_mapping(artifact_name, aero_artifact)

        return aero_artifact

    @override
    def declare_input(
        self,
        artifact: AeromancyArtifact | str,
        use_as: str | None = None,
    ) -> Sequence[Path]:
        if isinstance(artifact, str):
            artifact_name = WandbArtifactName.parse(artifact)
            # Basic version resolution
            if artifact_name.version == "latest":
                artifact_name.version = FAKE_VERSION
            if artifact_name.project is None:
                artifact_name.project = self.project_name
            # We don't support sharing artifacts across entities, so we'll
            # always mask out the entity name.
            artifact_name.entity = FAKE_ENTITY
            artifact = self.artifact_mapping.artifacts_by_name[str(artifact_name)]

        local_paths = [
            self.cache.get_path(s3, create_parents=False) for s3 in artifact.s3
        ]
        console.log(f"FakeTracker input: {artifact!r} → {len(local_paths)} paths")
        return local_paths

    @override
    def log(self, metrics: dict[str, Any]) -> None:
        console.log("FakeTracker logged metrics:", metrics)
