"""ЛР1, вариант 25: проверка данных, EDA и иллюстрация калибровки."""

import argparse
import hashlib
import io
import json
import platform
import subprocess
import tempfile
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path
from typing import Literal
from urllib.request import urlopen

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import mlflow
import numpy as np
import pandas as pd
import seaborn as sns
import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sklearn.calibration import CalibratedClassifierCV
from sklearn.datasets import load_breast_cancer
from sklearn.frozen import FrozenEstimator
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits

ROOT = Path(__file__).resolve().parent
RAW = ROOT / "data/raw/breast_cancer.csv"
REPORT = ROOT / "reports/LAB1"
SOURCE = "https://raw.githubusercontent.com/scikit-learn/scikit-learn/1.8.0/sklearn/datasets/data/breast_cancer.csv"
EXPECTED_SHA256 = "fed3eb72d0575ef6192293f5093c6e801b1476b577d0386bf4455504522172ed"
EXPECTED_SIZE = 119913


class Config(BaseModel):
    model_config = ConfigDict(extra="forbid")
    author: str = Field(min_length=1)
    variant: Literal[25] = 25
    seed: int = Field(default=42, ge=0)
    bins: int = Field(default=10, ge=2, le=30)
    test_fraction: float = Field(default=0.2, gt=0, lt=1)
    calibration_fraction: float = Field(default=0.2, gt=0, lt=1)

    @model_validator(mode="after")
    def valid_split(self):
        if self.test_fraction + self.calibration_fraction >= 1:
            raise ValueError("Для обучения должна остаться непустая часть данных")
        if not self.author.strip():
            raise ValueError("Укажите автора")
        return self


def load_config(path=ROOT / "configs/lab1.yaml"):
    return Config.model_validate(yaml.safe_load(Path(path).read_text(encoding="utf-8")))


def save_json(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def validate_bytes(payload):
    digest = hashlib.sha256(payload).hexdigest()
    if digest != EXPECTED_SHA256 or len(payload) != EXPECTED_SIZE:
        raise ValueError(f"DATA_HASH_MISMATCH: SHA-256={digest}; размер={len(payload)}")


def prepare_data():
    if not RAW.exists():
        with urlopen(SOURCE, timeout=30) as response:
            payload = response.read()
        validate_bytes(payload)
        RAW.parent.mkdir(parents=True, exist_ok=True)
        RAW.write_bytes(payload)
    validate_bytes(RAW.read_bytes())
    manifest = {
        "source": SOURCE,
        "dataset": "Breast Cancer Wisconsin Diagnostic",
        "dataset_url": "https://doi.org/10.24432/C5DW2B",
        "license": "CC BY 4.0",
        "files": [
            {
                "path": "data/raw/breast_cancer.csv",
                "size_bytes": EXPECTED_SIZE,
                "sha256": EXPECTED_SHA256,
            }
        ],
    }
    save_json(ROOT / "hash_manifest.json", manifest)
    save_json(REPORT / "hash_manifest.json", manifest)
    print(f"PASS: исходные данные; {EXPECTED_SIZE} байт; SHA-256 {EXPECTED_SHA256}")


def verify_data(path=RAW, manifest=ROOT / "hash_manifest.json"):
    payload = Path(path).read_bytes()
    validate_bytes(payload)
    entries = json.loads(Path(manifest).read_text(encoding="utf-8")).get("files")
    expected = {
        "path": "data/raw/breast_cancer.csv",
        "size_bytes": EXPECTED_SIZE,
        "sha256": EXPECTED_SHA256,
    }
    if entries != [expected]:
        raise ValueError("MANIFEST_MISMATCH: манифест не соответствует закреплённому эталону")
    return payload


def split_indices(y, config):
    train_cal, test = train_test_split(
        np.arange(len(y)), test_size=config.test_fraction, stratify=y, random_state=config.seed
    )
    train, calibration = train_test_split(
        train_cal,
        test_size=config.calibration_fraction / (1 - config.test_fraction),
        stratify=y[train_cal],
        random_state=config.seed,
    )
    return {"train": train, "calibration": calibration, "test": test}


def calibration_bins(y, probability, bins):
    y, probability = np.asarray(y), np.asarray(probability)
    if len(y) != len(probability) or not len(y) or not np.isfinite(probability).all():
        raise ValueError("Пустые или несогласованные предсказания")
    if ((probability < 0) | (probability > 1)).any():
        raise ValueError("Вероятность должна принадлежать [0, 1]")
    indices = np.minimum((probability * bins).astype(int), bins - 1)
    rows = []
    for index in range(bins):
        mask = indices == index
        count = int(mask.sum())
        if count:
            mean, fraction = float(probability[mask].mean()), float(y[mask].mean())
            rows.append(
                {
                    "bin": index,
                    "count": count,
                    "mean_probability": mean,
                    "positive_fraction": fraction,
                    "ece_contribution": count / len(y) * abs(mean - fraction),
                }
            )
    return pd.DataFrame(rows)


def code_commit():
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, capture_output=True, check=False
    )
    return result.stdout.strip() if result.returncode == 0 else "unversioned"


