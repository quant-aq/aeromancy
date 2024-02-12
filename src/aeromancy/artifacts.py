"""Library for interfacing with artifacts (files stored and tracked externally).

This is effectively a bridge between Weights and Biases artifacts and S3-backed
version objects.
"""

import re
from collections.abc import Sequence
from pathlib import Path

import hyperlink
import msgspec
import wandb
import wandb.errors
import wandb.sdk.wandb_run
from loguru import logger
from wandb.sdk.artifacts.artifact import Artifact as WandbApiArtifact
from wandb.sdk.wandb_run import Run as WandbRun

from .runtime_environment import get_runtime_environment
from .s3 import (
    S3Client,
    S3Object,
    VersionedS3Object,
)

# This is subject to change, of course, but there doesn't seem to be an exported
# constant from wandb that we can use.
VALID_WANDB_ARTIFACT_NAME_RE = re.compile(r"^[a-zA-Z0-9_\-.]+$")


def _validate_wandb_artifact_string(name: str | None, role: str):
    """Ensure a string conforms to Weights and Biases naming constraints.

    These strings must be non-empty and made up of a combination of alphanumeric
    characters, digits, underscores, dashes, and/or dots.

    These definitely apply to artifact names and likely apply to other Weights
    and Biases strings as well (e.g., project name).

    Note that None **is** a valid string here based on how this helper function
    is used (we're often constructing artifacts from parts, some of which are
    optional).

    Parameters
    ----------
    name
        String to validate or None (since there are many cases where Weights and
        Biases strings are optional).
    role
        Description of the string and how it's used.

    Raises
    ------
    ValueError
        If `name` doesn't conform.
    """
    if name is None:
        return

    if not VALID_WANDB_ARTIFACT_NAME_RE.match(name):
        raise ValueError(
            f"Invalid {role} name: {name!r} (can only include alphanumeric "
            "characters, digits, underscores, dashes, and/or dots)",
        )


