"""Execute a computation graph over Action objects using pydoit."""

import tempfile
import typing

import pydot
import term_image.image
from doit.cmd_base import TaskLoader2
from doit.doit_cmd import DoitMain
from doit.reporter import ConsoleReporter
from doit.task import Task as DoitTask
from rich import print as rich_print
from rich.console import Console
from typing_extensions import override

from .action import Action
from .fake_tracker import FakeTracker
from .runtime_environment import get_runtime_environment

console = Console()

ActionType = typing.TypeVar("ActionType", bound=Action)


def task_to_rich_markup(task: DoitTask):
    """Format a pydoit task for Rich Console."""
    meta = task.meta or {}
    return f"\\[[bold]{meta['job_type']}[/bold]] {meta['outputs'][0]}"


class RichConsoleReporter(ConsoleReporter):
    """Logs pydoit events using Rich Console."""

    def _draw_rule(
        self,
        emoji: str,
        line_color: str,
        message: str,
        task: DoitTask,
        message_style: str | None = None,
    ):
        message_style = line_color if message_style is None else message_style
        console.rule(
            f"{emoji}[{line_color}] ─── [/{line_color}]"
            f"[{message_style}]{message}[/{message_style}] "
            + task_to_rich_markup(task),
            style=line_color,
            align="left",
        )

    @override
    def execute_task(self, task: DoitTask):
        self._draw_rule(
            emoji="🚀",
            line_color="green",
            message="Running",
            task=task,
        )

    @override
    def skip_uptodate(self, task: DoitTask):
        self._draw_rule(
            emoji="⏭️ ",  # Needs an extra space Because Unicode(tm).
            line_color="yellow",
            message_style="yellow italic",
            message="Skipped",
            task=task,
        )

    @override
    def add_failure(self, task: DoitTask, _):
        self._draw_rule(
            emoji="💣",
            line_color="red",
            message="Task failed:",
            task=task,
        )


class ActionRunner(TaskLoader2):
    """Bridge between ActionBuilder and pydoit.

    Under the hood, this is a pydoit `TaskLoader2`. The `run_actions`
    convenience method is the main entry point for running these tasks via
    pydoit.
    """

    def __init__(self, actions: list[Action]):
        """Create a runner for already constructed `Action`s.

        Parameters
        ----------
        actions
            `Action`s to run.
        """
        self.actions = actions
        self.job_name_filter = None
        self.job_tags = set()

    @override
    def load_doit_config(self):
        # verbosity=2 makes doit not mess with stdout/stderr.
        return {
            "verbosity": 2,
            "reporter": RichConsoleReporter,
        }

    @override
    def load_tasks(self, **unused) -> list[DoitTask]:
        tasks = []
        for action in self.actions:
            action._set_runtime_properties(tags=self.job_tags)
            tasks.append(self._convert_action_to_doittask(action))

        return tasks

    def _convert_action_to_doittask(
        self,
        action: Action,
    ) -> DoitTask:
        if get_runtime_environment().dev_mode:
            action._set_tracker(FakeTracker)

        outputs = action.outputs()
        skip = action.skip

        if self.job_name_filter is not None:
            description = f"{action.job_type} {' '.join(outputs)}"
            # Filter overrides normal skip settings.
            skip = not self.job_name_filter(description)

        task_deps = []
        for parent in action.parents:
            task_deps.extend(parent.outputs())

        doit_task = DoitTask(
            name=outputs[0],
            doc=action.job_type,
            actions=[action._run],
            task_dep=task_deps,
            uptodate=[skip],
            meta={
                "job_type": action.job_type,
                "outputs": action.outputs(),
            },
            io={"capture": False},  # doit shouldn't mess with stdin, etc.
        )

        if self.job_name_filter is not None:
            message = (
                "[white on red] NO [/white on red]"
                if skip
                else "[black on bright_green] GO [/black on bright_green]"
            )
            console.log(f"Action filter: {message} {task_to_rich_markup(doit_task)}")

        return doit_task

    def _draw_graph(self):
        dot = pydot.Dot(resolution=300)
        for task in self.load_tasks():
            up_to_date = task.uptodate[0][0]
            job_type = task.meta["job_type"]  # type: ignore
            label = f"{job_type} | {task.name}"
            dot.add_node(
                pydot.Node(
                    task.name,
                    label=label,
                    shape="record",
                    fontname="Sans-Serif",
                    color="yellow" if up_to_date else "green",
                ),
            )
            for parent in task.task_dep:
                dot.add_edge(pydot.Edge(parent, task.name))

        with tempfile.NamedTemporaryFile(suffix=".png") as dot_png_file:
            dot.write(dot_png_file.name, format="png")
            deps_image = term_image.image.from_file(dot_png_file.name)
            deps_image.draw()

    def _list_actions(self):
        for task in self.load_tasks():
            rich_print(task_to_rich_markup(task))

    def run_actions(
        self,
        only: set[str] | None,
        graph: bool,
        list_actions: bool,
        tags: set[str] | None,
        **unused_kwargs,
    ):
        """Run the stored `Action`s using pydoit.

        Parameters
        ----------
        only
            If set, a comma-separated list of substrings to filter job names
            against. In this case, we will only run jobs that match at least one
            of these filters.
        graph
            If True, show the action dependency graph and exit.
        list_actions
            If True, show a list of action names and exit.
        tags
            If set, a comma-separated list of tags to apply to all jobs launched.
        unused_kwargs
            Should not be used -- this is here as part of some Click hackery to
            show all options in the help menu.
        """
        if only:

            def job_name_filter(job_name):
                for job_name_substring in only:
                    if job_name_substring.strip() in job_name:
                        return True
                return False

            self.job_name_filter = job_name_filter

        if graph:
            self._draw_graph()
            raise SystemExit

        if list_actions:
            self._list_actions()
            raise SystemExit

        self.job_tags = tags

        if get_runtime_environment().dev_mode:
            console.rule(
                "[red bold]DEV MODE[/red bold]",
                style="red",
                characters="⚠️  ",
            )

        # Launch pydoit.
        DoitMain(self).run([])
