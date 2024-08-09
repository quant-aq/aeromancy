"""Tests for working with Aeromancy Artifacts."""

import pytest

from aeromancy.artifacts import (
    AeromancyArtifact,
    WandbArtifactName,
    _validate_wandb_artifact_string,
)
from aeromancy.runtime_environment import (
    _ensure_valid_environment,
    get_runtime_environment,
)
from aeromancy.s3 import VersionedS3Object

_ensure_valid_environment()


def test_valid_wandbartifactname() -> None:
    """Ensure WandbArtifactName works with valid artifact names."""
    wandb_artifact_name = WandbArtifactName(
        "entity",
        "project",
        "artifact_name",
        "latest",
    )
    assert wandb_artifact_name.entity == "entity"
    assert wandb_artifact_name.project == "project"
    assert wandb_artifact_name.artifact_name == "artifact_name"
    assert wandb_artifact_name.version == "latest"


@pytest.mark.parametrize(
    "artifact_name",
    ["with/slashes", "with spaces", "illegalpunctuation!", "", "****"],
)
def test_invalid_wandbartifactname(artifact_name) -> None:
    """Ensure WandbArtifactName fails with invalid artifact names."""
    with pytest.raises(ValueError):  # noqa: PT011
        WandbArtifactName(
            "entity",
            "project",
            artifact_name,
            "latest",
        )


def test_valid_aeromancyartifact() -> None:
    """Ensure AeromancyArtifact works with valid artifact names."""
    artifact = AeromancyArtifact(
        "artifact_name",
        "artifact_type",
        s3=[VersionedS3Object("bucket", "key", "version_id")],
    )
    assert artifact.name == "artifact_name"
    assert artifact.artifact_type == "artifact_type"
    assert artifact.s3 == [VersionedS3Object("bucket", "key", "version_id")]


@pytest.mark.parametrize(
    "artifact_name",
    ["with/slashes", "with spaces", "illegalpunctuation!", "", "****"],
)
def test_invalid_aeromancyartifact(artifact_name) -> None:
    """Ensure WandbArtifactName fails with invalid artifact names."""
    with pytest.raises(ValueError):  # noqa: PT011
        AeromancyArtifact(
            artifact_name,
            "artifact_type",
            s3=[VersionedS3Object("bucket", "key", "version_id")],
        )


@pytest.mark.parametrize(
    "artifact_name",
    ["valid-name", "also_valid", "still-valid-23", None],
)
def test_validate_wandb_artifact_string_valid_name(artifact_name) -> None:
    """Ensure WandbArtifactName works with valid artifact names."""
    _validate_wandb_artifact_string(artifact_name, "test role")


@pytest.mark.parametrize(
    "artifact_name",
    ["with/slashes", "with spaces", "illegalpunctuation!", "", "****"],
)
def test_validate_wandb_artifact_string_invalid_name(artifact_name) -> None:
    """Ensure WandbArtifactName works with valid artifact names."""
    with pytest.raises(ValueError):  # noqa: PT011
        _validate_wandb_artifact_string(artifact_name, "test role")


def test_resolve_artifact() -> None:
    """Test artifact resolution with no overrides."""
    # Ensure no artifact overrides are set.
    get_runtime_environment().artifact_overrides = []

    resolved = WandbArtifactName.resolve_artifact_name("artifactname")
    assert resolved == "artifactname:latest"


def test_resolve_artifact_unversioned_with_overrides() -> None:
    """Test unversioned artifact resolution with an artifact override."""
    # Force a specific version of our test artifact.
    get_runtime_environment().artifact_overrides = ["artifactname:v3"]

    resolved = WandbArtifactName.resolve_artifact_name("artifactname")
    assert resolved == "artifactname:v3"


def test_resolve_artifact_versioned_with_overrides() -> None:
    """Test versioned artifact resolution with an artifact override."""
    # Force a specific version of our test artifact.
    get_runtime_environment().artifact_overrides = ["artifactname:v3"]

    resolved = WandbArtifactName.resolve_artifact_name("artifactname:v5")
    # We should get the overridden version even if it was already set.
    assert resolved == "artifactname:v3"


def test_resolve_artifact_tagged_version_with_overrides() -> None:
    """Test artifact resolution with an artifact override and a version tag."""
    # Force a specific version of our test artifact.
    get_runtime_environment().artifact_overrides = ["artifactname:v3"]

    resolved = WandbArtifactName.resolve_artifact_name("artifactname:latest")
    # We should get the overridden version even if it was already set to a tag.
    assert resolved == "artifactname:v3"


def test_resolve_artifact_with_irrelevant_overrides() -> None:
    """Ensure irrelevant overrides don't affect artifact resolution."""
    # Add a superfluous artifact override.
    get_runtime_environment().artifact_overrides = ["someotherartifact:v3"]

    resolved = WandbArtifactName.resolve_artifact_name("artifactname")
    assert resolved == "artifactname:latest"


def test_resolve_artifact_with_overrides_and_default_project() -> None:
    """Ensure we can resolve artifacts with project names partially filled in."""
    # Add a superfluous artifact override.
    get_runtime_environment().artifact_overrides = ["projectname/artifactname:v3"]

    resolved = WandbArtifactName.resolve_artifact_name(
        "artifactname",
        default_project_name="projectname",
    )
    assert resolved == "projectname/artifactname:v3"


def test_resolve_artifact_with_overrides_and_project() -> None:
    """Ensure we can resolve artifacts with project names filled in."""
    # Add a superfluous artifact override.
    get_runtime_environment().artifact_overrides = ["projectname/artifactname:v3"]

    resolved = WandbArtifactName.resolve_artifact_name("projectname/artifactname")
    assert resolved == "projectname/artifactname:v3"