class WandbArtifactName(msgspec.Struct):
    """Represents a parse of a Weights and Biases artifact name.

    Can include None for any missing entries.

    Attributes
    ----------
    entity
        Entity name (person or organization on Weights and Biases).
    project
        Name of Weights and Biases project.
    artifact_name
        Should comply with Weights and Biases artifact naming scheme
        (see `validate_wandb_artifact_string`).
    version
        Weights and Biases version string (e.g., "latest", "v0").
    """

    entity: str | None
    project: str | None
    artifact_name: str
    version: str | None

    def __post_init__(self):
        """Validate our inputs."""
        # We don't know for sure that Weights and Biases holds entity, project,
        # and version strings subject to the same constraints as artifact name,
        # but we'll enforce it here out of paranoia.
        _validate_wandb_artifact_string(self.entity, "entity")
        _validate_wandb_artifact_string(self.project, "project")
        _validate_wandb_artifact_string(self.artifact_name, "artifact")
        _validate_wandb_artifact_string(self.version, "version")

    def __str__(self) -> str:
        """Format as a Weights and Biases artifact string."""
        pieces = []
        if self.entity:
            pieces.append(self.entity)
        if self.project:
            pieces.append(self.project)
        pieces.append(self.artifact_name)
        base = "/".join(pieces)
        if self.version:
            return f"{base}:{self.version}"
        else:
            return base

    @classmethod
    def parse(
        cls,
        wandb_artifact_name: str,
    ) -> "WandbArtifactName":
        """Parse a string representing a Weights and Biases artifact.

        Supports parsing the following formats:

        - `name`
        - `project/name`
        - `org/project/name`
        - `org/project/name:v0`
        - `org/project/name:latest`

        Any missing fields will be given the value None.

        Parameters
        ----------
        wandb_artifact_name
            String to parse.

        Returns
        -------
            Instance of `WandbArtifactName` with values from `wandb_artifact_name`
        """
        project = None
        entity = None
        version = None

        pieces = wandb_artifact_name.split("/")
        # If there's a version, pull it off the last piece.
        if ":" in pieces[-1]:
            last_part, version = pieces[-1].rsplit(":", 1)
            pieces[-1] = last_part

        match len(pieces):
            case 1:
                artifact_name = pieces[0]
            case 2:
                project, artifact_name = pieces
            case 3:
                entity, project, artifact_name = pieces
            case _:
                raise ValueError(
                    f"Not sure how to parse: {wandb_artifact_name!r}",
                )

        return cls(entity, project, artifact_name, version)

    def matches(self, other_artifact_name: "WandbArtifactName") -> bool:
        """Test whether this and another artifact name are compatible.

        Artifact names match when all set fields match, ignoring versions.
        This is different than equality, since it allows for fields to be
        unset on one or both of the artifact names.

        Parameters
        ----------
        other_artifact_name
            The artifact name to match against.

        Returns
        -------
            True if they match.
        """
        if (
            self.entity
            and other_artifact_name.entity
            and self.entity != other_artifact_name.entity
        ):
            return False

        if (
            self.project
            and other_artifact_name.project
            and self.project != other_artifact_name.project
        ):
            return False

        if self.artifact_name != other_artifact_name.artifact_name:
            return False

        return True

    def incorporate_overrides(self):
        """Incorporate artifact version overrides.

        If these are set for this artifact via environment variables and we
        don't already have a specific version set for this artifact, we'll use
        the overridden version.
        """
        for artifact_name in get_runtime_environment().artifact_overrides:
            parsed_artifact_name = self.__class__.parse(artifact_name)
            if self.matches(parsed_artifact_name):
                self.version = parsed_artifact_name.version
                break

    @classmethod
    def resolve_artifact_name(
        cls,
        artifact_name: str,
        default_project_name: str | None = None,
    ) -> str:
        """Resolve an artifact name, incorporating overrides.

        This will always pick the latest version of an artifact unless it has
        been specifically overridden by `--artifact-override`.

        Note that this method works without net access and thus won't actually
        resolve the "latest" tag to a specific version.

        Parameters
        ----------
        artifact_name
            Artifact name to resolve. Version will default to "latest", entity
            to Weights and Biases default, and project name to the `Tracker`'s
            project name.
        default_project_name
            Project name will be filled in from the `artifact_name` if it
            includes one (e.g., "project/artifact:v3"). If not, we will use this
            value. Note that if this value is None, we can still incorporate
            overrides (but project name won't be used to determine whether
            entities match, so it could be less precise).

        Returns
        -------
            Resolved artifact name as a string.
        """
        wandb_artifact_name = cls.parse(artifact_name)
        # Fill in some defaults.
        wandb_artifact_name.project = (
            wandb_artifact_name.project or default_project_name
        )
        wandb_artifact_name.version = wandb_artifact_name.version or "latest"
        wandb_artifact_name.incorporate_overrides()

        return str(wandb_artifact_name)