def run_analysis(config, output=REPORT):
    """Один воспроизводимый EDA-прогон; модель нужна только для графика варианта."""
    payload = verify_data()
    output = Path(output)
    figures = output / "figures"
    figures.mkdir(parents=True, exist_ok=True)
    raw = pd.read_csv(io.BytesIO(payload), skiprows=1, header=None)
    x = raw.iloc[:, :30].copy()
    x.columns = load_breast_cancer().feature_names
    y = (raw.iloc[:, 30].to_numpy() == 0).astype(int)  # malignant — положительный класс
    q1, q3 = x.quantile(0.25), x.quantile(0.75)
    outliers = x.lt(q1 - 1.5 * (q3 - q1)) | x.gt(q3 + 1.5 * (q3 - q1))
    summary = {
        "rows": len(x),
        "features": x.shape[1],
        "missing_values": int(x.isna().sum().sum()),
        "duplicate_rows": int(raw.duplicated().sum()),
        "nonfinite_values": int((~np.isfinite(x.to_numpy())).sum()),
        "negative_values": int((x < 0).sum().sum()),
        "zero_values": int((x == 0).sum().sum()),
        "outlier_rows": int(outliers.any(axis=1).sum()),
        "outlier_cells": int(outliers.sum().sum()),
        "malignant": int(y.sum()),
        "benign": int((y == 0).sum()),
        "malignant_share": float(y.mean()),
    }
    correlations = x.corr()
    upper = correlations.where(np.triu(np.ones(correlations.shape), k=1).astype(bool)).stack()
    summary["maximum_abs_correlation"] = float(upper.abs().max())
    stats = x.describe().T
    stats["dtype"] = x.dtypes.astype(str)
    stats["missing"] = x.isna().sum()
    stats["outliers_iqr"] = outliers.sum()
    stats.to_csv(output / "feature_stats.csv", index_label="feature", float_format="%.12g")
    correlations.to_csv(output / "correlations.csv", index_label="feature", float_format="%.12g")
    split = split_indices(y, config)
    with threadpool_limits(limits=1):
        model = make_pipeline(
            StandardScaler(), LogisticRegression(C=1, max_iter=2000, random_state=config.seed)
        )
        model.fit(x.iloc[split["train"]], y[split["train"]])
        calibrated = CalibratedClassifierCV(FrozenEstimator(model), method="sigmoid")
        calibrated.fit(x.iloc[split["calibration"]], y[split["calibration"]])
        probabilities = {
            name: estimator.predict_proba(x.iloc[split["test"]])[:, 1]
            for name, estimator in [("logreg", model), ("sigmoid", calibrated)]
        }
    tables, metrics = {}, {}
    for name, probability in probabilities.items():
        tables[name] = calibration_bins(y[split["test"]], probability, config.bins)
        metrics[name] = {
            "brier": float(brier_score_loss(y[split["test"]], probability)),
            "ece": float(tables[name]["ece_contribution"].sum()),
        }
    pd.concat(tables, names=["model", "row"]).reset_index().drop(columns="row").to_csv(
        output / "calibration_bins.csv", index=False, float_format="%.12g"
    )
    all_stats = {
        **summary,
        **{f"split_{k}": len(v) for k, v in split.items()},
        **{f"{m}_{k}": v for m, values in metrics.items() for k, v in values.items()},
    }
    pd.DataFrame(all_stats.items(), columns=["metric", "value"]).to_csv(
        output / "eda_stats.csv", index=False, float_format="%.12g"
    )
    sns.set_theme(style="whitegrid", font_scale=0.9)
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.bar(["benign", "malignant"], [summary["benign"], summary["malignant"]])
    ax.set(
        ylabel="Count",
        title=f"Classes: benign={summary['benign']}, malignant={summary['malignant']}",
    )
    fig.tight_layout()
    fig.savefig(figures / "class_balance.png", dpi=150)
    plt.close(fig)
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    for ax, column in zip(axes, ["mean radius", "mean area"]):
        sns.histplot(
            x=x[column], hue=np.where(y, "malignant", "benign"), bins=20, element="step", ax=ax
        )
        ax.set_title(column)
    fig.tight_layout()
    fig.savefig(figures / "distributions.png", dpi=150)
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(11, 9))
    sns.heatmap(correlations, cmap="coolwarm", vmin=-1, vmax=1, center=0, ax=ax)
    ax.set_title(f"Pearson correlations; max |r| = {summary['maximum_abs_correlation']:.4f}")
    fig.tight_layout()
    fig.savefig(figures / "correlations.png", dpi=150)
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.plot([0, 1], [0, 1], "--", color="gray", label="Perfect calibration")
    for name, table in tables.items():
        ax.plot(
            table.mean_probability,
            table.positive_fraction,
            "o-",
            label=f"{name}: Brier={metrics[name]['brier']:.4f}, ECE={metrics[name]['ece']:.4f}",
        )
        for row in table.itertuples():
            ax.annotate(
                str(row.count),
                (row.mean_probability, row.positive_fraction),
                xytext=(-5, 7) if name == "logreg" else (4, -12),
                textcoords="offset points",
                fontsize=7,
            )
    ax.set(
        xlabel="Mean predicted P(malignant)",
        ylabel="Observed malignant fraction",
        title=f"Calibration: test n={len(split['test'])}, bins={config.bins}",
        xlim=(0, 1),
        ylim=(0, 1.05),
    )
    ax.legend(loc="lower right", fontsize=8)
    fig.tight_layout()
    fig.savefig(figures / "calibration.png", dpi=150)
    plt.close(fig)
    mlflow.set_tracking_uri((ROOT / "mlruns").as_uri())
    mlflow.set_experiment("lab1_variant25")
    with mlflow.start_run(run_name="eda_calibration") as run:
        result = {
            "author": config.author,
            "variant": 25,
            "lab": 1,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "git_commit": code_commit(),
            "data_sha256": EXPECTED_SHA256,
            "run_id": run.info.run_id,
            "config": config.model_dump(),
            "summary": summary,
            "metrics": metrics,
            "split_indices": {k: v.tolist() for k, v in split.items()},
        }
        save_json(output / "results.json", result)
        mlflow.log_params(
            {
                **config.model_dump(),
                "data_sha256": EXPECTED_SHA256,
                "git_commit": result["git_commit"],
            }
        )
        mlflow.log_metrics(
            {f"{m}_{k}": v for m, values in metrics.items() for k, v in values.items()}
        )
        for path in sorted(output.glob("*.csv")):
            mlflow.log_artifact(str(path), artifact_path="tables")
        mlflow.log_artifact(str(output / "results.json"))
        mlflow.log_artifacts(str(figures), artifact_path="figures")
    save_json(
        output / "run_environment.json",
        {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "run_id": result["run_id"],
            "versions": {
                name: version(name)
                for name in [
                    "numpy",
                    "pandas",
                    "scikit-learn",
                    "scipy",
                    "matplotlib",
                    "seaborn",
                    "pydantic",
                    "PyYAML",
                    "mlflow-skinny",
                    "joblib",
                    "threadpoolctl",
                ]
            },
        },
    )
    print(f"PASS: EDA; {summary['rows']} строк, {summary['features']} признаков")
    print(f"Автор: {config.author}; вариант 25; seed={config.seed}")
    print(f"MLflow run_id: {result['run_id']}; commit: {result['git_commit']}")
    for name, values in metrics.items():
        print(f"{name}: Brier={values['brier']:.8f}; ECE={values['ece']:.8f}")
    print(f"Сводки и графики: {output}")
    return result


