#!/bin/bash
#SBATCH --account=project_462001520
#SBATCH --partition=small
#SBATCH --cpus-per-task=16
#SBATCH --mem=12G
#SBATCH --time=02:00:00
#SBATCH --job-name=te-submit
#SBATCH --output=lumi/logs/submit_%j.out
# Official val (score.py) + test (validator) for a spec file. Submit from ~/te:
#   sbatch --export=ALL,SPECFILE=lumi/cal_int4.json,TAG=cal_int4 lumi/submit.sbatch
module load cray-python
source "$HOME/te/.venv-lumi/bin/activate"
cd "$HOME/te"
export OMP_NUM_THREADS=$SLURM_CPUS_PER_TASK OPENBLAS_NUM_THREADS=$SLURM_CPUS_PER_TASK
for MODE in val test; do
  python -W ignore -m experiments.lab.submit --mode $MODE --tag "$TAG" --spec-file "$SPECFILE"
done
