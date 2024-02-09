# Aeromancy Docker
# This creates an image for running Aeromancy tasks, used by runner.py.
# See Aeromancy scaffolding docs for an overview of how this fits together.

# This Python version must match a version required by pyproject.toml.
FROM python:3.10.5-bullseye
# To set this in Aeromancy, pass --extra-debian-package to `pdm go`.
ARG EXTRA_DEBIAN_PACKAGES=""

RUN mkdir /base
WORKDIR /base

RUN apt update
RUN apt install --yes graphviz ${EXTRA_DEBIAN_PACKAGES}
# Store a list of all installed packages. Aeromancy will include this as
# metadata for each task.
RUN dpkg-query -f '${binary:Package}=${Version}\n' -W > /base/packages_list.txt

# Set up Python environment with pdm.
RUN pip3 install pdm

# pdm needs to see README.md and src/ (can be empty) to validate the project.
COPY --from=project pyproject.toml pdm.lock README.md /base/
RUN mkdir /base/src

# To access private repos on GitHub, we need to add it as a known host.
RUN mkdir -p -m 0700 ~/.ssh && ssh-keyscan github.com >> ~/.ssh/known_hosts

# --mount=type=ssh allows us to use forwarded SSH authentication.
# --no-self since we haven't copied our project-specific code here yet (we do
# that last since it's the most variable step and should help keep image build
# time low during development).
RUN --mount=type=ssh pdm install --prod --no-self

# Include Python code.
# Note that `project` must be mapped as a build context:
# https://docs.docker.com/engine/reference/commandline/buildx_build/#build-context
COPY --from=project ./src/ /base/src/
