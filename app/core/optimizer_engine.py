"""OptimizerEngine: quét lưới (R_snub, C_snub) và tìm cặp tối ưu theo tiêu chí đa
mục tiêu: V_peak <= V_target (chống đánh thủng MOSFET), rồi cân bằng công suất tổn hao,
chi phí và kích thước của linh kiện thật theo trọng số người dùng chọn.
"""

from dataclasses import dataclass, replace

import numpy as np

from app import config
from app.core import rlc_model
from app.utils.errors import NoFeasibleRegionError, InputValidationError


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
    cost_grid: np.ndarray = None    # VND, inf neu khong co linh kien phu hop
    area_grid: np.ndarray = None    # mm², inf neu khong co linh kien phu hop
    cost_opt: float = 0.0
    area_opt: float = 0.0
    opt_index: tuple = (0, 0)
    R_part: str = ""
    C_part: str = ""
    score_grid: np.ndarray = None
    pareto_mask: np.ndarray = None
    settling_time_grid: np.ndarray = None
    settling_time_opt: float = float("nan")


def _first_match(n_parts: int, shape: tuple, fits) -> np.ndarray:
    """Chỉ số linh kiện đầu tiên (nhỏ/rẻ nhất) thỏa `fits(k)` tại mỗi điểm lưới; -1 nếu không có."""
    idx = np.full(shape, -1)
    for k in range(n_parts):
        idx = np.where((idx < 0) & fits(k), k, idx)
    return idx


def _lookup(parts: list, idx: np.ndarray, col: int) -> np.ndarray:
    values = np.array([p[col] for p in parts], dtype=float)
    return np.where(idx >= 0, values[np.maximum(idx, 0)], np.inf)


