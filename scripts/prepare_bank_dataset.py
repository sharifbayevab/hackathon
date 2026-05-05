"""Prepare Bank Marketing dataset for the leaderboard.

Downloads bank-full.csv from UCI, drops the `duration` data leak,
splits into train/test (stratified), then test -> public/private (stratified).

Outputs to Dataset/bank-marketing/:
  - train.csv             (participants get this)
  - test_features.csv     (participants get this)
  - groundtruth.csv       (admin uploads this)
  - sample_submission.csv (participants get this)
"""
from __future__ import annotations

import io
import urllib.request
import zipfile
from pathlib import Path

import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

UCI_URL = "https://archive.ics.uci.edu/static/public/222/bank+marketing.zip"
OUT_DIR = Path(__file__).resolve().parents[1] / "Dataset" / "bank-marketing"
SEED = 42
TEST_SIZE = 0.30           # 30% of all rows go to test
PRIVATE_SHARE = 0.50       # half of test -> private


def download_bank_full() -> pd.DataFrame:
    print(f"[download] {UCI_URL}")
    raw = urllib.request.urlopen(UCI_URL, timeout=60).read()
    with zipfile.ZipFile(io.BytesIO(raw)) as outer:
        with outer.open("bank.zip") as inner:
            with zipfile.ZipFile(io.BytesIO(inner.read())) as z:
                with z.open("bank-full.csv") as f:
                    return pd.read_csv(f, sep=";")


def baseline_auc(train: pd.DataFrame, gt: pd.DataFrame) -> dict[str, float]:
    """Quick LogReg baseline on numeric-only features as a sanity check."""
    num = train.select_dtypes(include=["number"]).columns.tolist()
    num = [c for c in num if c not in ("id", "y")]
    Xtr = train[num].fillna(0).values
    ytr = train["y"].values

    test_ids = gt["id"].values
    full_test = pd.read_csv(OUT_DIR / "test_features.csv")
    test_features = full_test.set_index("id").loc[test_ids].reset_index()
    Xte = test_features[num].fillna(0).values
    yte = gt["answer"].values

    scaler = StandardScaler()
    Xtr_s = scaler.fit_transform(Xtr)
    Xte_s = scaler.transform(Xte)

    model = LogisticRegression(max_iter=1000, class_weight="balanced")
    model.fit(Xtr_s, ytr)
    proba = model.predict_proba(Xte_s)[:, 1]

    pub = gt["split"] == "public"
    prv = gt["split"] == "private"
    return {
        "public_auc": roc_auc_score(yte[pub.values], proba[pub.values]),
        "private_auc": roc_auc_score(yte[prv.values], proba[prv.values]),
        "overall_auc": roc_auc_score(yte, proba),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    df = download_bank_full()
    print(f"[load] rows={len(df):,}  cols={list(df.columns)}")

    # Data leak: duration is known only AFTER the call -> drop it.
    df = df.drop(columns=["duration"])

    # Binary target as 0/1
    df["y"] = (df["y"].str.strip().str.lower() == "yes").astype(int)

    # Stable id (1..N)
    df = df.reset_index(drop=True)
    df.insert(0, "id", df.index + 1)

    # Stratified train/test split
    train, test = train_test_split(
        df, test_size=TEST_SIZE, stratify=df["y"], random_state=SEED, shuffle=True
    )
    # Stratified public/private split inside test
    public, private = train_test_split(
        test, test_size=PRIVATE_SHARE, stratify=test["y"], random_state=SEED, shuffle=True
    )

    train = train.sort_values("id").reset_index(drop=True)
    test = test.sort_values("id").reset_index(drop=True)

    # train.csv: id + features + y
    train_path = OUT_DIR / "train.csv"
    train.to_csv(train_path, index=False)

    # test_features.csv: id + features (NO y)
    test_features = test.drop(columns=["y"])
    test_features_path = OUT_DIR / "test_features.csv"
    test_features.to_csv(test_features_path, index=False)

    # groundtruth.csv: id, answer, split
    gt_pub = pd.DataFrame({"id": public["id"], "answer": public["y"], "split": "public"})
    gt_prv = pd.DataFrame({"id": private["id"], "answer": private["y"], "split": "private"})
    gt = pd.concat([gt_pub, gt_prv]).sort_values("id").reset_index(drop=True)
    gt_path = OUT_DIR / "groundtruth.csv"
    gt.to_csv(gt_path, index=False)

    # sample_submission.csv: id + answer=majority class (0)
    sample = pd.DataFrame({"id": test_features["id"], "answer": 0})
    sample_path = OUT_DIR / "sample_submission.csv"
    sample.to_csv(sample_path, index=False)

    # Stats
    print("\n=== files ===")
    for p in [train_path, test_features_path, gt_path, sample_path]:
        kb = p.stat().st_size / 1024
        print(f"  {p.relative_to(OUT_DIR.parents[1])}  ({kb:,.0f} KB)")

    print("\n=== row counts ===")
    print(f"  train:           {len(train):,}")
    print(f"  test (total):    {len(test):,}")
    print(f"  test public:     {len(public):,}")
    print(f"  test private:    {len(private):,}")

    print("\n=== class balance (% positive 'yes') ===")
    print(f"  train:           {train['y'].mean()*100:.2f}%")
    print(f"  test public:     {public['y'].mean()*100:.2f}%")
    print(f"  test private:    {private['y'].mean()*100:.2f}%")

    print("\n=== columns in train.csv ===")
    print(f"  {list(train.columns)}")

    print("\n=== baseline LogReg (numeric features only, class_weight=balanced) ===")
    aucs = baseline_auc(train, gt)
    print(f"  public  ROC-AUC: {aucs['public_auc']:.4f}")
    print(f"  private ROC-AUC: {aucs['private_auc']:.4f}")
    print(f"  overall ROC-AUC: {aucs['overall_auc']:.4f}")


if __name__ == "__main__":
    main()
