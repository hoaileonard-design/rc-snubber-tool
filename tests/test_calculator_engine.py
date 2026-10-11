import math
import pytest

from app.core.calculator_engine import CalculatorEngine
from app.utils.errors import InputValidationError


@pytest.fixture
def engine():
    return CalculatorEngine()


@pytest.fixture
def defaults():
    return dict(
        Vin=24.0,
        fsw_Hz=20_000.0,
        L_stray_H=67.54e-9,
        C_oss_F=150e-12,
        V_peak_unprotected=70.0,
    )


def test_hart_erickson_matches_hand_calculation(engine, defaults):
    result = engine.method_hart_erickson(
        Vin=defaults["Vin"], fsw_Hz=defaults["fsw_Hz"],
        L_stray_H=defaults["L_stray_H"], C_oss_F=defaults["C_oss_F"], c_multiplier=2.0,
    )
    expected_z0 = math.sqrt(defaults["L_stray_H"] / defaults["C_oss_F"])
    assert math.isclose(result["Z0"], expected_z0, rel_tol=1e-6)
    assert math.isclose(result["R_sn"], expected_z0, rel_tol=1e-6)
    assert math.isclose(result["C_sn"], 2.0 * defaults["C_oss_F"], rel_tol=1e-6)
    expected_p = result["C_sn"] * defaults["Vin"] ** 2 * defaults["fsw_Hz"]
    assert math.isclose(result["P_Rsn"], expected_p, rel_tol=1e-6)
    # Sanity: gia tri phai co bac do lon hop ly (~21 Ohm, ~300pF, ~3.5mW)
    assert 15 < result["R_sn"] < 30
    assert result["P_Rsn"] < 0.01


def test_luo_rcmap_zeta_meets_minimum(engine, defaults):
    result = engine.method_luo_rcmap(
        Vin=defaults["Vin"], V_peak_unprotected=defaults["V_peak_unprotected"],
        fsw_Hz=defaults["fsw_Hz"], L_stray_H=defaults["L_stray_H"], C_oss_F=defaults["C_oss_F"],
        c_multiplier=2.0, zeta_min=0.7,
    )
    assert result["zeta"] == 0.7
    assert result["R_sn"] > 0
    assert result["C_sn"] > 0
    assert result["V_peak_check"] > defaults["Vin"]


def test_luo_rcmap_rejects_low_unprotected_peak(engine, defaults):
    with pytest.raises(InputValidationError):
        engine.method_luo_rcmap(
            Vin=defaults["Vin"], V_peak_unprotected=30.0,  # < 2*Vin
            fsw_Hz=defaults["fsw_Hz"], L_stray_H=defaults["L_stray_H"], C_oss_F=defaults["C_oss_F"],
        )


def test_park_transient_no_oversizing_monotonic_check(engine, defaults):
    result = engine.method_park_transient(
        Vin=defaults["Vin"], V_peak_unprotected=defaults["V_peak_unprotected"],
        fsw_Hz=defaults["fsw_Hz"], L_stray_H=defaults["L_stray_H"], C_oss_F=defaults["C_oss_F"],
        target_zeta=1.0, theta_ja=150.0, overshoot_ratio_max=1.05,
    )
    c_sn = result["C_sn"]
    assert c_sn > 0
    assert result["delta_T_C"] == pytest.approx(result["P_Rsn"] * 150.0)

    # Kiem tra tinh "khong oversizing": giam nhe C_sn phai vi pham dieu kien vuot lo,
    # tang nhe C_sn van phai thoa dieu kien (bisection hoi tu dung huong).
    from app.core import rlc_model
    i0 = rlc_model.estimate_drive_current(
        defaults["Vin"], defaults["V_peak_unprotected"], defaults["L_stray_H"], defaults["C_oss_F"]
    )

    def v_peak_for_c(c):
        r = 2.0 * 1.0 * math.sqrt(defaults["L_stray_H"] / c)
        v_peak, _, _, _ = rlc_model.peak_of_response(defaults["Vin"], i0, r, c, defaults["L_stray_H"])
        return v_peak

    v_target = 1.05 * defaults["Vin"]
    assert v_peak_for_c(c_sn * 1.2) <= v_target * 1.01  # tang C van thoa (co dung sai nho)
    assert v_peak_for_c(c_sn * 0.8) > v_target * 0.99  # giam C vi pham (co dung sai nho)


def test_recommend_component_thresholds():
    low = CalculatorEngine.recommend_component(0.05, 24.0)
    mid = CalculatorEngine.recommend_component(0.3, 24.0)
    high = CalculatorEngine.recommend_component(0.8, 24.0)
    assert "SMD 2512" in low
    assert "0.5W" in mid
    assert "1W" in high
