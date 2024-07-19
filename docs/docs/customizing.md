
# Customizing Aeromancy projects

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
- **Extra `docker run` arguments**: (E.g., mounting
  [volumes](https://docs.docker.com/engine/reference/commandline/run/#mount)).
  These can be baked `pdm go` script with `--extra-docker-run-args='...'`. The
  [template](https://github.com/quant-aq/aeromancy-project-template) includes a
  standard volume mapping (`data/`) for ingesting datasets.
- **Extra Debian packages:** (outside of those included by Aeromancy), you may
  want to bake them into the `pdm go` script with `--extra-debian-package='...'`
  (specify the flag once per package name).
- **Extra environment variables:** If your code needs information in environment
  variables (e.g., API keys and other credentials), you can pass tell Aeromancy
  to pass these through to container with `--extra-env-var` (specify the flag
  once per variable). Use these sparingly, as they could make steps using these
  variables harder to reproduce and are **not** tracked by Aeromancy.

## Filesystem layout

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
