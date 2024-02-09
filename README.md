# Aeromancy

[![Tests](https://github.com/quant-aq/aeromancy/actions/workflows/ci.yml/badge.svg)](https://github.com/quant-aq/aeromancy/actions/workflows/ci.yml)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![pdm-managed](https://img.shields.io/badge/pdm-managed-blueviolet)](https://pdm.fming.dev)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![pre-commit enabled](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&logoColor=white)](https://pre-commit.com/)
![Apache 2.0 licensed](https://img.shields.io/github/license/quant-aq/aeromancy)

**Aeromancy** is an opinionated philosophy and open-sourced framework that closely
tracks experimental runtime environments for more reproducible machine learning.
In existing experiment trackers, it’s easy to miss important details about how
an experiment was run, e.g., which version of a dataset was used as input or the
exact versions of library dependencies. Missing these details can make
replicability more difficult. Aeromancy aims to make this process smoother by
providing both new infrastructure (a more comprehensive versioning scheme
including both system runtimes and external datasets) and a corresponding set of
best practices to ensure experiments are maximally trackable.

In its current form, Aeromancy requires a fairly specific software stack:

- **Experiment tracker**: [Weights and Biases](https://wandb.ai)
- **Object storage** (artifacts): S3-compatible, e.g., [Ceph](https://github.com/ceph/ceph)
- **Virtualization**: [Docker](https://www.docker.com/)

**Coming soon**: A proper Getting Started section and a
[Copier](https://copier.readthedocs.io/en/stable/) template for quickly setting
up a new Aeromancy-managed project.

**Note:** As is likely obvious, Aeromancy documentation is in a very early
state. As this is a pre-release support may be limited. For now, we include a
couple pointers for how to setup your environment for Aeromancy. Once you have
[`pdm`](https://pdm.fming.dev) installed, run `pdm doc` to launch a doc server
which will provide additional information.

## Requirements

- Python 3.10.5 or higher
- [`pdm`](https://pdm.fming.dev): Install via `pip install --user pdm` then
  install Aeromancy packages with `pdm install`.
- **Environment variables**:
  - S3 backend location and credentials:
    - `AEROMANCY_AWS_ACCESS_KEY_ID`
    - `AEROMANCY_AWS_SECRET_ACCESS_KEY`
    - `AEROMANCY_AWS_S3_ENDPOINT_URL`
    - `AEROMANCY_AWS_REGION`
  - `WANDB_API_KEY` (from [Weights and Biases](https://wandb.ai))
- **SSH Authentication**: You'll want `ssh-agent` setup if you need to access
  private GitHub repositories. Check out these
  [instructions](https://docs.github.com/en/authentication/connecting-to-github-with-ssh/generating-a-new-ssh-key-and-adding-it-to-the-ssh-agent).

### Mac OS

- Use [Homebrew](https://brew.sh/) to install the following:
  - `brew install apache-arrow@13.0.0_5 bat@0.23.0 graphviz@8.1.0 openblas@0.3.24 pre-commit@3.3.3`
- Install Docker Desktop from [docker.com](https://www.docker.com/) (not Brew since it has a trickier upgrade story)

## Common commands

- `pdm lint`: Run pre-commit linters
- `pdm test`: Run test suite
- `pdm doc`: Start doc server