def tamper_control():
    original = verify_data()
    altered = bytearray(original)
    altered[30] ^= 1
    with tempfile.TemporaryDirectory() as folder:
        copy = Path(folder) / "changed.csv"
        copy.write_bytes(altered)
        try:
            verify_data(copy)
        except ValueError as error:
            rejected, reason = True, str(error)
        else:
            rejected, reason = False, "Повреждение не обнаружено"
    result = {
        "rejected": rejected,
        "original_unchanged": RAW.read_bytes() == original,
        "original_sha256": EXPECTED_SHA256,
        "changed_sha256": hashlib.sha256(altered).hexdigest(),
        "reason": reason,
    }
    save_json(REPORT / "hash_tamper.json", result)
    log = f"Изменён один байт временной копии.\n{reason}\nОригинал сохранён: {result['original_unchanged']}\n"
    (REPORT / "hash_tamper.log").write_text(log, encoding="utf-8")
    if not (rejected and result["original_unchanged"]):
        raise RuntimeError("Негативный контроль не пройден")
    print("PASS: подмена обнаружена; исходный файл не изменён")
    print(log)
    return result


def reproduce(config):
    with tempfile.TemporaryDirectory() as folder:
        left, right = Path(folder) / "first", Path(folder) / "second"
        first, second = run_analysis(config, left), run_analysis(config, right)
        files = ["eda_stats.csv", "feature_stats.csv", "correlations.csv", "calibration_bins.csv"]
        checks = {name: (left / name).read_bytes() == (right / name).read_bytes() for name in files}
    difference = max(
        abs(first["metrics"][m][k] - second["metrics"][m][k])
        for m in first["metrics"]
        for k in first["metrics"][m]
    )
    result = {
        "first_run_id": first["run_id"],
        "second_run_id": second["run_id"],
        "files_equal": checks,
        "max_metric_difference": difference,
        "passed": all(checks.values()) and difference == 0,
        "scope": "Two runs in the same environment; one BLAS thread; timestamps/PNG excluded",
    }
    save_json(REPORT / "reproducibility.json", result)
    log = "\n".join(f"{name}: {'PASS' if ok else 'FAIL'}" for name, ok in checks.items())
    log += f"\nmax metric difference: {difference}\nMLflow: {first['run_id']}, {second['run_id']}\n"
    (REPORT / "reproducibility.log").write_text(log, encoding="utf-8")
    if not result["passed"]:
        raise RuntimeError("Повторный прогон отличается")
    print("PASS: повторяемость\n" + log)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["prepare", "verify", "run", "tamper", "reproduce"])
    args = parser.parse_args()
    try:
        config = load_config()
        if args.command == "prepare":
            prepare_data()
        elif args.command == "verify":
            verify_data()
            print(f"PASS: SHA-256 {EXPECTED_SHA256}; {EXPECTED_SIZE} байт")
        elif args.command == "run":
            run_analysis(config)
        elif args.command == "tamper":
            tamper_control()
        else:
            reproduce(config)
        return 0
    except (ValueError, OSError, RuntimeError) as error:
        print(f"ОШИБКА: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
