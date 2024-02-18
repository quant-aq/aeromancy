# Installing and setting up Aeromancy

The easiest way to setup Aeromancy is to follow the [Quick
Start](quick_start.md) guide. This document includes additional setup
instructions for running Aeromany in "production" mode.

- **Python**: Aeromancy works with Python 3.10.5 or higher
- **Python package manager**: Aeromancy currently requires [`pdm`](https://pdm.fming.dev).

    - Install via `pip install --user pdm`

- **Environment variables**:

    - To use an S3-compatible backend (e.g.,
      [Ceph](https://github.com/ceph/ceph)), you'll need to set these
      environmental variables:

        - `AEROMANCY_AWS_ACCESS_KEY_ID`
        - `AEROMANCY_AWS_SECRET_ACCESS_KEY`
        - `AEROMANCY_AWS_S3_ENDPOINT_URL`
        - `AEROMANCY_AWS_REGION` (can be left empty if it doesn't apply)

    - You'll also need to set `WANDB_API_KEY` (from [Weights and Biases](https://wandb.ai))

- **SSH Authentication**: You'll want `ssh-agent` setup if you need to access
  private GitHub repositories. Check out these
  [instructions](https://docs.github.com/en/authentication/connecting-to-github-with-ssh/generating-a-new-ssh-key-and-adding-it-to-the-ssh-agent).

## Linux

You'll want to install some packages. On Debian, you can use:

- `apt install bat graphviz libopenblas-dev pre-commit docker.io`

## Mac OS

- We recommend using [Homebrew](https://brew.sh/) to install the following:
    - `brew install apache-arrow@13.0.0_5 bat@0.23.0 graphviz@8.1.0
       openblas@0.3.24 pre-commit@3.3.3`
- Install Docker Desktop from [docker.com](https://www.docker.com/) (not Brew
  since it has a trickier upgrade story)
