"""Extended version of `msgspec.Struct` with easier serialization and validation."""

import json
import tempfile
from pathlib import Path
from typing import TypeAlias

import msgspec

from .artifacts import AeromancyArtifact, ArtifactDescriptor
from .s3 import S3Object
from .tracker import Tracker

JSONType: TypeAlias = (
    dict[str, "JSONType"] | list["JSONType"] | str | int | float | bool | None
)


class AeromancyStruct(msgspec.Struct):
    """`msgspec.Struct` baseclass with additional features.

    These includes validation, easier (de)serialization to JSON/YAML, and
    Aeromancy Artifact integration.
    """

    def encode(self, format: str) -> bytes:
        """Serialize this `msgspec.Struct` to bytes.

        Parameters
        ----------
        format
            Which encoding format to use. This can be "yaml", "json", or "msgpack".

        Returns
        -------
        This msgspec.Struct encoded according to `format`.
        """
        match format:
            case "yaml":
                encoded = msgspec.yaml.encode(self)
            case "json":
                encoded = msgspec.json.encode(self)
            case "msgpack":
                encoded = msgspec.msgpack.encode(self)
            case _:
                raise ValueError(f"Unknown format: {format!r}")

        return encoded

    @classmethod
    def decode(cls, encoded_bytes: bytes, format: str):
        """Deserialize this `msgspec.Struct` from bytes.

        Parameters
        ----------
        encoded_bytes
            Bytes to attempt to deserialize.
        format
            The format to used to encode the `msgspec.Struct`. This can be
            "yaml", "json", or "msgpack".

        Returns
        -------
        An instance of this class decoded according to `format`.
        """
        match format:
            case "yaml":
                return msgspec.yaml.decode(encoded_bytes, type=cls)
            case "json":
                return msgspec.json.decode(encoded_bytes, type=cls)
            case "msgpack":
                return msgspec.msgpack.decode(encoded_bytes, type=cls)
            case _:
                raise ValueError(f"Unknown format: {format!r}")

    def validate(self) -> None:
        """Confirm current values of this `msgspec.Struct` match the spec.

        Raises
        ------
        msgspec.ValidationError
            If current values do not conform.
        """
        # TODO: May eventually be part of msgspec:
        #   https://github.com/jcrist/msgspec/issues/513
        # In the meantime, a workaround: msgspec validates only on
        # serialization, so we can roundtrip our data.
        self.decode(self.encode(format="msgpack"), format="msgpack")

    def as_json_objects(self) -> JSONType:
        """Encode this structure as JSON using corresponding Python objects."""
        return json.loads(self.encode(format="json"))

    def to_artifact(
        self,
        filename: str,
        artifact_name: str,
        artifact_type: str,
        s3_destination: S3Object,
        format: str,
        tracker: Tracker,
    ) -> AeromancyArtifact:
        """Save a `msgspec.Struct` object and declare it an output artifact.

        We use YAML as the serialization format.

        Parameters
        ----------
        filename
            Where to save the object locally.
        artifact_name
            Name of the artifact in Weights and Biases.
        artifact_type
            Type of the artifact in Weights and Biases.
        s3_destination
            Where to save the artifacts on S3.
        format
            Which encoding format to use. This can be "yaml", "json", or "msgpack".
        tracker
            The current Aeromancy Tracker.

        Returns
        -------
            `AeromancyArtifact` representing the new artifact.
        """
        # The file needs to have a specific name (filename will be used directly in S3
        # storage), so we can't use NamedTemporaryFile.
        with tempfile.TemporaryDirectory() as tempdir:
            full_filename = Path(tempdir) / filename
            full_filename.write_bytes(self.encode(format))

            msgspec_artifact = tracker.declare_output(
                name=artifact_name,
                local_filenames=[full_filename],
                s3_destination=s3_destination,
                artifact_type=artifact_type,
                strip_prefix=Path(tempdir),
            )

        return msgspec_artifact

    @classmethod
    def from_artifact(
        cls,
        msgspec_artifact: ArtifactDescriptor,
        format: str,
        tracker: Tracker,
    ):
        """Load a `msgspec.Struct` object and declare it an input artifact.

        Parameters
        ----------
        msgspec_artifact
            Artifact to load (W&B artifact name or existing `AeromancyArtifact`)
        format
            How the artifact was encoded. This can be "yaml", "json", or "msgpack".
        tracker
            The current Aeromancy Tracker.

        Returns
        -------
            An instance of this class with deserialized data from `msgspec_artifact`.

        Raises
        ------
        ValueError
            We currently require msgspec artifacts to only include a single local
            filename in them. This will be raised if this assumption is violated.
        """
        msgspec_paths = tracker.declare_input(msgspec_artifact)
        if len(msgspec_paths) != 1:
            raise ValueError(
                f"Expected 1 path for {msgspec_artifact}, got {len(msgspec_paths)}: "
                f"{msgspec_paths}",
            )
        [msgspec_path] = msgspec_paths
        msgfile_bytes = msgspec_path.read_bytes()
        return cls.decode(msgfile_bytes, format=format)
