"""Main entry point for Aeromancy.

This takes care of building/checking the Aeromancy environment and running Aeromancy
code properly.

You shouldn't ever need to run or call this directly -- the "pdm go" pdm script should
be setup in pyproject.toml.
"""

import os
import shlex
import subprocess
import sys
from pathlib import Path

import rich_click as click
from git.repo import Repo
from rich.console import Console
from rich.theme import Theme

from .click_options import runner_click_options
from .runtime_environment import (
    AEROMANCY_ARTIFACT_OVERRIDES_ENV,
    AEROMANCY_DEBUG_MODE_ENV,
    AEROMANCY_DEV_MODE_ENV,
    DOCKER_HASH_ENV,
    GIT_BRANCH_ENV,
    GIT_MESSAGE_ENV,
    GIT_REF_ENV,
    GIT_REMOTE_ENV,
    NOT_IN_DOCKER,
)

# Environment variables to passthrough to container
# These must be already set for Aeromancy to work properly.
PASSTHROUGH_ENV_VARIABLES = (
    "AEROMANCY_AWS_ACCESS_KEY_ID",
    "AEROMANCY_AWS_SECRET_ACCESS_KEY",
    "AEROMANCY_AWS_S3_ENDPOINT_URL",
    "AEROMANCY_AWS_REGION",
    "WANDB_API_KEY",
)

repo = Repo(".")
custom_theme = Theme({"info": "dim cyan", "warning": "magenta", "error": "bold red"})
console = Console(theme=custom_theme)


def interactive(command_pieces: list[str]) -> None:
    """Run interactive shell commands."""
    formatted_pieces = shlex.join(command_pieces)
    console.log(f"[bold]Running:[/bold] {formatted_pieces}", style="info")
    exit_code = subprocess.call(
        command_pieces,
        stdout=sys.stdout,
        stderr=subprocess.STDOUT,
    )
    if exit_code:
        console.log(f"Exit code {exit_code} for {formatted_pieces}", style="warning")


def check_git_state() -> None:
    """Ensure our git repo is set up properly for tracking."""
    if str(repo.active_branch) in ("main", "master"):
        raise SystemExit(
            "Error: Switch to a non-main branch before running experiments.",
        )

    # First, call `git diff` since it's well formatted.
    if subprocess.call("/usr/bin/git diff --exit-code", shell=True):  # noqa: S602
        print()

    if repo.is_dirty() or repo.untracked_files:
        if repo.untracked_files:
            console.log("Untracked files:", style="warning")
            for filename in repo.untracked_files:
                console.log(f"  {filename}", style="warning")
        console.log(
            "Error: You must checkin your code before starting a run.",
            style="error",
        )
        raise SystemExit


def build_docker(
    docker_tag: str,
    extra_debian_packages: list[str],
    quiet: bool = True,
) -> str:
    """Build our Docker image for running experiments.

    Returns the hash of the Docker image.
    """
    ssh_auth_sock = os.environ.get("SSH_AUTH_SOCK", "")
    docker_commmand_pieces = [
        "docker",
        "buildx",
        "build",
        # Forward SSH authorization so we can access private repos.
        f"--ssh=default={ssh_auth_sock}",
        # Add local project (i.e., not Aeromancy's repo) as a build context so
        # we can copy project-specific files to the image.
        "--build-context",
        "project=.",
    ]
    if extra_debian_packages:
        # Format with !r (repr()) to automatically handle spaces and escaping.
        build_arg = f"EXTRA_DEBIAN_PACKAGES={' '.join(extra_debian_packages)!r}"
        docker_commmand_pieces.extend(("--build-arg", build_arg))
    if quiet:
        docker_commmand_pieces.append("--quiet")
    docker_commmand_pieces.extend(
        (
            "--tag",
            docker_tag,
            # The version tag should be updated whenever ../../docker/Dockerfile
            # changes.
            "https://github.com/quant-aq/aeromancy.git#v0.2.2:docker",
        ),
    )

    console.log(
        f"[bold]Building Docker image:[/bold] {shlex.join(docker_commmand_pieces)}",
        style="info",
    )
    try:
        docker_output = subprocess.check_output(
            docker_commmand_pieces,
            text=True,
            stderr=subprocess.STDOUT,
        )
        docker_status = 0
    except subprocess.CalledProcessError as cpe:
        docker_output = cpe.output
        docker_status = cpe.returncode

    if docker_status or not quiet:
        console.log(
            f"Docker output:\n{docker_output}",
            style="error" if docker_status else "info",
        )
    if docker_status:
        raise SystemExit(f"Docker image building failed with exit code {docker_status}")
    return docker_output.strip()


