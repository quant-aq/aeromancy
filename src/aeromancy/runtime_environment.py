"""Captures information about the runtime environment for Aeromancy."""

from contextlib import suppress
from os import environ as env

import giturlparse
from loguru import logger

# Constants for environment variables which configure runtime state.
AEROMANCY_DEV_MODE_ENV = "AEROMANCY_DEV_MODE"
AEROMANCY_DEBUG_MODE_ENV = "AEROMANCY_DEBUG_MODE"
AEROMANCY_ARTIFACT_OVERRIDES_ENV = "AEROMANCY_ARTIFACT_OVERRIDES"
DOCKER_HASH_ENV = "DOCKER_HASH"
GIT_BRANCH_ENV = "GIT_BRANCH"
GIT_MESSAGE_ENV = "GIT_MESSAGE"
GIT_REF_ENV = "GIT_REF"
GIT_REMOTE_ENV = "GIT_REMOTE"

# Used to explicitly mark that we're not running in Docker.
NOT_IN_DOCKER = "NOT_IN_DOCKER"

# Singleton to store our RuntimeEnvironment instance. See get_runtime_environment().
_runtime_environment = None


class RuntimeEnvironment:
    """Information about the runtime environment for Aeromancy.

    Note: You should not need to create one of these on your own. See
    `get_runtime_environment`.
    """

    def __init__(self):
        """Determine the current runtime environment."""
        self.docker_hash = env.get(DOCKER_HASH_ENV)
        if not self.docker_hash or self.docker_hash == NOT_IN_DOCKER:
            self.docker_hash = None

        # When running in dev mode, we use FakeTracker and avoid any calls
        # to W&B or S3.
        self.dev_mode = env.get(AEROMANCY_DEV_MODE_ENV, "").lower() == "true"

        # Debug mode makes us more verbose about Aeromancy internals. It's
        # primarily used for debugging Aeromancy itself or in conjunction with
        # dev mode while performing development in an Aeromancy project.
        self.debug_mode = env.get(AEROMANCY_DEBUG_MODE_ENV, "").lower() == "true"

        # Offline mode means we should avoid any sort of network access. It's currently
        # only triggered by dev mode.
        self.offline = self.dev_mode

        self.git_commit_hash = env.get(GIT_REF_ENV)
        self._parse_git_remote()
        self.git_message = env.get(GIT_MESSAGE_ENV)
        self.git_branch = env.get(GIT_BRANCH_ENV)

        # Parse artifact overrides (comma-separated list)
        artifact_overrides_env = env.get(AEROMANCY_ARTIFACT_OVERRIDES_ENV, "")
        self.artifact_overrides: list[str] = (
            artifact_overrides_env.split(",") if artifact_overrides_env else []
        )

    def _parse_git_remote(self):
        """Parse Git remote URL (if available)."""
        self.git_remote_url = env.get(GIT_REMOTE_ENV)
        self.git_repo_name = None

        with suppress(ValueError, TypeError):
            parsed = giturlparse.parse(self.git_remote_url)
            if parsed.valid:
                self.git_repo_name = parsed.data.get("repo")

        if not self.git_repo_name:
            message = f"Couldn't parse Git remote URL: {self.git_remote_url!r}"
            if self.dev_mode:
                # Let them off with a warning, since results won't be logged anyway.
                logger.warning(message)
            else:
                raise ValueError(message)

    def confirm_running_from_container(self) -> None:
        """Gut check to ensure Aeromancy main scripts aren't run directly."""
        if self.dev_mode:
            # Development mode lets you bypass this check.
            return

        if not (self.docker_hash and self.git_commit_hash):
            # TODO: point to appropriate docs
            raise SystemExit(
                "Error: Aeromancy Trackers can only be used when running in a "
                "Docker container.",
            )


def get_runtime_environment() -> RuntimeEnvironment:
    """Fetch the `RuntimeEnvironment` global.

    This is created on demand and reuses existing instances.
    """
    global _runtime_environment
    if not _runtime_environment:
        _runtime_environment = RuntimeEnvironment()
    return _runtime_environment


def _ensure_valid_environment():
    """Ensure we're able to run Aeromancy functions in a non-standard settings.

    Examples of non-standard settings include running the test suite or
    accessing tools in Notebooks (e.g., `get_artifact_paths`). Standard
    environments include typical usage with Weights and Biases and `--dev` mode.

    You shouldn't need to call this function outside of Aeromancy directly.
    """
    # When running tests, this won't be set by runner.py, so we need to set it
    # manually. Technically, its contents don't matter -- just needs to be a valid
    # Git repo.
    if not env.get(GIT_REMOTE_ENV):
        env[GIT_REMOTE_ENV] = "https://github.com/some-valid-looking/git-repo-url.git"