class AeromancyArtifact(msgspec.Struct):
    """External artifact produced and/or consumed by Aeromancy `Action`s.

    This class includes information to simultaneously track external files using
    Weights and Biases and a S3-compatible storage provider.

    Attributes
    ----------
    name
        The artifact name (should comply with Weights and Biases naming scheme,
        see `validate_wandb_artifact_string`).
    artifact_type
        Free text string to be associated with the artifact (should comply with
        Weights and Biases naming scheme, see `validate_wandb_artifact_string`).
        Semantics are up to project-specific conventions, but recommendation is
        a simple human-readable description of the extension.
    s3
        S3 references for the contents of this artifact.
    """

    name: str
    artifact_type: str
    s3: list[VersionedS3Object]

    def __post_init__(self):
        """Validate our inputs."""
        # We don't know for sure that Weights and Biases holds artifact type
        # strings subject to the same constraints as artifact name, but we'll
        # enforce it here out of paranoia.
        _validate_wandb_artifact_string(self.name, "artifact")
        _validate_wandb_artifact_string(self.artifact_type, "artifact type")

    @classmethod
    def from_wandb_api_artifact(cls, wandb_api_artifact: WandbApiArtifact):
        """Create an `AeromancyArtifact` from a Weights and Biases API artifact.

        Parameters
        ----------
        wandb_api_artifact
            Artifact to convert. Note that this is a Weights and Biases *API*
            Artifact, which is distinct from the typical Weights and Biases
            Artifact.

        Returns
        -------
            An `AeromancyArtifact` corresponding to `wandb_api_artifact`
        """
        s3_objects = []
        for _, manifest_value in sorted(wandb_api_artifact.manifest.entries.items()):
            if manifest_value.ref is None:
                raise ValueError("No URI associated with manifest entry")
            aeromancy_uri = hyperlink.parse(manifest_value.ref)
            s3 = VersionedS3Object.from_aeromancy_uri(aeromancy_uri)
            s3_objects.append(s3)

        artifact_type = wandb_api_artifact.type
        artifact_name = WandbArtifactName.parse(wandb_api_artifact.name)

        return AeromancyArtifact(
            s3=s3_objects,
            artifact_type=artifact_type,
            name=artifact_name.artifact_name,
        )

    def as_wandb_artifact(
        self,
        metadata: dict | None = None,
    ) -> wandb.Artifact:
        """Convert this into a Weights and Biases `Artifact`.

        Parameters
        ----------
        metadata, optional
            Optional fields to associate with the `Artifact`. These will be
            stored and accessible on Weights and Biases.

        Returns
        -------
            This object represented as a Weights and Biases `Artifact`.
        """
        primary_s3 = self.s3[0]
        # Metadata here is intended as a debugging aid.
        # We make a copy since we're going to modify it and the caller doesn't expect it
        # to change.
        metadata = dict(metadata or {})
        metadata.update(
            primary_s3_key=primary_s3.key,
            primary_s3_bucket=primary_s3.bucket,
            primary_s3_version=primary_s3.version_id,
            # For viewing this Artifact on an S3 viewer webpage.
            viewer_url=self.to_s3_viewer_url(),
            num_files=len(self.s3),
        )

        description = f"{primary_s3.bucket}/{primary_s3.key}"
        if len(self.s3) > 1:
            description = f"{description} (+{len(self.s3) - 1} others)"
        artifact = wandb.Artifact(
            name=self.name,
            description=description,
            type=self.artifact_type,
            metadata=metadata,
        )
        # We need an external reference so W&B knows when it changes.
        for s3 in self.s3:
            artifact.add_reference(name=s3.key, uri=str(s3.to_aeromancy_uri()))
        return artifact

    # TODO: Generalize this for non-DigitalOcean users.
    def to_s3_viewer_url(self) -> hyperlink.URL:
        """Return a URL to view the Artifact files on a web-based S3 viewer.

        Returns
        -------
            URL for viewing the Artifact.
        """
        primary_s3 = self.s3[0]

        query = {}
        key = Path(primary_s3.key)
        if len(key.parts) > 1:
            # View the parent directory in DigitalOcean.
            query = {"path": f"{key.parent}/"}

        return hyperlink.URL(
            scheme="https",
            host="cloud.digitalocean.com",
            path=(
                "spaces",
                primary_s3.bucket,
            ),
            query=query,
        )


# Either an actual artifact or a Weights and Biases name for an artifact.
ArtifactDescriptor = AeromancyArtifact | str


