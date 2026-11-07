#!/bin/bash
#SBATCH --account=project_462001520
#SBATCH --partition=small
#SBATCH --cpus-per-task=8
#SBATCH --mem=16G
#SBATCH --time=03:00:00
#SBATCH --job-name=te-hist
#SBATCH --output=lumi/logs/%A_%a.out
# History-mode queue on LUMI, one queue job per array task (see experiments/lab/queue.py):
#   sbatch --array=0-$((N-1))%40 --export=ALL,QUEUE=lumi/queue_lumi.jsonl lumi/hist.sbatch
module load cray-python
source "$HOME/te/.venv-lumi/bin/activate"
cd "$HOME/te"
export OMP_NUM_THREADS=$SLURM_CPUS_PER_TASK OPENBLAS_NUM_THREADS=$SLURM_CPUS_PER_TASK LAB_HISTORY=1
export LAB_BOARD="$HOME/te/lumi/results/hboard_${SLURM_ARRAY_JOB_ID}_${SLURM_ARRAY_TASK_ID}.csv"
python -W ignore -m experiments.lab.queue "${QUEUE:-lumi/queue_lumi.jsonl}" --one "$SLURM_ARRAY_TASK_ID"
