#!/usr/bin/env bash
set -Eeuo pipefail

readonly INSTALL_DIR="${NIRJ_AGENT_INSTALL_DIR:-/opt/nirj-agent}"
readonly REPO_DIR="${INSTALL_DIR}/source"
readonly VENV_DIR="${INSTALL_DIR}/venv"
readonly BRANCH="${NIRJ_AGENT_BRANCH:-main}"

export GIT_TERMINAL_PROMPT=0
export PIP_DISABLE_PIP_VERSION_CHECK=1

git -C "${REPO_DIR}" pull --ff-only origin "${BRANCH}"

"${VENV_DIR}/bin/python" -m pip install \
    --upgrade \
    "${REPO_DIR}"

exec "${VENV_DIR}/bin/nirj-agent" up
