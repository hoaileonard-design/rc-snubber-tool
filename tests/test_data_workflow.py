"""Hồi quy lỗi P6 và kiểm tra chọn theo dữ liệu, không chứng nhận phần cứng."""

import math
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from app.core.waveform_analyzer import WaveformAnalyzer as W
from app.core.sweep_data import SweepDataset
from app.utils.errors import AppError
from app.utils.validation import parse_float, parse_int_positive

EXAMPLES = Path(__file__).resolve().parents[1] / "examples" / "p6_buck"


def test_p6_first_peak_frequency_and_unsettled():
    t, v = W.load_file(str(EXAMPLES / "before.csv"))
    result = W.analyze(t, v, plateau=24.55164337158203)
    assert result.v_peak == pytest.approx(38.843482971191406)
    assert result.t_transition < result.t_peak
    assert result.f_ring == pytest.approx(30.390788586898726e6, rel=0.002)
    assert result.zeta == pytest.approx(0.00135717897895, rel=0.02)
    assert result.settling_censored and math.isnan(result.settling_time)


def test_p6_two_waveforms_identify_actual_parasitics():
    a = W.analyze(*W.load_file(str(EXAMPLES / "before.csv")), plateau=24.55164337158203)
    b = W.analyze(*W.load_file(str(EXAMPLES / "with_470pF.csv")), plateau=24.5384521484375)
    identified = W.identify_parasitics(a, b, 470e-12)
    assert identified.Lp_H == pytest.approx(100.1205056312364e-9, rel=0.002)
    assert identified.Cp_F == pytest.approx(273.9260217587687e-12, rel=0.002)
    with pytest.raises(AppError):
        W.identify_parasitics(b, a, 470e-12)


def test_monotonic_edge_does_not_invent_ringing_frequency():
    t = np.linspace(0, 3e-6, 3000)
    v = 24 * (1 - np.exp(-t / 40e-9))
    result = W.analyze(t, v)
    assert math.isnan(result.f_ring) and math.isnan(result.zeta)
    assert not result.settling_censored


@pytest.mark.parametrize("bad_time", [np.zeros(20), np.r_[np.arange(19), 5], np.r_[np.arange(19), np.inf]])
def test_invalid_time_rejected(bad_time):
    with pytest.raises(AppError):
        W.analyze(bad_time, np.arange(20))


def test_short_hold_in_band_is_censored():
    t = np.linspace(0, 300e-9, 300)
    v = 24 * (1 - np.exp(-t / 10e-9))
    result = W.analyze(t, v, plateau=24, settling_hold=500e-9)
    assert result.settling_censored


@pytest.mark.parametrize("plateau", [12, 200, 600])
def test_identification_independent_of_buck_parameters(plateau):
    # Đối chứng phương trình độc lập, không phải mô phỏng Flyback/phần cứng.
    lp, cp, added, zeta = 680e-9, 560e-12, 1500e-12, .04
    t = np.linspace(0, 5e-6, 16000)
    tau = np.clip(t - 200e-9, 0, None)
    metrics = []
    for capacitance in (cp, cp + added):
        omega0 = 1 / np.sqrt(lp * capacitance)
        wave = plateau + .4 * plateau * np.exp(-zeta * omega0 * tau) * np.cos(omega0 * np.sqrt(1 - zeta**2) * tau)
        wave[t < 200e-9] = 0
        metrics.append(W.analyze(t, wave, plateau=plateau))
    identified = W.identify_parasitics(*metrics, added)
    assert identified.Cp_F == pytest.approx(cp, rel=.01)
    assert identified.Lp_H == pytest.approx(lp, rel=.01)
    assert metrics[0].zeta == pytest.approx(zeta, rel=.02)


def _dataset(tmp_path, rows):
    frame = pd.DataFrame(rows)
    path = tmp_path / "sweep.csv"
    frame.to_csv(path, index=False)
    return SweepDataset.load(path)


