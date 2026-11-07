#!/bin/bash
#SBATCH --account=project_462001520
#SBATCH --partition=small
#SBATCH --cpus-per-task=8
#SBATCH --mem=4G
#SBATCH --time=01:30:00
#SBATCH --job-name=te-grid
#SBATCH --output=lumi/logs/%A_%a.out
# Submit from ~/te:  sbatch --array=0-$(($(wc -l < lumi/specs.jsonl)-1))%15 --export=ALL,SPECS=lumi/specs.jsonl lumi/grid.sbatch
module load cray-python
source "$HOME/te/.venv-lumi/bin/activate"
cd "$HOME/te"
export OMP_NUM_THREADS=$SLURM_CPUS_PER_TASK OPENBLAS_NUM_THREADS=$SLURM_CPUS_PER_TASK
export LAB_BOARD="$HOME/te/lumi/results/board_${SLURM_ARRAY_JOB_ID}_${SLURM_ARRAY_TASK_ID}.csv"
SPEC=$(sed -n "$((SLURM_ARRAY_TASK_ID+1))p" "${SPECS:-lumi/specs.jsonl}")
echo "task $SLURM_ARRAY_TASK_ID on $(hostname): $SPEC"
python -W ignore -m experiments.lab.combo "$SPEC"
