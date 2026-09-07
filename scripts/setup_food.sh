#!/usr/bin/env bash
set -euo pipefail
project_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd "$project_root"
mkdir -p .cache/tmp .cache/pip .cache/xdg .conda/envs .conda/pkgs
export CONDA_NO_PLUGINS=true
export CONDA_REGISTER_ENVS=false
export CONDA_ENVS_DIRS="$project_root/.conda/envs"
export CONDA_PKGS_DIRS="$project_root/.conda/pkgs"
export CONDA_NUMBER_CHANNEL_NOTICES=0
export XDG_CACHE_HOME="$project_root/.cache/xdg"
export TMPDIR="$project_root/.cache/tmp"
export PIP_CACHE_DIR="$project_root/.cache/pip"
food_python="$project_root/.conda/envs/food/bin/python"
if [[ ! -x "$food_python" ]]; then
  conda create --solver classic --prefix "$project_root/.conda/envs/food" python=3.12 pip --no-default-packages -y -q
fi
"$food_python" -c 'import sys; assert sys.version_info[:2] == (3, 12), "food requires Python 3.12"'
"$food_python" -m pip install --disable-pip-version-check -r requirements-dev.lock
"$food_python" -m pip install --disable-pip-version-check --no-deps --no-build-isolation -e .
printf 'Ready: conda activate %s/.conda/envs/food\n' "$project_root"