def _normalize(grid: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Đưa về [0, 1] theo min/max trên vùng khả thi để cộng được các mục tiêu khác đơn vị."""
    lo, hi = grid[mask].min(), grid[mask].max()
    if hi <= lo:
        return np.zeros(grid.shape)
    return (np.where(mask, grid, lo) - lo) / (hi - lo)


class OptimizerEngine:
    @staticmethod
    def build_grid(R_min: float, R_max: float, R_steps: int,
                    C_min: float, C_max: float, C_steps: int):
        """Tạo lưới quét 2D cho (R_snub, C_snub) bằng np.meshgrid với indexing='ij'
        (trục 0 tương ứng R, trục 1 tương ứng C)."""
        if not all(np.isfinite(x) and x > 0 for x in (R_min, R_max, C_min, C_max)):
            raise InputValidationError("Giới hạn R/C phải hữu hạn và > 0.")
        if R_max <= R_min or C_max <= C_min or min(R_steps, C_steps) < 2 or R_steps * C_steps > 10_000:
            raise InputValidationError("Giới hạn tăng, ít nhất 2 bước/trục và tối đa 10.000 điểm mô hình.")
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
    def compute_part_grids(P_loss_grid: np.ndarray, V_peak_grid: np.ndarray, CC: np.ndarray):
        """Chọn linh kiện thật cho từng điểm (R, C) từ config.RESISTOR_PARTS / CAPACITOR_PARTS:
        điện trở chịu được R_POWER_DERATING x P_loss; tụ đủ điện dung và chịu được
        C_VOLTAGE_DERATING x V_peak. Trả về (chi phí VND, diện tích mm², chỉ số R, chỉ số C);
        điểm không có linh kiện phù hợp nhận chi phí/diện tích = inf và chỉ số = -1."""
        rp, cp = config.RESISTOR_PARTS, config.CAPACITOR_PARTS
        r_idx = _first_match(len(rp), P_loss_grid.shape,
                             lambda k: rp[k][1] >= config.R_POWER_DERATING * P_loss_grid)
        # (1 + 1e-9): giá trị từ linspace có thể lệch vài ULP so với điện dung danh định
        c_idx = _first_match(len(cp), CC.shape,
                             lambda k: (CC <= cp[k][1] * (1 + 1e-9))
                             & (cp[k][2] >= config.C_VOLTAGE_DERATING * V_peak_grid))
        cost = _lookup(rp, r_idx, 3) + _lookup(cp, c_idx, 4)
        area = _lookup(rp, r_idx, 2) + _lookup(cp, c_idx, 3)
        return cost, area, r_idx, c_idx

    @staticmethod
    def find_optimum(RR: np.ndarray, CC: np.ndarray, V_peak_grid: np.ndarray,
                      P_loss_grid: np.ndarray, V_target: float,
                      cost_grid: np.ndarray = None, area_grid: np.ndarray = None,
                      weights: tuple = (1.0, 0.0, 0.0),
                      valid_mask: np.ndarray = None) -> OptimizationResult:
        """Lọc điểm khả thi (V_peak <= V_target và có linh kiện thật phù hợp), rồi chọn điểm có
        tổng có trọng số nhỏ nhất của (công suất, chi phí, kích thước) đã chuẩn hóa về [0, 1].
        Mặc định weights=(1, 0, 0): chỉ tối thiểu P_loss như phiên bản ban đầu."""
        cost = np.zeros(P_loss_grid.shape) if cost_grid is None else cost_grid
        area = np.zeros(P_loss_grid.shape) if area_grid is None else area_grid
        if len(weights) != 3 or not np.all(np.isfinite(weights)) or min(weights) < 0 or sum(weights) <= 0:
            raise InputValidationError("Cần ba trọng số hữu hạn, không âm và ít nhất một trọng số > 0.")
        if not np.isfinite(V_target) or V_target <= 0:
            raise InputValidationError("Điện áp mục tiêu phải hữu hạn và > 0.")
        feasible_mask = ((V_peak_grid <= V_target) & np.isfinite(V_peak_grid)
                         & np.isfinite(P_loss_grid) & (P_loss_grid >= 0)
                         & np.isfinite(cost) & (cost >= 0) & np.isfinite(area) & (area >= 0))
        if valid_mask is not None:
            feasible_mask &= valid_mask
        n_total = feasible_mask.size
        n_feasible = int(np.count_nonzero(feasible_mask))

        if n_feasible == 0:
            raise NoFeasibleRegionError(
                "Không tìm thấy điểm (R_snub, C_snub) nào trong vùng quét thỏa điều kiện "
                f"V_peak <= V_target ({V_target:.3g} V) và có linh kiện thật phù hợp. "
                "Kiểm tra thêm giới hạn thời gian, công suất và dữ liệu chưa xác lập."
            )

        score = sum(w * _normalize(g, feasible_mask) for w, g in zip(weights, (P_loss_grid, cost, area)))
        # Chỉ dùng Vpeak phá hòa thật sự; không để epsilon đổi thứ tự mục tiêu.
        available = np.flatnonzero(feasible_mask)
        order = np.lexsort((V_peak_grid.ravel()[available], score.ravel()[available]))
        i, j = np.unravel_index(int(available[order[0]]), score.shape)

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
            cost_grid=cost_grid,
            area_grid=area_grid,
            cost_opt=float(cost[i, j]),
            area_opt=float(area[i, j]),
            opt_index=(i, j),
            score_grid=np.where(feasible_mask, score, np.nan),
        )

    def run_full_sweep(self, R_min: float, R_max: float, R_steps: int,
                        C_min: float, C_max: float, C_steps: int,
                        Vin: float, fsw_Hz: float, L_stray_H: float, C_oss_F: float,
                        V_target: float, V_peak_unprotected: float = None,
                        I0_override: float = None,
                        weights: tuple = (1.0, 0.0, 0.0)) -> OptimizationResult:
        """Điều phối toàn bộ pipeline: dựng lưới -> tính V_peak/P_loss -> chọn linh kiện thật
        (chi phí, kích thước) -> lọc và chọn điểm tối ưu theo trọng số."""
        if I0_override is not None:
            i0 = I0_override
        else:
            i0 = rlc_model.estimate_drive_current(Vin, V_peak_unprotected, L_stray_H, C_oss_F)

        RR, CC = self.build_grid(R_min, R_max, R_steps, C_min, C_max, C_steps)
        v_peak_grid = self.compute_vpeak_grid(Vin, i0, RR, CC, L_stray_H)
        p_loss_grid = self.compute_ploss_grid(Vin, fsw_Hz, CC)
        cost_grid, area_grid, r_idx, c_idx = self.compute_part_grids(p_loss_grid, v_peak_grid, CC)
        result = self.find_optimum(RR, CC, v_peak_grid, p_loss_grid, V_target, cost_grid, area_grid, weights)
        i, j = result.opt_index
        return replace(result,
                       R_part=config.RESISTOR_PARTS[r_idx[i, j]][0],
                       C_part=config.CAPACITOR_PARTS[c_idx[i, j]][0])
