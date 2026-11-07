#!/bin/bash
# Robust wait: returns only when LUMI confirms none of the given job ids are queued/running (ssh errors = keep waiting).
JOBS="$1"
while true; do
  n=$(ssh -o BatchMode=yes -o ConnectTimeout=20 amojahid@lumi.csc.fi "squeue -h -j $JOBS 2>/dev/null | wc -l" 2>/dev/null) || n=err
  [ "$n" = "0" ] && break
  sleep 60
done
