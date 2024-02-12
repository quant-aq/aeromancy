# Aeromancy scaffolding

<!-- TODO: These look best in mkdocs HTML. Maybe we can find a better way of
doing the cross-references. -->

In order to enable tracking, Aeromancy is rather opinionated about how projects
are set up. A "project" in this case means a pipeline of tasks, potentially
configurable through CLI flags. This document provides an overview of the
components involved and how to set up a new Aeromancy project.

This diagram roughly shows the flow:

``` mermaid
graph LR
    pdmgo[shell> pdm go] -->|runs| runner[aeromancy.runner]
    subgraph pdm [pdm virtualenv]
        runner -->|runs| aeromain
        runner -->|builds| Dockerfile
        Dockerfile -->|specifies container| docker
        subgraph docker [docker image]
            subgraph projectspecific [project-specific code]
                aeromain --> etc[...]
            end
        end
    end
    pdmgo -->|script defined by| pyproject[pyproject.toml]
    pyproject -->|customizes via build args| Dockerfile

    %% Project specific (blue)
    style projectspecific stroke:blue
    style pdm stroke:blue
    style pdmgo stroke:blue
    style docker stroke:blue
    style aeromain stroke:blue
    style etc stroke:blue
    style pyproject stroke:blue
    %% Aeromancy provided (red)
    style runner stroke:red
    style Dockerfile stroke:red
```

(red indicates something provided by Aeromancy, blue indicates something
specific to the user's project)

## Entry points

In order to run pipelines with full tracking, Aeromancy runs project-specific
code inside a [Docker](http://docker.com) container. This means that we end up
with two main-like files:

1. One provided by Aeromancy that lives outside the container to set up the
container ([`aeromancy.runner`][]) and
2. A project-specific one that runs inside the container (the project's "AeroMain").

### The [`aeromancy.runner`][] module

Aeromancy pipelines are invoked by a [PDM](https://pdm.fming.dev/latest/)
[script](https://pdm.fming.dev/latest/usage/scripts/) called `pdm go` which
launches [`aeromancy.runner`][] inside PDM's virtual environment.

[`aeromancy.runner`][] sets up the runtime environment and, in the common case,
and launches AeroMain inside a Docker container. This may include several
customizations, including additional `docker run` flags (e.g., to set additional
[volumes](https://docs.docker.com/engine/reference/commandline/run/#mount)) and
extra Debian packages to include in the Docker image.

(**NOTE:** In development mode, we bypass Docker for speed and run AeroMain
directly in a subprocess.)

### Inside AeroMain

AeroMain parses project-specific command line flags to determine common
configuration options. It then instantiates a project-specific
[`ActionBuilder`][aeromancy.action_builder.ActionBuilder] class. This class is
responsible for generating sequences of project-specific
[`Action`][aeromancy.action.Action] objects and their dependency structures.
Finally, it hands off the
[`ActionBuilder`][aeromancy.action_builder.ActionBuilder] to an
[`ActionRunner`][aeromancy.action_runner.ActionRunner] to actually executes the
generated [`Action`][aeromancy.action.Action]s.

See [Tasks, Trackers, and Actions](tasks.md) for more information on these
objects.

## Creating a new Aeromancy project

In order to set up a new project, you'll need a Git repository with these
components:

- Actions (subclasses of [`Action`][aeromancy.action.Action] with specific logic
  for your tasks)
- An [`ActionBuilder`][aeromancy.action_builder.ActionBuilder] to instantiate
  the [`Action`][aeromancy.action.Action] objects and describe their
  dependencies
- An "AeroMain" script to parse any project-specific options and bring it all
  together

To quickly set up an Aeromancy project, we've created a
[Copier](https://copier.readthedocs.io/en/stable/) template. See instructions at
the
[quant-aq/aeromancy-project-template](https://github.com/quant-aq/aeromancy-project-template?tab=readme-ov-file#quick-start).
In the generated Python project setup (`pyproject.toml`), you may also want to
adjust:

- **Extra Python packages:** Add them with `pdm add <pkgname>`. See [PDM
  docs](https://pdm.fming.dev/latest/usage/dependency/) for more information on
  this.
- **`pdm` [scripts](https://pdm.fming.dev/latest/usage/scripts/)**: Some of
  these are necessary for running Aeromancy (like `pdm go`), but you can add
  more if there are common tasks for your project.
- **Extra `docker run` arguments**: E.g., mounting
  [volumes](https://docs.docker.com/engine/reference/commandline/run/#mount)).
  These can be baked `pdm go` script with `--extra-docker-run-args='...'`.
- **Extra Debian packages:** (outside of those included by Aeromancy), you may
  want to bake them into the `pdm go` script with `--extra-debian-package='...'`
  (specify the flag once per package name).
- **Development environment (linters, etc.):** Aeromancy encourages the use of
  the `ruff` linter and `Black` formatter, but these are customizable.

### Filesystem layout

Ultimately, the structure of an Aeromancy project should look something like
this:

```text
<projectroot>/
  pyproject.toml
  pdm.lock
  main.py  # AeroMain
  src/
    <projectname>/
      <youractions>.py
      <youractionbuilder>.py
```

The structure of the classes containing your
[`Action`][aeromancy.action.Action](s) and
[`ActionBuilder`][aeromancy.action_builder.ActionBuilder] is flexible -- they
just need to be importable in AeroMain.
