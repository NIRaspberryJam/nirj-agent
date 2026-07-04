#!/usr/bin/env bash
set -Eeuo pipefail

readonly INSTALL_DIR="${NIRJ_AGENT_INSTALL_DIR:-/data/nirj}"
readonly REPO_DIR="${INSTALL_DIR}/agent-repo"
readonly VENV_DIR="${INSTALL_DIR}/agent-venv"
readonly BRANCH="${NIRJ_AGENT_BRANCH:-main}"

export GIT_TERMINAL_PROMPT=0
export PIP_DISABLE_PIP_VERSION_CHECK=1

git -C "${REPO_DIR}" fetch origin "${BRANCH}"
git -C "${REPO_DIR}" checkout "${BRANCH}"
git -C "${REPO_DIR}" merge --ff-only "origin/${BRANCH}"

install -d -m 0755 /usr/share/nirj-agent
install -m 0644 \
    "${REPO_DIR}/assets/background-base.png" \
    /usr/share/nirj-agent/background-base.png

"${VENV_DIR}/bin/python" -m pip install \
    --upgrade \
    "${REPO_DIR}"

set +e
"${VENV_DIR}/bin/nirj-agent" boot-prep
boot_prep_status=$?
set -e

if [[ "${boot_prep_status}" -eq 194 ]]; then
    exit 0
fi

if [[ "${boot_prep_status}" -ne 0 ]]; then
    exit "${boot_prep_status}"
fi

exec "${VENV_DIR}/bin/nirj-agent" up
