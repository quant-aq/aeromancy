# Contributing

Contributions are welcome, and they are greatly appreciated! Every little bit
helps, and credit will always be given. Aeromancy is a young project and
expected to change much code and process-wise at first.

## Environment setup

Fork and clone the repository:

```bash
git clone https://github.com/<your-github-username>/aeromancy
cd aeromancy
```

We use [pdm](https://pdm.fming.dev) to manage the project and dependencies. To install PDM:

```bash
pip install --user "pdm[copier]"
```

Then you can install all Aeromancy dependencies with:

```bash
pdm install
```

You now have the dependencies installed. If you haven't used `PDM` before, it's
worth reading their [documentation](https://pdm-project.org/en/stable/), but we
include a few key commands below.

## Common development commands

- `pdm run`: Start a Python interpreter with PDM's virtual environment. This
  will have access to all of Aeromancy's dependencies
- `pdm run python <path/to/some/file.py>`: Similar to the above, but for running
  a Python script in PDM's virtual environment
- `pdm add <python-pkg-name>`: Add and install a new dependency
- `pdm lint`: Run pre-commit linters
- `pdm test`: Run test suite
- `pdm doc`: Start doc server (see also the [public
  version](https://quant-aq.github.io/aeromancy/) for the latest release)

## Bugs and feature requests

Check the list of [open issues](https://github.com/quant-aq/aeromancy/issues)
before filing. Please include as much information as you can so it's easier to
reproduce your issue. We can't promise we'll be able to address a feature
request, but we'd love to know what folks think is missing.

## Development

As usual:

1. Create a new branch: `git checkout -b your-username/feature-or-bugfix-name`
1. Edit the code and/or the documentation

If you updated the documentation or the project dependencies:

1. Run `pdm doc`
1. Go to <http://localhost:8030> and check that everything looks good.

**Before committing:**

1. Install [pre-commit](https://pre-commit.com/) and hooks:

   ```bash
   pre-commit install
   ```

1. Then linter task will be run each time when you commit something. Or you can run it manually:

   ```bash
   pdm lint
   ```

   The linter will autofix any issues that it can. We like to stage our changes
   before running the linter to make it easy to see what it changed.

1. Run the test suite and make sure everything is passing:

   ```bash
   pdm test
   ```

   If a test fails, please investigate and/or include a note in the PR if you think it's expected.

If you are unsure about how to fix or ignore a warning,
just let the continuous integration fail,
and we will help you during review.

## Pull requests guidelines

Please link to any related issue in the Pull Request message.
