"""Utilities for working with Aeromancy artifacts outside of Aeromancy.

While Aeromancy works best when you're keeping artifacts within Aeromancy,
sometimes you just need to pull an artifact out and analyze it in a Notebook.

Warning: Here be dragons (*cough* hacks). Code in this module relies on
Aeromancy internals and is subject to change.
"""

import os
from collections.abc import Sequence
from pathlib import Path

from wandb.sdk.wandb_run import Run as WandbRun

from aeromancy.artifacts import Artifacts, WandbArtifactName
from aeromancy.fake_tracker import FakeTracker
from aeromancy.runtime_environment import (
    AEROMANCY_DEV_MODE_ENV,
    _ensure_valid_environment,
)


class _MockWandbRun(WandbRun):
    """Weights and Biases Run-like object which doesn't do anything.

    Definitely a hack and only for use within get_artifact_paths() -- behavior
    outside of that is undefined.
    """

    def __init__(self, *args, **kwargs):
        pass

    def use_artifact(self, *args, **kwargs):
        pass


def get_artifact_paths(
    artifact_name: str,
    dev: bool = False,
) -> Sequence[Path]:
    """Get local paths for an Aeromancy Artifact for exporting purposes.

    This will not track a dependency on the artifact and must be run outside of
    an Aeromancy runner script (Aeromain). To get artifact paths within
    Aeromancy, just use `Tracker.declare_input()` which will track dependencies.

    Parameters
    ----------
    artifact_name
        An mostly-qualified artifact name, minimally with project and artifact
        names (e.g., "project/artifact-name"). Version numbers
        ("project/artifact-name:v2") and organization entities
        ("mycorp/project/artifact-name") can also be included.
    dev
        If True, use the dev version (FakeTracker, FakeCache, etc.) of the
        artifact. Otherwise, use the Weights and Biases version (requires
        network access).

    Returns
    -------
        A list of local paths for where to find the artifact.
    """
    # First, make sure we're not running via an Aeromancy runner script, since
    # this method is not intended to be used there.
    if AEROMANCY_DEV_MODE_ENV in os.environ:
        raise RuntimeError(
            "get_artifact_paths() should only be used in Notebooks or non-Aeromancy "
            "scripts. Within Aeromancy, getting an artifact path should be done "
            "through Tracker.declare_input().",
        )
    # Since we're not running in an Aeromancy runner script, perform any
    # necessary environment tweaks.
    _ensure_valid_environment()

    original_artifact_name = artifact_name
    artifact_name = WandbArtifactName.resolve_artifact_name(
        artifact_name=original_artifact_name,
        default_project_name=None,
    )

    if dev:
        # Project must be specified as part of `artifact_name` or we won't match
        # it. To keep the API simple, we don't include default_project_name as a
        # parameter.
        tracker = FakeTracker(project_name="fake_project")
        try:
            paths = tracker.declare_input(artifact_name)
        except KeyError as ke:
            raise KeyError(
                f"Couldn't find artifact {original_artifact_name!r} "
                f"(resolved to {artifact_name!r})",
            ) from ke
    else:
        artifact_handler = Artifacts(wandb_run=_MockWandbRun())
        paths = artifact_handler.declare_input(artifact_name)

    return paths
