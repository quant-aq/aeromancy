# Aeromancy

[![Tests](https://github.com/quant-aq/aeromancy/actions/workflows/ci.yml/badge.svg)](https://github.com/quant-aq/aeromancy/actions/workflows/ci.yml)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![pdm-managed](https://img.shields.io/badge/pdm-managed-blueviolet)](https://pdm.fming.dev)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![pre-commit enabled](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&logoColor=white)](https://pre-commit.com/)
![Apache 2.0 licensed](https://img.shields.io/github/license/quant-aq/aeromancy)

**Aeromancy** is an opinionated philosophy and open-sourced framework that
closely tracks experimental runtime environments for more reproducible machine
learning. In existing experiment trackers, it’s easy to miss important details
about how an experiment was run, e.g., which version of a dataset was used as
input or the exact versions of library dependencies. Missing these details can
make replicability more difficult. Aeromancy aims to make this process smoother
by providing both new infrastructure (a more comprehensive versioning scheme
including both system runtimes and external datasets) and a corresponding set of
best practices to ensure experiments are maximally trackable.

In its current form, Aeromancy requires a fairly specific software stack: (hey,
we said it was opinionated)

- **Experiment tracker**: [Weights and Biases](https://wandb.ai)
- **Object storage** (artifacts): S3-compatible, e.g.,
  [Ceph](https://github.com/ceph/ceph)
- **Virtualization**: [Docker](https://www.docker.com/)
- **Python Package Manager**: [pdm](https://pdm.fming.dev)
- **Revision Control**: [Git](https://git-scm.com/)

## Aeromancy at SciPy 2024

Check out our [abstract](scipy_abstract.md) and [poster](https://raw.githubusercontent.com/quant-aq/aeromancy/main/docs/docs/Aeromancy_SciPy_2024_poster.pdf):

[![SciPy 2024 poster](https://raw.githubusercontent.com/quant-aq/aeromancy/main/docs/docs/Aeromancy_SciPy_2024_poster_thumb.png)](https://raw.githubusercontent.com/quant-aq/aeromancy/main/docs/docs/Aeromancy_SciPy_2024_poster.pdf)

## Documentation overview

- If you're new to Aeromancy, [start here](quick_start.md)! Or check out our
  [SciPy 2024](scipy_abstract.md) abstract for a high level overview.
- In the Developer Reference section of the documentation, we include some
  design docs which provide an [architectural overview](scaffolding.md) and a
  [glossary](tasks.md) of terms.
- Want to get involved? We have starting points in our [Contributor
  Guidelines](docs/docs/contributing.md).
- Lastly, we have autogenerated documentation in [Code
  Reference](reference/aeromancy/index.md).

!!! note
    Aeromancy documentation is still in a very early state. As this is a
    pre-release, support may be limited.
