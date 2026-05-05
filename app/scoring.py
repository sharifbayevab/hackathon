from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    log_loss,
    mean_absolute_error,
    mean_squared_error,
    r2_score,
    roc_auc_score,
)

from app.models import HIGHER_IS_BETTER, Metric

SPLIT_COLUMN = "split"
SPLIT_PUBLIC = "public"
SPLIT_PRIVATE = "private"


class ScoringError(ValueError):
    pass


@dataclass
class ScoreResult:
    public: float
    private: float


def _compute(metric: Metric, y_true: np.ndarray, y_pred: np.ndarray) -> float:
    if metric == Metric.accuracy:
        return float(accuracy_score(y_true, np.round(y_pred).astype(int)))
    if metric == Metric.f1_macro:
        return float(f1_score(y_true, np.round(y_pred).astype(int), average="macro"))
    if metric == Metric.f1_binary:
        return float(f1_score(y_true.astype(int), np.round(y_pred).astype(int), average="binary"))
    if metric == Metric.roc_auc:
        return float(roc_auc_score(y_true.astype(int), y_pred))
    if metric == Metric.log_loss:
        clipped = np.clip(y_pred, 1e-15, 1 - 1e-15)
        return float(log_loss(y_true.astype(int), clipped))
    if metric == Metric.mae:
        return float(mean_absolute_error(y_true, y_pred))
    if metric == Metric.rmse:
        return float(np.sqrt(mean_squared_error(y_true, y_pred)))
    if metric == Metric.r2:
        return float(r2_score(y_true, y_pred))
    raise ScoringError(f"Unsupported metric: {metric}")


def is_higher_better(metric: Metric) -> bool:
    return HIGHER_IS_BETTER[metric]


def load_groundtruth(path: Path, id_col: str, answer_col: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    required = {id_col, answer_col, SPLIT_COLUMN}
    missing = required - set(df.columns)
    if missing:
        raise ScoringError(
            f"Groundtruth must contain columns: {sorted(required)}. Missing: {sorted(missing)}"
        )
    if not df[SPLIT_COLUMN].isin({SPLIT_PUBLIC, SPLIT_PRIVATE}).all():
        raise ScoringError(
            f"Column '{SPLIT_COLUMN}' must contain only '{SPLIT_PUBLIC}' or '{SPLIT_PRIVATE}'"
        )
    if df[id_col].duplicated().any():
        raise ScoringError(f"Duplicate ids in groundtruth column '{id_col}'")
    return df


def score_submission(
    submission_path: Path,
    groundtruth: pd.DataFrame,
    metric: Metric,
    id_col: str,
    answer_col: str,
) -> ScoreResult:
    try:
        sub = pd.read_csv(submission_path)
    except Exception as e:
        raise ScoringError(f"Could not read CSV: {e}")

    if id_col not in sub.columns or answer_col not in sub.columns:
        raise ScoringError(f"Submission must have columns '{id_col}' and '{answer_col}'")

    sub = sub[[id_col, answer_col]].copy()
    if sub[id_col].duplicated().any():
        raise ScoringError(f"Duplicate ids in submission column '{id_col}'")

    merged = groundtruth.merge(sub, on=id_col, how="left", suffixes=("_true", "_pred"))
    pred_col = f"{answer_col}_pred"
    true_col = f"{answer_col}_true"
    if merged[pred_col].isna().any():
        missing = merged.loc[merged[pred_col].isna(), id_col].head(5).tolist()
        raise ScoringError(f"Missing predictions for ids (showing up to 5): {missing}")

    try:
        y_pred = pd.to_numeric(merged[pred_col]).to_numpy()
        y_true = pd.to_numeric(merged[true_col]).to_numpy()
    except Exception as e:
        raise ScoringError(f"Could not coerce values to numeric: {e}")

    public_mask = merged[SPLIT_COLUMN] == SPLIT_PUBLIC
    private_mask = merged[SPLIT_COLUMN] == SPLIT_PRIVATE
    if not public_mask.any() or not private_mask.any():
        raise ScoringError("Groundtruth must contain both public and private rows")

    public = _compute(metric, y_true[public_mask.values], y_pred[public_mask.values])
    private = _compute(metric, y_true[private_mask.values], y_pred[private_mask.values])
    return ScoreResult(public=public, private=private)
