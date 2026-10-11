import math
import numpy as np
import pytest

from app.core import rlc_model
from app.utils.errors import InputValidationError


def test_undamped_omega():
    L, C = 100e-9, 100e-12
    assert math.isclose(rlc_model.undamped_omega(L, C), 1 / math.sqrt(L * C))


def test_damping_ratio():
    R, C, L = 20.0, 300e-12, 67.54e-9
    expected = (R / 2) * math.sqrt(C / L)
    assert math.isclose(rlc_model.damping_ratio(R, C, L), expected)


def test_characteristic_impedance():
    L, C = 67.54e-9, 150e-12
    assert math.isclose(rlc_model.characteristic_impedance(L, C), math.sqrt(L / C))


def test_estimate_drive_current_valid():
    Vin, L, C_oss = 24.0, 67.54e-9, 150e-12
    v_peak_unprotected = 70.0  # >= 2*Vin=48
    i0 = rlc_model.estimate_drive_current(Vin, v_peak_unprotected, L, C_oss)
    assert i0 > 0


def test_estimate_drive_current_below_threshold_raises():
    with pytest.raises(InputValidationError):
        rlc_model.estimate_drive_current(24.0, 30.0, 67.54e-9, 150e-12)  # 30 < 2*24=48


def test_peak_of_response_zero_resistance_matches_analytic_formula():
    """Với R=0 (không snubber), V_peak phải khớp với công thức
    V_peak = Vin + sqrt(Vin^2 + B^2) dùng để suy ra estimate_drive_current (kiểm tra
    tính nhất quán ngược của 2 hàm)."""
    Vin, L, C_oss = 24.0, 67.54e-9, 150e-12
    v_peak_unprotected = 70.0
    i0 = rlc_model.estimate_drive_current(Vin, v_peak_unprotected, L, C_oss)
    v_peak, t_peak, t_arr, v_arr = rlc_model.peak_of_response(Vin, i0, 0.0, C_oss, L)
    assert math.isclose(v_peak, v_peak_unprotected, rel_tol=1e-3)


def test_peak_of_response_more_damping_reduces_peak():
    Vin, L, C = 24.0, 67.54e-9, 300e-12
    i0 = 0.5
    v_peak_low_r, _, _, _ = rlc_model.peak_of_response(Vin, i0, 1.0, C, L)
    v_peak_high_r, _, _, _ = rlc_model.peak_of_response(Vin, i0, 50.0, C, L)
    assert v_peak_high_r < v_peak_low_r


def test_peak_of_response_grid_matches_scalar():
    Vin, L = 24.0, 67.54e-9
    i0 = 0.5
    R_grid = np.array([[5.0, 5.0], [20.0, 20.0]])
    C_grid = np.array([[200e-12, 500e-12], [200e-12, 500e-12]])
    grid_result = rlc_model.peak_of_response_grid(Vin, i0, R_grid, C_grid, L)
    for i in range(2):
        for j in range(2):
            scalar_peak, _, _, _ = rlc_model.peak_of_response(Vin, i0, R_grid[i, j], C_grid[i, j], L)
            assert math.isclose(grid_result[i, j], scalar_peak, rel_tol=1e-2)


def test_peak_of_response_all_three_damping_branches_run():
    """Kiem tra ca 3 nhanh (under/critical/overdamped) tra ve gia tri huu han, khong
    tran so/NaN. Luu y: KHONG gia dinh v_peak luon >= Vin — voi tat dan qua muc manh
    (zeta lon) va dong kich thich I0 vua phai, dap ung tiem can Vin tu duoi len, khong
    vot lo (dung tinh chat vat ly cua he qua tat dan), nen chi kiem tra tinh huu han
    va tinh don dieu giam dan cua v_peak khi tang R (da kiem tra rieng o test khac)."""
    Vin, L, C = 24.0, 67.54e-9, 300e-12
    i0 = 5.0
    z0 = rlc_model.characteristic_impedance(L, C)
    r_critical = 2 * z0  # zeta = (R/2)*sqrt(C/L) = R/(2*Z0) = 1 khi R = 2*Z0
    for R in [0.1 * r_critical, r_critical, 5 * r_critical]:
        v_peak, t_peak, t_arr, v_arr = rlc_model.peak_of_response(Vin, i0, R, C, L)
        assert np.isfinite(v_peak)
        assert v_peak > 0
