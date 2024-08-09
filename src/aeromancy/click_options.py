"""Groups of Click options for the main Aeromancy CLI interface."""

import functools

import rich_click as click

# Named option groups to separate standard Aeromancy options from
# project-specific options.
click.rich_click.OPTION_GROUPS = {
    "main.py": [
        {
            "name": "Task runner options",
            "options": ["--only", "--graph", "--list-actions"],
        },
        {
            "name": "Aeromancy runtime options",
            "options": [
                "--dev",
                "--debug",
                "--debug-shell",
                "--extra-docker-run-args",
                "--extra-debian-package",
                "--extra-env-var",
                "--artifact-override",
            ],
        },
    ],
}


def runner_click_options(function):
    """Wrap `function` with all Click options for Aeromancy runtime."""
    # NOTE: Keep in sync with OPTION_GROUPS.

    @click.option(
        "--dev",
        is_flag=True,
        help="If set, use development mode for quickly testing changes (don't actually "
        "track anything, or use Weights and Biases, S3, Docker, etc.).",
    )
    @click.option(
        "--debug",
        is_flag=True,
        help="Used to aid in Aeromancy debugging. If set, Aeromancy and related tools "
        "(e.g., Docker) will be more verbose.",
    )
    @click.option(
        "--debug-shell",
        help="If True, open a debug shell in the Docker container instead of running "
        "Aeromain. Implies --debug.",
        is_flag=True,
    )
    @click.option(
        "--extra-docker-run-args",
        default="",
        metavar="ARGS",
        help=(
            "Flags or arguments to pass to Docker run verbatim (e.g., extra volumes to "
            "mount). You should generally not need to change this, but it may be "
            "set in pdm scripts when setting up a project."
        ),
    )
    @click.option(
        "--extra-debian-package",
        "extra_debian_packages",
        metavar="PKG",
        multiple=True,
        help=(
            "Name of a Debian package to include in the Docker image in addition to "
            "standard packages required by Aeromancy. Specify this option once per "
            "extra package. You should generally not need to change this, but it may "
            "be set in pdm scripts when setting up a project."
        ),
    )
    @click.option(
        "--extra-env-var",
        "extra_env_vars",
        metavar="VAR",
        multiple=True,
        help=(
            "Extra environment variable to passthrough to Aeromancy. Specify this "
            "option once per variable. You should generally not need to change this, "
            "but it may be set in pdm scripts when setting up a project."
        ),
    )
    @click.option(
        "--artifact-override",
        "artifact_overrides",
        metavar="NAMEVER",
        help=(
            "Set this to a versioned Weights and Biases artifact (e.g, 'a/b/c:v3') to "
            "force using that version for input. May be specified multiple times. For "
            "any artifact not mentioned, we will default to its latest Weights and "
            "Biases version."
        ),
        multiple=True,
    )
    @click.option(
        "--aeromain",
        "aeromain_path",
        default="src/main.py",
        metavar="PATH",
        # This is only intended for debugging/testing Aeromancy itself so hidden
        # to minimize confusion.
        hidden=True,
        help="Set an alternate Aeromain file to run.",
    )
    @functools.wraps(function)
    def wrapper_aeromancy_options(*args, **kwargs):
        return function(*args, **kwargs)

    return wrapper_aeromancy_options


def aeromancy_click_options(function):
    """Wrap `function` with all Click options for Aeromancy.

    This is intended to wrap an `aeromain` function.
    """
    # NOTE: Keep in sync with OPTION_GROUPS.

    @click.option(
        "-o",
        "--only",
        default=None,
        type=str,
        metavar="SUBSTRS",
        help="If set: comma-separated list of substrings. We'll only run jobs which "
        "match at least one of these (in dependency order).",
    )
    @click.option(
        "--graph",
        is_flag=True,
        help="If set: show a graph of job dependencies and exit.",
    )
    @click.option(
        "--list-actions",
        "--list",
        is_flag=True,
        help="If set: show a list of all job names and exit.",
    )
    @click.option(
        "--tags",
        "tags",
        metavar="TAGS",
        help="Comma-separated tags to add to each task launched. These tags are purely "
        "for organizational purposes.",
    )
    @runner_click_options
    @functools.wraps(function)
    def wrapper_aeromancy_options(*args, **kwargs):
        return function(*args, **kwargs)

    return wrapper_aeromancy_options
