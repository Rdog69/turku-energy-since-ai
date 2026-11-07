#!/bin/bash
# Run ON LUMI (login node), once: Python env in the PRIVATE home dir + prebuilt lab caches.
set -euo pipefail
cd "$HOME/te"
chmod 700 "$HOME/te"                       # licensed spot data: keep it private (not in shared project scratch)
module load cray-python
[ -d .venv-lumi ] || python3 -m venv .venv-lumi
source .venv-lumi/bin/activate
pip install -q --upgrade pip
pip install -q "pandas>=2.2" numpy pyarrow scikit-learn lightgbm scipy
python -c "import pandas, sklearn, lightgbm; print('env ok', pandas.__version__, sklearn.__version__, lightgbm.__version__)"
mkdir -p lumi/logs lumi/results
OMP_NUM_THREADS=4 python -W ignore -c "from experiments.lab.data import build_base, Data; b=build_base(); Data()['pkg']; print('caches ok', b.shape)"
