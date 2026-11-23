"""Проверки целостности данных, настроек и численных соглашений ЛР1."""

import json

import numpy as np
import pytest
from pydantic import ValidationError

import lab1
from check_staged import check_blob


@pytest.mark.parametrize("changed", [b"corrupted", None])
def test_raw_bytes_are_strictly_verified(changed):
    original = lab1.RAW.read_bytes()
    lab1.validate_bytes(original)
    # CRLF in an existing raw file is also a byte-level change.
    payload = changed if changed is not None else original.replace(b"\n", b"\r\n")
    with pytest.raises(ValueError, match="DATA_HASH_MISMATCH"):
        lab1.validate_bytes(payload)
    assert lab1.RAW.read_bytes() == original


def test_manifest_cannot_replace_pinned_hash(tmp_path):
    raw = tmp_path / "raw.csv"
    raw.write_bytes(lab1.RAW.read_bytes())
    manifest = tmp_path / "hash_manifest.json"
    value = json.loads((lab1.ROOT / "hash_manifest.json").read_text())
    manifest.write_text(json.dumps(value))
    assert lab1.verify_data(raw, manifest) == raw.read_bytes()
    value["files"][0]["sha256"] = "0" * 64
    manifest.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="MANIFEST_MISMATCH"):
        lab1.verify_data(raw, manifest)
    raw.write_bytes(raw.read_bytes() + b"X")
    with pytest.raises(ValueError, match="DATA_HASH_MISMATCH"):
        lab1.verify_data(raw, manifest)


@pytest.mark.parametrize(
    "override",
    [
        {"author": " "},
        {"variant": 24},
        {"seed": -1},
        {"bins": 1},
        {"test_fraction": 0},
        {"test_fraction": 0.6, "calibration_fraction": 0.4},
        {"unknown_option": True},
    ],
)
def test_invalid_config_is_rejected(override):
    with pytest.raises(ValidationError):
        lab1.Config(**({"author": "Саргсян Ален Артурович"} | override))


def test_ece_hand_calculation_includes_probability_one():
    table = lab1.calibration_bins([0, 1, 0, 1], [0.0, 0.2, 0.8, 1.0], bins=2)
    assert table["count"].tolist() == [2, 2]
    assert table["ece_contribution"].sum() == pytest.approx(0.4)
    sparse = lab1.calibration_bins([0, 1], [0.0, 1.0], bins=10)
    assert sparse["bin"].tolist() == [0, 9]
    assert sparse["count"].sum() == 2
    assert sparse["ece_contribution"].sum() == 0


@pytest.mark.parametrize("probability", [[-0.1], [1.1], [np.nan], [np.inf], []])
def test_invalid_probabilities_are_rejected(probability):
    with pytest.raises(ValueError):
        lab1.calibration_bins([1], probability, bins=10)


def test_splits_are_disjoint_exhaustive_and_repeatable():
    y = np.repeat([0, 1], [357, 212])
    config = lab1.load_config()
    first, second = lab1.split_indices(y, config), lab1.split_indices(y, config)
    assert [len(first[k]) for k in ("train", "calibration", "test")] == [341, 114, 114]
    joined = np.concatenate(list(first.values()))
    assert len(joined) == len(np.unique(joined)) == len(y)
    assert set(joined) == set(range(len(y)))
    for name in first:
        np.testing.assert_array_equal(first[name], second[name])
        assert set(y[first[name]]) == {0, 1}


@pytest.mark.parametrize("name,payload", [("x.py", b"if :"), ("x.json", b"{"), ("x.yml", b"x: [")])
def test_invalid_staged_syntax_is_blocked(name, payload):
    assert any("BLOCK_SYNTAX" in reason for reason in check_blob(name, payload))
