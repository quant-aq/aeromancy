"""Script to rerun an existing Aeromancy run.

Run with:

    shell> pdm aeroview <Weights and Biases run name>

After it creates a Git repo for that run, it will provide instructions for how to rerun.
"""
import subprocess
import tempfile
from dataclasses import dataclass

import rich_click as click
import wandb
import wandb.apis
from git.repo import Repo
from rich import print
from rich.console import Console

CLICK_CONTEXT_SETTINGS = {"help_option_names": ["-h", "--help"]}
console = Console()


@dataclass
class _RerunDetails:
    """Information relevant to rerunning a specific Weights and Biases run.

    Should not be used outside of this specific task.
    """

    git_commit: str
    git_remote: str
    wandb_id: str
    artifact_names: list[str]


def fetch_metadata_for_run(run_path: str) -> _RerunDetails:
    """Extract information for how to rerun a run from Weights and Biases.

    Parameters
    ----------
    run_path
        Any string that Weights and Biases will parse as a run name. Typically
        something like `orgname/projectname/runname` where `runname` is a string
        of alphanumeric characters.

    Returns
    -------
        Key information for how to rerun `run_path` with the same state, code, etc.
    """
    wandb_api = wandb.Api()
    run = wandb_api.run(run_path)

    try:
        git_metadata = run.metadata["git"]
        git_commit = git_metadata["commit"]
        git_remote = git_metadata["remote"]
    except KeyError as ke:
        raise KeyError("Couldn't find git metadata in Weights and Biases run") from ke

    artifact_names = [
        used_artifact.source_qualified_name
        for used_artifact in run.used_artifacts()
        if used_artifact.type != "job"
    ]

    return _RerunDetails(git_commit, git_remote, run.id, artifact_names)


def checkout_git_commit(git_remote, git_commit, checkout_dir, branch_name):
    """Checkout a specific Git commit into a local directory.

    Parameters
    ----------
    git_remote
        URL to Git repository.
    git_commit
        Specific commit to checkout from `git_remote`
    checkout_dir
        Directory for checkout of `git_remote`
    branch_name
        Name of branch in the checkout to point to `git_commit`
    """
    repo = Repo.clone_from(git_remote, to_path=checkout_dir)

    # Switch to the commit used in the run.
    # Confused? See https://gitpython.readthedocs.io/en/stable/tutorial.html#switching-branches
    rerun_branch = repo.create_head(branch_name, git_commit)
    repo.head.reference = rerun_branch
    if repo.head.is_detached:
        raise ValueError(f"Repo head is detached: {repo}")
    # Reset the index and working tree to match the pointed-to commit
    repo.head.reset(index=True, working_tree=True)


@click.command(context_settings=CLICK_CONTEXT_SETTINGS, no_args_is_help=True)
@click.argument("run")
def rerun(run: str) -> None:
    """Rerun a specific Weights and Biases run.

    RUN is the name of Weights and Biases Run to rerun. Typical names look like
    `org/project/alphanumericchars` though often parts of Weights & Biases run URLs can
    be used, e.g., ``org/project/runs/alphanumericchars`.
    """
    console.rule(f"Rerunning Weights and Biases run {run!r}")
    rerun_details = fetch_metadata_for_run(run)
    console.log("Rerun details:", rerun_details)
    git_commit = rerun_details.git_commit
    git_remote = rerun_details.git_remote

    console.rule(f"Cloning commit {git_commit!r} from {git_remote}")
    checkout_dir = tempfile.mkdtemp(prefix=f"rerun-{rerun_details.wandb_id}-")
    console.log("Checkout directory:", checkout_dir)
    checkout_git_commit(git_remote, git_commit, checkout_dir, "rerun_branch")

    console.log("Installing PDM dependencies")
    subprocess.check_call(["pdm", "install"], cwd=checkout_dir)  # noqa: S607

    artifact_flags = [
        f"--artifact-override {artifact_name}"
        for artifact_name in rerun_details.artifact_names
    ]
    artifact_flags_str = ""
    if artifact_flags:
        artifact_flags_str = " \\\n\t".join(["", *artifact_flags])
    console.log("Rerun with:")
    # No console.log() here since it will include line numbers and make copy-paste
    # messy.
    print(f"  cd {checkout_dir} && pdm go{artifact_flags_str}")


if __name__ == "__main__":
    rerun()