class Artifacts:
    """Bridge between Aeromancy and external artifact storage.

    This connects S3 objects to Weights and Bias artifacts and helps manages
    artifact dependencies.
    """

    def __init__(
        self,
        wandb_run: WandbRun,
        s3_client: S3Client | None = None,
    ):
        """Construct an `Artifacts` object for a specific Weights and Biases `Run`.

        Parameters
        ----------
        wandb_run
            Weights and Biases `Run` which will be associated with declared artifacts.
        s3_client, optional
            If missing, a default one will be set up from environment variables.
        """
        if s3_client:
            self._s3 = s3_client
        else:
            self._s3 = S3Client.from_env_variables()

        self.wandb_run = wandb_run
        self.wandb_api = wandb.Api()

    def declare_output(
        self,
        name: str,
        local_filenames: Sequence[Path],
        s3_destination: S3Object,
        artifact_type: str,
        strip_prefix: Path | None = None,
        metadata: dict | None = None,
    ) -> AeromancyArtifact:
        """Store a new artifact and log it as a produced artifact.

        External artifacts are created from local files. Declaring them will
        upload the files to S3 and register the artifact with Weights and
        Biases.

        Parameters
        ----------
        name
            Artifact name. Must meet Weights and Biases naming conventions,
            beyond that semantics are up to the caller/project design.
        local_filenames
            Paths to local files.
        s3_destination
            Where local files should be uploaded on S3.
        artifact_type
            Short description of the artifact type. Semantics are up to the
            caller/project design.
        strip_prefix, optional
            Prefix of local_filenames to remove before uploading them to S3. For
            example, if `strip_prefix=Path('/a/b')`, a local filename with
            `Path('/a/b/c/d.txt')` will be uploaded to
            `<s3_destination>/c/d.txt`
        metadata, optional
            Any additional information to associate with the artifact. Semantics
            are up to the caller/project design, though types must be storable
            by Weights and Biases.

        Returns
        -------
            `AeromancyArtifact` representing the output.
        """
        if not local_filenames:
            raise ValueError("Need at least 1 item in local_filenames to be an output.")

        s3_objects = []
        for local_filename in local_filenames:
            new_path = local_filename
            if strip_prefix:
                # Need a trailing slash since otherwise we end up with an absolute path.
                new_path = str(new_path).removeprefix(str(strip_prefix) + "/")
            s3_objects.append(self._s3.put(local_filename, s3_destination / new_path))
        # Upgrade it to an AeromancyArtifact.
        aero_artifact = AeromancyArtifact(
            name=name,
            artifact_type=artifact_type,
            s3=s3_objects,
        )

        wandb_artifact = aero_artifact.as_wandb_artifact(metadata=metadata)
        self.wandb_run.log_artifact(wandb_artifact)

        return aero_artifact

    def _try_use_artifact(self, wandb_artifact, use_as):
        try:
            self.wandb_run.use_artifact(wandb_artifact, use_as=use_as)
        except wandb.errors.CommError as comm_error:
            raise ValueError(
                f"Error using artifact: {wandb_artifact!r}",
            ) from comm_error

    def declare_input(
        self,
        artifact: ArtifactDescriptor,
        use_as: str | None = None,
    ) -> Sequence[Path]:
        """Record a dependency on an existing artifact and provide local access.

        This indicates that our current Weights and Biases `Run` depends on the files in
        the `artifact` and will resolve and fetch the files in the `artifact`.

        Parameters
        ----------
        artifact
            An artifact that our associated Weights and Biases `Run` depends on.
        use_as, optional
            Description of how we're using the artifact (e.g., "train", "test").
            Most useful when there are multiple input artifacts of the same
            type.

        Returns
        -------
            Returns a local filesystem version of the artifact.
        """
        if isinstance(artifact, str):
            self._try_use_artifact(artifact, use_as=use_as)

            api_artifact = self.wandb_api.artifact(artifact)
            if api_artifact.qualified_name != api_artifact.source_qualified_name:
                logger.info(f"Resolved {api_artifact.name!r} -> {api_artifact.version}")
            artifact = AeromancyArtifact.from_wandb_api_artifact(api_artifact)
        else:
            wandb_artifact = artifact.as_wandb_artifact()
            self._try_use_artifact(wandb_artifact, use_as=use_as)

        local_paths = [self._s3.fetch(s3) for s3 in artifact.s3]
        return local_paths
