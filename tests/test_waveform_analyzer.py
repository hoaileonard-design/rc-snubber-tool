import math
import os

import numpy as np
import pytest

from app.core.waveform_analyzer import WaveformAnalyzer
from app.utils.errors import WaveformFileError, InsufficientDataError

SAMPLE_DIR = os.path.join(os.path.dirname(__file__), "sample_data")


def _write_file(tmp_path, name, lines):
    path = tmp_path / name
    path.write_text("\n".join(lines), encoding="utf-8")
    return str(path)


def test_load_file_missing_raises(tmp_path):
    with pytest.raises(WaveformFileError):
        WaveformAnalyzer.load_file(str(tmp_path / "does_not_exist.csv"))


def test_load_file_empty_raises(tmp_path):
    path = tmp_path / "empty.csv"
    path.write_text("", encoding="utf-8")
    with pytest.raises(WaveformFileError):
        WaveformAnalyzer.load_file(str(path))


def test_load_file_comma_with_header(tmp_path):
    lines = ["time,V(vds)"] + [f"{i * 1e-9},{24 + i}" for i in range(20)]
    path = _write_file(tmp_path, "comma.csv", lines)
    t, v = WaveformAnalyzer.load_file(path)
    assert len(t) == 20
    assert math.isclose(v[0], 24.0)


def test_load_file_tab_with_header(tmp_path):
    lines = ["time\tV(vds)"] + [f"{i * 1e-9}\t{24 + i}" for i in range(20)]
    path = _write_file(tmp_path, "tab.txt", lines)
    t, v = WaveformAnalyzer.load_file(path)
    assert len(t) == 20


def test_load_file_malformed_raises(tmp_path):
    lines = ["not,numeric,data"] * 15
    path = _write_file(tmp_path, "bad.csv", lines)
    with pytest.raises((WaveformFileError, InsufficientDataError)):
        WaveformAnalyzer.load_file(path)


def test_load_file_insufficient_points_raises(tmp_path):
    lines = ["time,V(vds)"] + [f"{i * 1e-9},{24 + i}" for i in range(5)]
    path = _write_file(tmp_path, "short.csv", lines)
    with pytest.raises(InsufficientDataError):
        WaveformAnalyzer.load_file(path)


def test_analyze_synthetic_damped_sinusoid_matches_theory():
    """Sinh song damped sinusoid (co doan phang truoc thoi diem chuyen mach, giong du
    lieu LTspice thuc te) biet truoc alpha, omega_d, Vin va kiem tra WaveformAnalyzer
    trich xuat duoc cac gia tri gan dung ly thuyet."""
    Vin = 24.0
    v0_overshoot = 70.0
    alpha = 2e6
    omega_d = 2 * np.pi * 15e6
    pre_time = 0.3e-6
    duration = 2.3e-6
    n_points = 3000

    t = np.linspace(0, duration, n_points)
    tau = np.clip(t - pre_time, 0, None)
    ringing = Vin + (v0_overshoot - Vin) * np.exp(-alpha * tau) * np.cos(omega_d * tau)
    v = np.where(t < pre_time, 0.0, ringing)

    metrics = WaveformAnalyzer.analyze(t, v)

    theoretical_f_ring = omega_d / (2 * np.pi)
    assert math.isclose(metrics.f_ring, theoretical_f_ring, rel_tol=0.1)
    assert math.isclose(metrics.v_peak, v0_overshoot, rel_tol=0.05)
    expected_os = (v0_overshoot - Vin) / Vin * 100.0
    assert math.isclose(metrics.percent_overshoot, expected_os, rel_tol=0.1)


def test_analyze_insufficient_points_after_transition_raises():
    t = np.array([0.0, 1e-9])
    v = np.array([0.0, 24.0])
    with pytest.raises(InsufficientDataError):
        WaveformAnalyzer.analyze(t, v)
