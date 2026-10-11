import math
import numpy as np
import pytest

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