def store_environment_variables(
    git_ref: str,
    docker_hash: str,
    dev_mode: bool,
    debug_mode: bool,
    aeromancy_artifact_overrides: list[str],
    extra_env_vars: list[str],
) -> str:
    """Store git and Docker info in environment variables to pass to container.

    Returns path to an file to pass to Docker via --env-file.
    """
    if dev_mode:
        # Set some bogus values so we can operate in development mode with an
        # incomplete Git repo setup.
        message_lines = ["development"]
        git_remote = "https://github.com/some-valid-looking/git-repo-url.git"
    else:
        message_lines = str(repo.commit().message).splitlines()
        git_remote = next(repo.remote().urls)

    # Show a truncated version of the first line.
    message = message_lines[0]
    if len(message_lines) > 1:
        message += " (...)"
    loguru_diagnose = not dev_mode
    updates: dict[str, str] = {
        GIT_REF_ENV: git_ref,
        GIT_MESSAGE_ENV: message,
        GIT_REMOTE_ENV: git_remote,
        GIT_BRANCH_ENV: str(repo.active_branch),
        DOCKER_HASH_ENV: docker_hash,
        AEROMANCY_ARTIFACT_OVERRIDES_ENV: ",".join(aeromancy_artifact_overrides),
        AEROMANCY_DEV_MODE_ENV: str(dev_mode),
        AEROMANCY_DEBUG_MODE_ENV: str(debug_mode),
        # Don't do loguru diagnose by default (can leak sensitive info in W&B logs)
        "LOGURU_DIAGNOSE": str(loguru_diagnose).lower(),
    }
    os.environ.update(updates)

    # There's enough environment variables that they clutter the Docker commmand,
    # so we store them in an --env-file.
    all_passthrough_variables = PASSTHROUGH_ENV_VARIABLES + tuple(extra_env_vars)
    env_file_path = Path(".env_file")
    with env_file_path.open("w") as env_file:
        for key in tuple(updates.keys()) + all_passthrough_variables:
            env_file.write(f"{key}\n")
    return str(env_file_path)


def run_docker(
    env_filename: str,
    docker_tag: str,
    docker_subcommand_pieces: list[str],
    extra_docker_run_args: list[str],
) -> None:
    """Run `docker run` with specified arguments."""
    local_cache_path = Path("~/Cache").expanduser()
    interactive(
        [
            "docker",
            "run",
            "--env-file",
            env_filename,
            "-v",
            f"{local_cache_path}:/root/Cache",
            *extra_docker_run_args,
            "-it",
            docker_tag,
            *docker_subcommand_pieces,
        ],
    )


@click.command(
    context_settings={
        "ignore_unknown_options": True,  # Extra options are passed through to Aeromain.
        "help_option_names": ["-h", "--help"],
    },
)
@runner_click_options
@click.argument("extra_cmdline_args", nargs=-1, type=click.UNPROCESSED)
def main(
    debug_shell: bool,
    dev: bool,
    extra_docker_run_args: list[str],
    extra_debian_packages: list[str],
    extra_env_vars: list[str],
    artifact_overrides: list[str],
    extra_cmdline_args: list[str],
    debug: bool,
    aeromain_path: str,
) -> None:
    """Run Aeromancy as a CLI application."""
    if debug_shell or dev:
        # These values aren't critical in development mode. We fill them in
        # since an early Aeromancy project might not be completely set up with
        # Git.
        git_ref = docker_tag = "development"
    else:
        git_ref = str(repo.commit())
        docker_tag = git_ref[:7]  # Keep it short for cleaner command lines.
        check_git_state()

    # Autoset debug mode when we're doing a debug_shell (these are separate
    # options since we might want debug mode outside of a debug shell).
    debug = debug or debug_shell

    if dev:
        docker_hash = NOT_IN_DOCKER
    else:
        docker_hash = build_docker(
            docker_tag=docker_tag,
            extra_debian_packages=extra_debian_packages,
            quiet=not debug,
        )
        if debug:
            # Building Docker images in debug mode makes it tough to determine
            # the image hash, so we'll set it to a special value.
            # TODO: Parse Docker image hash in these cases?
            docker_hash = "debug_docker_hash"
    env_filename = store_environment_variables(
        git_ref=git_ref,
        docker_hash=docker_hash,
        dev_mode=dev,
        debug_mode=debug,
        aeromancy_artifact_overrides=artifact_overrides,
        extra_env_vars=extra_env_vars,
    )

    if debug_shell:
        docker_subcommand_pieces = [
            "/bin/sh",
            *extra_cmdline_args,
        ]
    else:
        docker_subcommand_pieces = [
            "pdm",
            "run",
            "python",
            aeromain_path,
            *extra_cmdline_args,
        ]

    if dev:
        interactive(docker_subcommand_pieces)
    else:
        run_docker(
            env_filename,
            docker_tag,
            docker_subcommand_pieces,
            extra_docker_run_args,
        )


if __name__ == "__main__":
    main()
