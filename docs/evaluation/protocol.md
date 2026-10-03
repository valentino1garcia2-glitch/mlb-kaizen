# Evaluation protocol

## Purpose

Provide one reproducible evaluation path for the baseline and ML challenger without turning the
analysis tool into a black box.

## Dataset contract

Each historical row contains:

- game identity and official date;
- prediction timestamp;
- feature timestamp;
- model features known at prediction time;
- final home and away runs.

The invariant is:

`feature_timestamp <= prediction_timestamp`

Rows are sorted chronologically by `prediction_timestamp` and then `game_id`.

## Walk-forward

Use an expanding training window. For each fold, fit only on rows strictly earlier than the test
block. Never shuffle historical rows across the temporal boundary.

## Metrics

Report at minimum:

- home-run MAE;
- away-run MAE;
- total-run RMSE;
- Brier score for home-win probability;
- log loss;
- prediction accuracy as a descriptive metric;
- temporal calibration when requested.

## Calibration

Fit a calibrator on earlier probability/outcome observations and evaluate it on a later block.
Never fit calibration parameters on the same outcomes used to claim final out-of-sample performance.

## ML challenger

The Random Forest is a challenger, not an assumed improvement. Keep the transparent baseline as the
reference. Retain the ML model only if future real historical evaluation demonstrates reproducible
out-of-sample improvement without unacceptable calibration deterioration.

## Evidence labels

`ENGINEERING_READY` means the pipeline executes and its tests pass.

`EMPIRICALLY_VALIDATED` requires a real historical dataset with trustworthy timestamps and a completed
walk-forward evaluation. Synthetic fixtures are for smoke tests only and must never be reported as
real model performance.
