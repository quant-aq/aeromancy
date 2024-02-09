"""Action objects are the core piece of trackable computation in Aeromancy."""

from .artifacts import WandbArtifactName
from .tracker import Tracker
from .wandb_tracker import WandbTracker


class Action:
    """A specific piece of work to track.

    This includes the code to run, artifacts it depends on, and artifacts it
    produces. For organizational purposes, they can fill in class variables:

    - `job_type`
    - `job_group`

    (`job_group` is more general than `job_type`. Semantics are up to the
    project design and `Tracker` backend.)
    """

    # Properties for subclasses to fill in.
    job_type: str | None = None
    job_group: str | None = None

    def __init__(self, parents: list["Action"], **config):
        """Create an `Action`.

        Parameters
        ----------
        parents
            `Action`s that this `Action` depends on. These must be run first.
        config
            Any `Action`-specific configuration. If the `Action` were a function
            call, these would be its parameters (e.g., hyperparameters for many
            ML algorithms).
        """
        self.config = config
        self.parents = parents
        self._tracker_class = WandbTracker
        self._project_name = None

    def outputs(self) -> list[str]:
        """Describe what this `Action` will produce after being run.

        Must be overridden.

        Returns
        -------
            List of artifact names that this `Action` will produce.
        """
        raise NotImplementedError

    def run(self, tracker: Tracker) -> None:
        """Execute this action.

        Parameters
        ----------
        tracker
            An Aeromancy `Tracker` for this task.

        This logic is Action-specific and must be overridden by subclasses.
        """
        raise NotImplementedError

    # TODO: should return outputs()? Then we can store them between runs.
    def _run(self) -> None:
        """Actual run method that task runners call.

        Should not be called directly.
        """
        if self._project_name is None:
            raise ValueError(
                f"Must set project_name on your Action class: {self.__class__}",
            )

        with self._tracker_class(
            job_type=self.job_type,
            job_group=self.job_group,
            config=self.config,
            project_name=self._project_name,
        ) as tracker:
            self.run(tracker)

    def _set_tracker(self, tracker_class: type[Tracker]) -> None:
        """Set a different class to use for tracking.

        This should only be called under special circumstances (e.g., testing
        environments, offline mode).
        """
        self._tracker_class = tracker_class

    def get_io(self, resolve_outputs=False) -> tuple[list[str], list[str]]:
        """Get inputs and outputs for this `Action`.

        Parameters
        ----------
        resolve_outputs, optional
            If set, output artifacts will be versioned

        Returns
        -------
            Tuple with names of (input artifacts, output artifacts)
        """
        parent_outputs = []
        for parent in self.parents:
            parent_outputs.extend(parent.outputs())
        full_inputs = [
            WandbArtifactName.resolve_artifact_name(
                artifact_name,
                default_project_name=self._project_name,
            )
            for artifact_name in parent_outputs
        ]
        full_outputs = self.outputs()
        if resolve_outputs:
            full_outputs = [
                WandbArtifactName.resolve_artifact_name(
                    artifact_name,
                    default_project_name=self._project_name,
                )
                for artifact_name in full_outputs
            ]
        return (full_inputs, full_outputs)

    def _set_runtime_properties(self, project_name: str, skip: bool):
        """Set properties that we won't know until we're ready to run."""
        self._skip = skip
        self._project_name = project_name

    skip = property(lambda self: self._skip, doc="Whether this action should be run")
