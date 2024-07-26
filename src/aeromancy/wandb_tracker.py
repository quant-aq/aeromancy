"""Tracker backed by Weights and Biases and S3.

Weights and Biases is used to track runs and S3 to store artifacts.
"""

from collections.abc import Sequence
from pathlib import Path
from typing import Any

import wandb
import wandb.sdk.wandb_run
from loguru import logger
from typing_extensions import override

from aeromancy.artifacts import AeromancyArtifact, Artifacts
from aeromancy.runtime_environment import get_runtime_environment
from aeromancy.s3 import S3Object
from aeromancy.tracker import Tracker


class WandbTracker(Tracker):
    """A single, logged piece of computation.

    This class uses Weights and Biases (W&B) as a backend for tracking.
    """

    @override
    def __init__(
        self,
        project_name: str,
        config: dict | None = None,
        job_type: str | None = None,
        job_group: str | None = None,
        tags: set[str] | None = None,
        quiet: bool = True,
    ):
        Tracker.__init__(
            self,
            project_name=project_name,
            config=config,
            job_type=job_type,
            job_group=job_group,
            tags=tags,
        )

        self.quiet = quiet

        runtime_environment = get_runtime_environment()
        git_ref = runtime_environment.git_commit_hash or ""
        # For "https://github.com/x/y.git", we'd pull out "y" as the job name
        job_name = runtime_environment.git_repo_name

        tags = self.tags or []
        tags.insert(f"git/{runtime_environment.git_branch}")

        # Run wandb init with our extra tracking data.
        notes = f"{runtime_environment.git_message} (git message for {git_ref[:6]})"
        wandb_run = wandb.init(
            project=project_name,
            config=config or {},
            job_type=job_type,
            group=job_group,
            notes=notes,
            tags=tags,
            settings=wandb.Settings(
                job_name=job_name,
                git_commit=git_ref,
                git_remote_url=runtime_environment.git_remote_url,
                docker=runtime_environment.docker_hash,
                quiet=self.quiet,
            ),
        )
        if not isinstance(wandb_run, wandb.sdk.wandb_run.Run):
            raise TypeError(
                f"Didn't get a valid run from Weights and Biases: {wandb_run}",
            )
        else:
            self.wandb_run = wandb_run

        self._artifacts = Artifacts(self.wandb_run)

    @override
    def __enter__(self):
        get_runtime_environment().confirm_running_from_container()
        self.wandb_run.__enter__()
        self._log_docker_package_versions()

        return self

    def _log_docker_package_versions(self):
        """Log all Docker package versions as a Weights and Biases Table artifact."""
        # packages_list.txt is created as part of Docker image construciton.
        packages_list = Path("/base/packages_list.txt").read_text()
        rows = [line.split("=", 1) for line in packages_list.splitlines()]
        package_version_table = wandb.Table(
            data=rows,
            columns=["package_name", "version"],
        )
        self.wandb_run.log(
            {"docker_package_versions": package_version_table},
            commit=False,
        )

    @override
    def __exit__(self, exctype, excinst, exctb) -> bool:
        had_error = exctype is not None
        if had_error:
            logger.exception(excinst)
        self.wandb_run.finish(quiet=self.quiet, exit_code=had_error)
        # TODO: find a better way to do this without lots of repeated stacktraces?
        return self.wandb_run.__exit__(exctype, excinst, exctb)

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
        return self._artifacts.declare_output(
            name=name,
            local_filenames=local_filenames,
            s3_destination=s3_destination,
            artifact_type=artifact_type,
            strip_prefix=strip_prefix,
            metadata=metadata,
        )

    @override
    def declare_input(
        self,
        artifact: AeromancyArtifact | str,
        use_as: str | None = None,
    ) -> Sequence[Path]:
        return self._artifacts.declare_input(artifact, use_as)

    @override
    def log(self, metrics: dict[str, Any]):
        wandb.log(metrics)
