"""CalculatorEngine: tính toán lý thuyết R_snub, C_snub theo 3 phương pháp học thuật.

Toan bo phuong thuc nhan/tra ve don vi SI (H, F, Ohm, s, V, W). Viec quy doi
nH/pF/kHz/mW chi thuc hien o lop UI.
"""

import numpy as np

from app.core import rlc_model
from app.utils.errors import InputValidationError


class CalculatorEngine:
    """Tính R_snub, C_snub, công suất tiêu tán và nhiệt độ tăng theo 3 phương pháp:
    Hart/Erickson (kinh điển), Luo et al. (RC-Map / hệ số tắt dần), Park et al. (tối
    ưu C_sn chống oversizing kèm ước lượng nhiệt).
    """

    def method_hart_erickson(self, Vin: float, fsw_Hz: float, L_stray_H: float,
                              C_oss_F: float, c_multiplier: float = 2.0) -> dict:
        """Phương pháp truyền thống Daniel W. Hart / Erickson:
        Z0 = sqrt(L_stray/C_oss); chọn R_sn ~= Z0; C_sn ~= c_multiplier * C_oss;
        P_Rsn = C_sn * Vin^2 * fsw.
        """
        z0 = rlc_model.characteristic_impedance(L_stray_H, C_oss_F)
        r_sn = z0
        c_sn = c_multiplier * C_oss_F
        p_rsn = c_sn * Vin ** 2 * fsw_Hz
        return {
            "R_sn": r_sn,
            "C_sn": c_sn,
            "P_Rsn": p_rsn,
            "Z0": z0,
            "delta_T_C": None,
        }

    def method_luo_rcmap(self, Vin: float, V_peak_unprotected: float, fsw_Hz: float,
                          L_stray_H: float, C_oss_F: float, c_multiplier: float = 2.0,
                          zeta_min: float = 0.7) -> dict:
        """Phương pháp Luo et al. (RC-Map / hệ số tắt dần):
        Cố định C_sn = c_multiplier * C_oss, tìm R_sn NHỎ NHẤT sao cho hệ số tắt dần
        zeta = (R/2)*sqrt(C/L) >= zeta_min (biên dưới của vùng "không dao động").
        Đây là phiên bản rút gọn 1 chiều của bản đồ RC-Map đầy đủ (được quét toàn bộ
        ở Tab 3 - Optimizer).
        """
        if zeta_min <= 0:
            raise InputValidationError("Hệ số tắt dần tối thiểu (zeta_min) phải lớn hơn 0.")

        c_sn = c_multiplier * C_oss_F
        # Suy tu zeta = (R/2)*sqrt(C/L)  =>  R = 2*zeta*sqrt(L/C)
        r_sn = 2.0 * zeta_min * np.sqrt(L_stray_H / c_sn)

        i0 = rlc_model.estimate_drive_current(Vin, V_peak_unprotected, L_stray_H, C_oss_F)
        v_peak_check, t_peak, _, _ = rlc_model.peak_of_response(Vin, i0, r_sn, c_sn, L_stray_H)

        p_rsn = c_sn * Vin ** 2 * fsw_Hz
        return {
            "R_sn": r_sn,
            "C_sn": c_sn,
            "P_Rsn": p_rsn,
            "zeta": zeta_min,
            "V_peak_check": v_peak_check,
            "delta_T_C": None,
        }

    def method_park_transient(self, Vin: float, V_peak_unprotected: float, fsw_Hz: float,
                               L_stray_H: float, C_oss_F: float, target_zeta: float = 1.0,
                               theta_ja: float = 150.0, overshoot_ratio_max: float = 1.05) -> dict:
        """Phương pháp Park et al. (đánh giá điện áp Drain quá độ):
        Tìm C_sn NHỎ NHẤT (chống oversizing) sao cho, với R_sn = 2*target_zeta*sqrt(L/C_sn),
        đỉnh điện áp quá độ V_peak <= overshoot_ratio_max * Vin. Dò bằng bisection trên
        thang log vì V_peak giảm đơn điệu khi C_sn tăng (ở zeta cố định, C_sn lớn hơn vừa
        làm tăng thời hằng RC vừa tăng zeta hiệu dụng thực tế... nhưng ở đây zeta được giữ
        cố định qua R nên quan hệ đơn điệu được đảm bảo bởi cách chọn R theo C).
        Sau đó ước tính độ tăng nhiệt DeltaT = P_Rsn * theta_ja (gia nhiet don gian qua
        tro nhiet, theta_ja tinh theo °C/W, mac dinh dung cho diet tro SMD 2512 la ~150 °C/W,
        nguoi dung co the chinh lai theo datasheet linh kien thuc te).
        """
        if overshoot_ratio_max <= 1.0:
            raise InputValidationError("overshoot_ratio_max phải lớn hơn 1.0 (vượt lố phải lớn hơn Vin).")

        i0 = rlc_model.estimate_drive_current(Vin, V_peak_unprotected, L_stray_H, C_oss_F)
        v_target = overshoot_ratio_max * Vin

        def v_peak_for_c(c_sn: float) -> float:
            r_sn = 2.0 * target_zeta * np.sqrt(L_stray_H / c_sn)
            v_peak, _, _, _ = rlc_model.peak_of_response(Vin, i0, r_sn, c_sn, L_stray_H)
            return v_peak

        c_low = 0.5 * C_oss_F
        c_high = 20.0 * C_oss_F

        # Quet so bo tren thang log de dam bao c_high thoa dieu kien (tranh bisection tren
        # khoang khong chua nghiem neu gia tri dau vao qua "khac thuong").
        n_scan = 30
        c_scan = np.logspace(np.log10(c_low), np.log10(c_high), n_scan)
        v_scan = np.array([v_peak_for_c(c) for c in c_scan])
        feasible_idx = np.where(v_scan <= v_target)[0]
        if feasible_idx.size == 0:
            raise InputValidationError(
                "Không tìm được C_sn trong khoảng khảo sát (0.5..20 lần C_oss) thỏa điều kiện "
                f"vượt lố <= {overshoot_ratio_max:.2f}*Vin. Hãy tăng overshoot_ratio_max hoặc "
                "kiểm tra lại V_peak_unprotected."
            )
        c_high = c_scan[feasible_idx[0]]
        c_low = c_scan[feasible_idx[0] - 1] if feasible_idx[0] > 0 else c_low * 0.5

        # Bisection tim C_sn nho nhat thoa dieu kien (chong oversizing).
        for _ in range(60):
            c_mid = np.sqrt(c_low * c_high)  # trung binh hinh hoc, phu hop thang log
            if v_peak_for_c(c_mid) <= v_target:
                c_high = c_mid
            else:
                c_low = c_mid

        c_sn = c_high
        r_sn = 2.0 * target_zeta * np.sqrt(L_stray_H / c_sn)
        p_rsn = c_sn * Vin ** 2 * fsw_Hz
        delta_t = p_rsn * theta_ja

        return {
            "R_sn": r_sn,
            "C_sn": c_sn,
            "P_Rsn": p_rsn,
            "zeta": target_zeta,
            "delta_T_C": delta_t,
            "theta_ja_used": theta_ja,
        }

    @staticmethod
    def recommend_component(P_Rsn_W: float, V_rating: float) -> str:
        """Gợi ý linh kiện thực tế dựa trên công suất tiêu tán tính được và điện áp Vin."""
        min_voltage_rating = 2.0 * V_rating
        if P_Rsn_W < 0.1:
            return (
                f"Điện trở SMD 2512 (hoặc 1206 nếu diện tích cho phép), loại không cảm kháng "
                f"(non-inductive/thick-film), điện áp chịu đựng >= {min_voltage_rating:.0f} V."
            )
        elif P_Rsn_W < 0.5:
            return (
                f"Điện trở công suất 0.5W loại wirewound không cảm kháng (non-inductive winding) "
                f"hoặc ghép song song 2 SMD 2512, điện áp chịu đựng >= {min_voltage_rating:.0f} V."
            )
        else:
            return (
                f"Điện trở công suất >= 1W loại wirewound không cảm kháng, cần kiểm tra tản nhiệt "
                f"kỹ (P_Rsn = {P_Rsn_W * 1000:.1f} mW), điện áp chịu đựng >= {min_voltage_rating:.0f} V."
            )
