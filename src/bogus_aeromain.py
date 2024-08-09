"""A bogus Aeromain for testing Aeromancy outside of Aeromancy projects.

This is enough to test both `--dev` mode. You can launch it with something like:

    shell> pdm debug_runner --aeromain src/bogus_aeromain.py --dev

Beyond that, flags are as they would be for a normal `pdm go` in an Aeromancy
project repo.
"""

from pathlib import Path

import rich_click as click
from rich.console import Console
from typing_extensions import override

from aeromancy import aeromancy_click_options
from aeromancy.action import Action
from aeromancy.action_builder import ActionBuilder
from aeromancy.s3 import S3Object
from aeromancy.tracker import Tracker

console = Console(log_time=False)


class BogusParentAction(Action):
    """Bogus Aeromancy `Action` for testing.

    Prints a message to let you know it ran and creates an output artifact.
    """

    job_type = "parent"
    job_group = "bogus"

    @override
    def outputs(self) -> list[str]:
        return ["bogus-parent"]

    @override
    def run(self, tracker: Tracker) -> None:
        output_path = Path("/tmp/bogus-output1.txt")  # noqa: S108
        output_path.write_text("BogusParentAction output!\n")

        [output_name] = self.outputs()
        tracker.declare_output(
            name=output_name,
            local_filenames=[output_path],
            s3_destination=S3Object("bogus-bucket", "key1/"),
            artifact_type="bogus-artifact",
            metadata={"meaning-of-life": 42},
            strip_prefix=Path("/tmp"),  # noqa: S108
        )
        print("Hello world from BogusParentAction.")


class BogusChildAction(Action):
    """Bogus Aeromancy `Action` for testing.

    Prints a message to let you know it ran and reads an input artifact from the
    parent.
    """

    job_type = "child"
    job_group = "bogus"

    @override
    def outputs(self) -> list[str]:
        return ["bogus-child"]

    @override
    def run(self, tracker: Tracker) -> None:
        [input_artifact], _ = self.get_io()
        [input_path] = tracker.declare_input(input_artifact)

        print("Hello world from BogusChildAction.")
        print(
            "Parent action created artifact with this text: "
            f"{input_path.read_text()!r}",
        )


class BogusActionBuilder(ActionBuilder):
    """Bogus Aeromancy `ActionBuilder` for testing.

    Creates a single `BogusAction`.
    """

    @override
    def build_actions(self) -> list[Action]:
        actions = []
        parent_action = self.add_action(actions, BogusParentAction(parents=[]))
        self.add_action(actions, BogusChildAction(parents=[parent_action]))
        return actions


@click.command()
@aeromancy_click_options
def aeromain(
    **aeromancy_options,
):
    """CLI application with a minimal Aeromain for Aeromancy development."""
    console.rule("[bold green][Bogus Aeromain][/bold green] Started!")
    action_builder = BogusActionBuilder(project_name="aeromancy-debug")
    action_runner = action_builder.to_runner()
    action_runner.run_actions(**aeromancy_options)
    console.rule("[bold green][Bogus Aeromain][/bold green] Done!")


if __name__ == "__main__":
    aeromain()
