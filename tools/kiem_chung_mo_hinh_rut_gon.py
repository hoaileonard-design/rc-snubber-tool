"""Kiểm chứng hai mô hình rút gọn (dự đoán V_DS đỉnh theo R, C) với 72 điểm RC LTspice của P5.

Chạy từ APP_khoiphuc: ..\\.venv\\Scripts\\python.exe tools\\kiem_chung_mo_hinh_rut_gon.py
Mạch: L ký sinh nối từ mức plateau vào nút D; tại D có Cp và nhánh Rsn–Csn về SW.
  A: tắt tức thời — dao động bắt đầu ở plateau với dòng dư I0 = (Vpk0 − Vp)·sqrt(Cp/L).
  B: dòng MOSFET giảm tuyến tính từ Ioff về 0 trong t_f; t_f suy ra từ đỉnh chưa snubber.
Cả hai giả định Csn đã nạp tới plateau khi bắt đầu (bỏ qua giai đoạn V_DS tăng do driver).
"""
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import brentq

GRID = Path(__file__).resolve().parents[2] / "LTspice/Driver/khao_sat_p5/final_220uH/quet_RC_RCD.csv"
L, CP = 100.12e-9, 273.9e-12          # phương pháp dịch tần số, P5
VP, VPK0, IOFF = 24.5516, 38.8435, 1.88  # plateau, đỉnh chưa snubber, dòng lúc khóa (LTspice P5)


def peak(R, C, cp=CP, i0=0.0, tf=None, T=1.2e-6, dt=0.05e-9):
    """Đỉnh V_D khi tích phân RK4 mạng L–Cp–(R+C).

    Mô hình A (tf=None): MOSFET đã ngắt, L mang thêm dòng dư i0 so với dòng IOFF đã chuyển sang diode.
    Mô hình B: dòng MOSFET giảm tuyến tính IOFF → 0 trong tf.
    """
    R, C = np.atleast_1d(R).astype(float), np.atleast_1d(C).astype(float)
    i_l = np.full_like(R, IOFF + i0)
    v_d, v_c, v_max, t = np.full_like(R, VP), np.full_like(R, VP), np.full_like(R, VP), 0.0

    def f(t, i_l, v_d, v_c):
        i_m = IOFF * max(0.0, 1 - t / tf) if tf else IOFF
        i_r = (v_d - v_c) / R
        return (VP - v_d) / L, (i_l - i_r - i_m) / cp, i_r / C

    for _ in range(int(T / dt)):
        k1 = f(t, i_l, v_d, v_c)
        k2 = f(t + dt / 2, *(x + dt / 2 * k for x, k in zip((i_l, v_d, v_c), k1)))
        k3 = f(t + dt / 2, *(x + dt / 2 * k for x, k in zip((i_l, v_d, v_c), k2)))
        k4 = f(t + dt, *(x + dt * k for x, k in zip((i_l, v_d, v_c), k3)))
        i_l, v_d, v_c = (x + dt / 6 * (a + 2 * b + 2 * c + d) for x, a, b, c, d in zip((i_l, v_d, v_c), k1, k2, k3, k4))
        t += dt
        v_max = np.maximum(v_max, v_d)
    return v_max


def main():
    g = pd.read_csv(GRID)
    g = g[(g.kind == "RC") & (g.status == "ok")]
    big, tiny = 1e9, 1e-15  # "không snubber"
    i0 = (VPK0 - VP) * np.sqrt(CP / L)
    tf = brentq(lambda x: peak(big, tiny, tf=x)[0] - VPK0, 1e-9, 200e-9, xtol=1e-11)
    print(f"Mô hình A: I0 dư = {i0:.3f} A | Mô hình B: t_f = {tf * 1e9:.2f} ns")
    print(f"Tụ thử 470 pF (LTspice 38.95 V): A dự đoán {peak(big, tiny, cp=CP + 470e-12, i0=i0)[0]:.2f} V, "
          f"B dự đoán {peak(big, tiny, cp=CP + 470e-12, tf=tf)[0]:.2f} V")
    for name, kw in (("A tắt tức thời", dict(i0=i0)), ("B dòng giảm dần", dict(tf=tf))):
        e = (peak(g.R_ohm.values, g.C_F.values, **kw) - g.VDS_MAX_V.values) / g.VDS_MAX_V.values * 100
        print(f"{name}: sai số V_peak trung bình {np.mean(abs(e)):.2f} %, lớn nhất {np.max(abs(e)):.2f} % ({len(e)} điểm)")


if __name__ == "__main__":
    main()
