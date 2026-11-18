#!/bin/sh
# Reproduce every result: dataset -> models -> simulation log -> diagrams
set -e
cd "$(dirname "$0")"
python3 generate_dataset.py
python3 train_evaluate.py
python3 simulate_pipeline.py
python3 make_diagrams.py