def _rows():
    return [dict(R_ohm=10, C_F=1e-9, VDS_MAX_V=27, ts_ns=500, ts_censored=False,
                 P_snubber_W=.01, cost_vnd=10, area_mm2=1),
            dict(R_ohm=20, C_F=2e-9, VDS_MAX_V=26, ts_ns=100, ts_censored=False,
                 P_snubber_W=.04, cost_vnd=200, area_mm2=4),
            dict(R_ohm=30, C_F=3e-9, VDS_MAX_V=27, ts_ns=150, ts_censored=False,
                 P_snubber_W=.06, cost_vnd=100, area_mm2=3)]


def test_ts_constraint_weights_and_pareto(tmp_path):
    data = _dataset(tmp_path, _rows())
    power = data.select(28, 200, (1, 0, 0))
    cost = data.select(28, 200, (0, 1, 0))
    assert power.R_opt == 20 and cost.R_opt == 30
    assert power.n_feasible == 2 and power.pareto_mask.sum() == 2
    assert power.n_total == 3  # mẫu số là điểm đã chạy, không đếm sáu ô trống
    assert power.R_grid.size == 9 and np.isfinite(power.V_peak_grid).sum() == 3


def test_censored_and_missing_cells_not_feasible(tmp_path):
    rows = _rows()
    rows[1].update(ts_censored=True, ts_ns=float("nan"))
    data = _dataset(tmp_path, rows)
    result = data.select(28, 200)
    assert result.R_opt == 30 and result.n_feasible == 1


def test_mixed_topologies_and_duplicate_pairs_rejected(tmp_path):
    rows = _rows()
    rows[0]["topology"], rows[1]["topology"], rows[2]["topology"] = "Buck", "Flyback", "Buck"
    with pytest.raises(AppError):
        _dataset(tmp_path, rows)
    with pytest.raises(AppError):
        _dataset(tmp_path, [_rows()[0], _rows()[0]])


@pytest.mark.parametrize("weights", [(0, 0, 0), (-1, 1, 1), (float("nan"), 1, 1)])
def test_bad_weights_rejected(tmp_path, weights):
    with pytest.raises(AppError):
        _dataset(tmp_path, _rows()).select(28, 200, weights)


def test_rcd_needs_cost_of_diode_and_exports_source(tmp_path):
    rows = _rows()
    for row in rows:
        row["kind"] = "RCD"
    data = _dataset(tmp_path, rows)
    result = data.select(28, 200)
    md, csv = data.export(tmp_path / "result.md", result,
                          dict(v_target=28, ts_max_ns=200, weights=(1, 1, 1), p_max_w=None),
                          "Flyback synthetic test; not measured", "drain-source")
    assert data.sha256 in md.read_text(encoding="utf-8")
    assert pd.read_csv(csv).selected.sum() == 1
    with pytest.raises(AppError):
        data.export(tmp_path / "sweep.md", result, {}, "test", "a-b")
    with pytest.raises(AppError):
        data.export(tmp_path / "wrong.csv", result, {}, "test", "a-b")
    for row in rows:
        row.pop("cost_vnd")
        row.pop("area_mm2")
    with pytest.raises(AppError):
        _dataset(tmp_path, rows).select(28, 200)


@pytest.mark.parametrize("path", sorted(EXAMPLES.glob("*_grid.csv")), ids=lambda p: p.stem)
def test_p6_case_respects_voltage_and_settling(path):
    data = SweepDataset.load(path)
    result = data.select(data.metadata["v_target"], 200, (1, 0, 0))
    assert result.V_peak_opt <= data.metadata["v_target"]
    assert result.settling_time_opt <= 200e-9
    assert result.n_total == 42
    assert result.R_opt == pytest.approx(data.metadata["selected_reference"]["R_ohm"])
    assert result.C_opt == pytest.approx(data.metadata["selected_reference"]["C_F"], rel=1e-10, abs=0)


@pytest.mark.parametrize("value", ["nan", "inf", "-inf"])
def test_nonfinite_user_numbers_rejected(value):
    with pytest.raises(AppError):
        parse_float(value)


def test_fractional_steps_rejected():
    with pytest.raises(AppError):
        parse_int_positive("2.5")
