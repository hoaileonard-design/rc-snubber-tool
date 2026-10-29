import math
import numpy as np
import pytest

from app import config
from app.core.optimizer_engine import OptimizerEngine
from app.utils.errors import NoFeasibleRegionError


@pytest.fixture
def engine():
    return OptimizerEngine()


def test_build_grid_shape():
    RR, CC = OptimizerEngine.build_grid(1.0, 50.0, 10, 100e-12, 2000e-12, 8)
    assert RR.shape == (10, 8)
    assert CC.shape == (10, 8)
    assert math.isclose(RR[0, 0], 1.0)
    assert math.isclose(RR[-1, 0], 50.0)
    assert math.isclose(CC[0, 0], 100e-12)
    assert math.isclose(CC[0, -1], 2000e-12)


def test_ploss_grid_linear_in_c():
    Vin, fsw = 24.0, 20_000.0
    RR, CC = OptimizerEngine.build_grid(1.0, 50.0, 5, 100e-12, 2000e-12, 5)
    p_loss = OptimizerEngine.compute_ploss_grid(Vin, fsw, CC)
    expected = CC * Vin ** 2 * fsw
    assert np.allclose(p_loss, expected)
    # Tang don dieu theo C tai R co dinh
    assert np.all(np.diff(p_loss[0, :]) > 0)


def test_run_full_sweep_finds_feasible_optimum():
    engine = OptimizerEngine()
    result = engine.run_full_sweep(
        R_min=1.0, R_max=50.0, R_steps=30,
        C_min=100e-12, C_max=2000e-12, C_steps=30,
        Vin=24.0, fsw_Hz=20_000.0, L_stray_H=67.54e-9, C_oss_F=150e-12,
        V_target=30.0, V_peak_unprotected=70.0,
    )
    assert result.n_feasible > 0
    assert result.V_peak_opt <= 30.0
    # Diem toi uu phai nam trong luoi
    assert 1.0 <= result.R_opt <= 50.0
    assert 100e-12 <= result.C_opt <= 2000e-12


def test_run_full_sweep_no_feasible_region_raises():
    engine = OptimizerEngine()
    with pytest.raises(NoFeasibleRegionError):
        engine.run_full_sweep(
            R_min=1.0, R_max=50.0, R_steps=10,
            C_min=100e-12, C_max=2000e-12, C_steps=10,
            Vin=24.0, fsw_Hz=20_000.0, L_stray_H=67.54e-9, C_oss_F=150e-12,
            V_target=1.0,  # thap hon Vin -> khong the dat duoc
            V_peak_unprotected=70.0,
        )


def test_find_optimum_picks_min_ploss_among_feasible():
    RR = np.array([[1.0, 1.0], [2.0, 2.0]])
    CC = np.array([[100e-12, 200e-12], [100e-12, 200e-12]])
    V_peak_grid = np.array([[10.0, 40.0], [50.0, 15.0]])
    P_loss_grid = np.array([[0.001, 0.002], [0.0005, 0.0015]])
    result = OptimizerEngine.find_optimum(RR, CC, V_peak_grid, P_loss_grid, V_target=20.0)
    # Feasible: (0,0) V=10<=20 P=0.001 ; (1,1) V=15<=20 P=0.0015 -> min la (0,0)
    assert result.R_opt == 1.0
    assert result.C_opt == 100e-12
    assert result.n_feasible == 2


@pytest.fixture
def small_catalog(monkeypatch):
    # Danh muc gia co dinh de test khong phu thuoc gia/kich thuoc that trong config
    monkeypatch.setattr(config, "RESISTOR_PARTS", [("R-small", 0.1, 1.0, 10), ("R-big", 1.0, 10.0, 100)])
    monkeypatch.setattr(config, "CAPACITOR_PARTS", [("C-small", 1e-9, 50.0, 2.0, 20),
                                                    ("C-big", 100e-9, 630.0, 20.0, 200)])
    monkeypatch.setattr(config, "R_POWER_DERATING", 2.0)
    monkeypatch.setattr(config, "C_VOLTAGE_DERATING", 1.5)


def test_part_grids_pick_first_adequate_part(small_catalog):
    P = np.array([[0.01, 0.2, 1.0]])    # can R chiu 0.02 / 0.4 / 2.0 W
    V = np.array([[20.0, 20.0, 20.0]])  # can tu chiu >= 30 V
    C = np.array([[1e-9, 50e-9, 1e-6]])
    cost, area, r_idx, c_idx = OptimizerEngine.compute_part_grids(P, V, C)
    assert r_idx.tolist() == [[0, 1, -1]]
    assert c_idx.tolist() == [[0, 1, -1]]
    assert cost[0, 0] == 10 + 20
    assert area[0, 1] == 10.0 + 20.0
    assert np.isinf(cost[0, 2]) and np.isinf(area[0, 2])


def test_capacitor_voltage_derating_forces_bigger_part(small_catalog):
    # 1.5 x 40 V = 60 V > 50 V cua C-small -> phai dung C-big
    _, _, _, c_idx = OptimizerEngine.compute_part_grids(np.array([[0.01]]), np.array([[40.0]]), np.array([[1e-9]]))
    assert c_idx.tolist() == [[1]]


def test_cost_weight_moves_optimum_to_cheaper_point():
    RR = np.array([[1.0, 2.0]])
    CC = np.array([[100e-12, 200e-12]])
    V = np.array([[10.0, 10.0]])
    P = np.array([[0.001, 0.002]])
    cost = np.array([[500.0, 100.0]])
    area = np.array([[5.0, 5.0]])
    by_power = OptimizerEngine.find_optimum(RR, CC, V, P, 20.0, cost, area, weights=(1, 0, 0))
    by_cost = OptimizerEngine.find_optimum(RR, CC, V, P, 20.0, cost, area, weights=(0, 1, 0))
    assert by_power.R_opt == 1.0
    assert by_cost.R_opt == 2.0
    assert by_cost.cost_opt == 100.0


def test_point_without_real_part_is_infeasible():
    RR = np.array([[1.0, 2.0]])
    CC = np.array([[100e-12, 200e-12]])
    V = np.array([[10.0, 10.0]])
    P = np.array([[0.001, 0.002]])
    result = OptimizerEngine.find_optimum(RR, CC, V, P, 20.0,
                                          np.array([[np.inf, 100.0]]), np.array([[5.0, 5.0]]))
    assert result.n_feasible == 1
    assert result.R_opt == 2.0


def test_run_full_sweep_reports_parts_cost_and_size():
    result = OptimizerEngine().run_full_sweep(
        R_min=1.0, R_max=50.0, R_steps=20,
        C_min=100e-12, C_max=2000e-12, C_steps=20,
        Vin=24.0, fsw_Hz=20_000.0, L_stray_H=67.54e-9, C_oss_F=150e-12,
        V_target=30.0, V_peak_unprotected=70.0, weights=(1.0, 1.0, 1.0),
    )
    assert result.R_part and result.C_part
    assert np.isfinite(result.cost_opt) and result.cost_opt > 0
    assert result.area_opt > 0
    assert result.V_peak_opt <= 30.0
