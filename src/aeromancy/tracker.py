"""Record details around code execution for repeatable data pipelines.

A Tracker is responsible for tracking the running of specific code, where
tracking includes the operating system state (Docker), external artifacts (S3),
the code itself (GitHub). Trackers also help organize runs, generally following
Weights and Biases organization.

In general, Trackers should be used as context managers surrounding the code to
be tracked.

Terminological note: The closest corresponding object in Weights and Biases is a
`Run`. Aeromancy Trackers have a different name to distinguish them from W&B
runs and indicate a larger scope.
"""

from abc import ABC, abstractmethod
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from .artifacts import AeromancyArtifact
from .s3 import S3Object

# TODO: create MockTracker for testing


class Tracker(ABC):
    """A single, logged piece of computation.

    This version of the class is abstract to specify the interface.
    """

    def __init__(
        self,
        project_name: str,
        config: dict | None = None,
        job_type: str | None = None,
        job_group: str | None = None,
        tags: set[str] | None = None,
    ):
        """Create a Tracker.

        Several parameters are purely for organization purposes. The hierarchy
        is essentially:

            project_name
                job_group
                    job_type
                        (individual run)

        In addition, a task may be associated with any number of tags.

        Parameters
        ----------
        project_name
            Name of the project, should correspond to a W&B project.
        config, optional
            Input parameters to a task. For ML, these include hyperparameters.
            For other tasks, these can include things such as command line
            flags.
        job_type, optional
            Typically used to describe the action of a specific task (e.g.,
            "munge", "evaluate")
        job_group, optional
            Typically used to describe the general goal of a group of tasks
            (e.g., "build", "model")
        tags, optional
            List of additional tags (strings) to associate with the task.
        """
        self.project_name = project_name
        self.config = config
        self.job_type = job_type
        self.job_group = job_group
        self.tags = tags or set()

    @abstractmethod
    def __enter__(self):
        """Use this Tracker as a context manager.

        This should be run before running the code to track.
        """
        raise NotImplementedError

    @abstractmethod
    def __exit__(self, exctype, excinst, exctb) -> bool:
        """Finish using this Tracker as a context manager.

        This should be run after running the code to track.
        Parameters and return values are standard for context managers.
        """
        raise NotImplementedError

    @abstractmethod
    def declare_output(
        self,
        name: str,
        local_filenames: Sequence[Path],
        s3_destination: S3Object,
        artifact_type: str,
        strip_prefix: Path | None = None,
        metadata: dict | None = None,
    ) -> AeromancyArtifact:
        """Declare and store local files as associated artifacts.

        These are uploaded and versioned on S3 and versioned on W&B.

        Parameters
        ----------
        name
            Name for the output artifact.
        local_filenames
            Paths to local files to be stored and associated with the artifact.
        s3_destination
            Where to store the artifacts on S3 (bucket and prefix for keys).
            Actual keys will be combined with the filenames in
            `local_filename_or_filenames`.
        artifact_type, optional
            Approximate type of the artifact, typically used as a human readable
            extension (e.g., "dataset", "predictions", "metadata").
        strip_prefix, optional
            Parts of the local filenames which should not be part of the
            structure when copied to S3. For example, if you want to store a
            file `/tmp/results.txt` but exclude `/tmp/`, you'd set
            `strip_prefix=Path('/tmp')`.
        metadata
            Any extra information to be associated with the artifact.

        Returns
        -------
            `AeromancyArtifact` representing this output.
        """
        raise NotImplementedError

    @abstractmethod
    def declare_input(
        self,
        artifact: AeromancyArtifact | str,
        use_as: str | None = None,
    ) -> Sequence[Path]:
        """Declare that this run depends on an existing artifact.

        If needed, this will fetch and catch the corresponding files for the artifact.

        Parameters
        ----------
        artifact
            An existing AeromancyArtifact or a W&B full name. A Weights & Biases
            full name is obtained from clicking the "Full name" field
            in the Version overview for an artifact.
        use_as, optional
            Additional metadata to track how this is being used.

        Returns
        -------
            Local paths to the artifact.
        """
        raise NotImplementedError

    @abstractmethod
    def log(self, metrics: dict[str, Any]) -> None:
        """Record a set of metrics to be associated with this run.

        Parameters
        ----------
        metrics
            Dictionary of string to any type of object that W&B will accept.
        """
        raise NotImplementedError
