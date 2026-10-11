"""OptimizerEngine: quét lưới (R_snub, C_snub) và tìm cặp tối ưu theo tiêu chí đa
mục tiêu: V_peak <= V_target (chống đánh thủng MOSFET) và P_loss nhỏ nhất.
"""

from dataclasses import dataclass

import numpy as np

from app.core import rlc_model
from app.utils.errors import NoFeasibleRegionError


@dataclass
class OptimizationResult:
    R_grid: np.ndarray          # luoi 2D (nR, nC)
    C_grid: np.ndarray          # luoi 2D (nR, nC)
    V_peak_grid: np.ndarray     # luoi 2D (nR, nC)
    P_loss_grid: np.ndarray     # luoi 2D (nR, nC)
    feasible_mask: np.ndarray   # luoi 2D bool (nR, nC)
    R_opt: float
    C_opt: float
    P_loss_opt: float
    V_peak_opt: float
    n_feasible: int
    n_total: int


class OptimizerEngine:
    @staticmethod
    def build_grid(R_min: float, R_max: float, R_steps: int,
                    C_min: float, C_max: float, C_steps: int):
        """Tạo lưới quét 2D cho (R_snub, C_snub) bằng np.meshgrid với indexing='ij'
        (trục 0 tương ứng R, trục 1 tương ứng C)."""
        r_axis = np.linspace(R_min, R_max, R_steps)
        c_axis = np.linspace(C_min, C_max, C_steps)
        RR, CC = np.meshgrid(r_axis, c_axis, indexing="ij")
        return RR, CC

    @staticmethod
    def compute_vpeak_grid(Vin: float, I0: float, RR: np.ndarray, CC: np.ndarray, L_stray_H: float) -> np.ndarray:
        """Tính V_peak cho toàn bộ lưới (R, C), vector hóa qua rlc_model.peak_of_response_grid."""
        return rlc_model.peak_of_response_grid(Vin, I0, RR, CC, L_stray_H)

    @staticmethod
    def compute_ploss_grid(Vin: float, fsw_Hz: float, CC: np.ndarray) -> np.ndarray:
        """Công suất tiêu tán trên R_snub: P_loss = C_snub * Vin^2 * fsw (tuyến tính theo C,
        không phụ thuộc R — đúng theo công thức nạp/xả năng lượng tụ mỗi chu kỳ đóng cắt)."""
        return CC * Vin ** 2 * fsw_Hz

    @staticmethod
    def find_optimum(RR: np.ndarray, CC: np.ndarray, V_peak_grid: np.ndarray,
                      P_loss_grid: np.ndarray, V_target: float) -> OptimizationResult:
        """Lọc các điểm khả thi (V_peak <= V_target), chọn điểm có P_loss nhỏ nhất."""
        feasible_mask = V_peak_grid <= V_target
        n_total = feasible_mask.size
        n_feasible = int(np.count_nonzero(feasible_mask))

        if n_feasible == 0:
            raise NoFeasibleRegionError(
                "Không tìm thấy điểm (R_snub, C_snub) nào trong vùng quét thỏa điều kiện "
                f"V_peak <= V_target ({V_target:.3g} V). Hãy nới rộng khoảng R/C hoặc tăng V_target."
            )

        masked_ploss = np.where(feasible_mask, P_loss_grid, np.inf)
        i, j = np.unravel_index(int(np.argmin(masked_ploss)), masked_ploss.shape)

        return OptimizationResult(
            R_grid=RR,
            C_grid=CC,
            V_peak_grid=V_peak_grid,
            P_loss_grid=P_loss_grid,
            feasible_mask=feasible_mask,
            R_opt=float(RR[i, j]),
            C_opt=float(CC[i, j]),
            P_loss_opt=float(P_loss_grid[i, j]),
            V_peak_opt=float(V_peak_grid[i, j]),
            n_feasible=n_feasible,
            n_total=n_total,
        )

    def run_full_sweep(self, R_min: float, R_max: float, R_steps: int,
                        C_min: float, C_max: float, C_steps: int,
                        Vin: float, fsw_Hz: float, L_stray_H: float, C_oss_F: float,
                        V_target: float, V_peak_unprotected: float = None,
                        I0_override: float = None) -> OptimizationResult:
        """Điều phối toàn bộ pipeline: dựng lưới -> tính V_peak/P_loss -> lọc tối ưu."""
        if I0_override is not None:
            i0 = I0_override
        else:
            i0 = rlc_model.estimate_drive_current(Vin, V_peak_unprotected, L_stray_H, C_oss_F)

        RR, CC = self.build_grid(R_min, R_max, R_steps, C_min, C_max, C_steps)
        v_peak_grid = self.compute_vpeak_grid(Vin, i0, RR, CC, L_stray_H)
        p_loss_grid = self.compute_ploss_grid(Vin, fsw_Hz, CC)
        return self.find_optimum(RR, CC, v_peak_grid, p_loss_grid, V_target)
