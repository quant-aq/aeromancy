"""Build a computation graph over Action objects."""

from .action import Action
from .action_runner import ActionRunner, ActionType


class ActionBuilder:
    """Sets up and runs (via pydoit) a computation graph over `Action`s.

    Subclasses must implement `build_actions`.
    """

    def __init__(self, project_name):
        """Create an `ActionBuilder`.

        Parameters
        ----------
        project_name
            The project that the `Action`s created by this should live in.
        """
        self._project_name = project_name

    def build_actions(self) -> list[Action]:
        """Produce a list of `Action`s to run.

        This must be implemented by subclasses.

        For each action, you should use the `add_action` helper to add it to a
        local list of `Action`s. This will help you set internal states on
        `Action`s (e.g., if an action should be skipped under the current
        configuration). For example:

        ```
            def build_actions(self):
                actions = []
                a1 = self.add_action(actions, Action1(), skip=True)
                a2 = self.add_action(actions, Action2(parents=[a1]), skip=False)
                a3 = self.add_action(actions, Action3(parents=[a1]), skip=False)
                a4 = self.add_action(actions, Action4(parents=[a2, a3]), skip=False)
                return actions
        ```

        Returns
        -------
            List of `Actions` to run.
        """
        raise NotImplementedError

    def add_action(
        self,
        actions: list[Action],
        action: ActionType,
        skip: bool = False,
    ) -> ActionType:
        """Add an `Action` while setting run state for the `Action`.

        See `build_actions` for more details and example usage.

        Parameters
        ----------
        actions
            A growing list of `Action`s, built up in a `build_actions` method
        action
            `Action` to add to `actions`
        skip, optional
            Whether the `action` should not be run, by default False

        Returns
        -------
            The `Action` passed as `action`, with additional run state added
        """
        action._set_buildtime_properties(self._project_name, skip=skip)
        actions.append(action)
        return action

    def to_runner(self) -> ActionRunner:
        """Convert to an `ActionRunner` for running these actions.

        Returns
        -------
            An `ActionRunner` which can run the `Actions` specified in
            `build_actions` using pydoit.
        """
        return ActionRunner(self.build_actions())
