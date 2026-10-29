"""Chọn RC/RCD từ dữ liệu của một mạch/điểm làm việc, không giả định topology."""

import hashlib
import json
from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np
import pandas as pd

from app import config
from app.core.optimizer_engine import OptimizerEngine
from app.utils.errors import InputValidationError, WaveformFileError


@dataclass
class SweepDataset:
    path: str
    sha256: str
    rows: pd.DataFrame
    metadata: dict

    @classmethod
    def load(cls, path):
        path = Path(path)
        try:
            frame = pd.read_csv(path, encoding="utf-8-sig")
        except (OSError, ValueError) as exc:
            raise WaveformFileError(f"Không đọc được bảng khảo sát: {exc}") from exc
        required = {"R_ohm", "C_F", "VDS_MAX_V", "ts_ns", "ts_censored", "P_snubber_W"}
        missing = required - set(frame.columns)
        if missing or frame.empty:
            raise WaveformFileError(f"Bảng rỗng hoặc thiếu cột: {', '.join(sorted(missing))}.")
        if len(frame) > 5000:
            raise WaveformFileError("Tối đa 5.000 điểm/bảng; chia vùng quét trước khi tối ưu Pareto.")
        for col in ("R_ohm", "C_F", "VDS_MAX_V", "P_snubber_W"):
            values = pd.to_numeric(frame[col], errors="coerce")
            if not np.all(np.isfinite(values)) or np.any(values < 0) or col != "P_snubber_W" and np.any(values == 0):
                raise WaveformFileError(f"Cột {col} chứa số không hợp lệ; đơn vị phải là Ω/F/V/W.")
            frame[col] = values
        frame["R_ohm"] = np.round(frame["R_ohm"], 9)
        frame["C_F"] = np.round(frame["C_F"] * 1e12, 6) * 1e-12
        bools = frame["ts_censored"].astype(str).str.strip().str.lower().map(
            {"true": True, "false": False, "1": True, "0": False})
        if bools.isna().any():
            raise WaveformFileError("ts_censored phải là True/False hoặc 1/0.")
        frame["ts_censored"] = bools.astype(bool)
        frame["ts_ns"] = pd.to_numeric(frame["ts_ns"], errors="coerce")
        invalid_ts = ~np.isfinite(frame["ts_ns"]) | (frame["ts_ns"] < 0)
        if np.any(invalid_ts & ~frame["ts_censored"]):
            raise WaveformFileError("ts_ns thiếu/không hợp lệ phải đi kèm ts_censored=True.")
        for col in ("case", "topology", "node", "kind"):
            if col in frame and frame[col].nunique(dropna=False) != 1:
                raise WaveformFileError(f"Cột {col} trộn nhiều mạch/loại. Mỗi bảng chỉ chứa một điều kiện và một loại snubber.")
        # Đối chiếu theo giá trị thực, tránh sai số vài ULP từ file CSV.
        keys = list(zip(np.round(frame.R_ohm, 9), np.round(frame.C_F * 1e12, 6)))
        if len(set(keys)) != len(keys):
            raise WaveformFileError("Bảng có cặp R/C trùng. Chọn một mức kiểm chứng cho mỗi cặp trước khi nạp.")
        metadata = {}
        sidecar = path.with_suffix(".json")
        if sidecar.is_file():
            try:
                metadata = json.loads(sidecar.read_text(encoding="utf-8-sig"))
                if not isinstance(metadata, dict):
                    raise ValueError("metadata phải là object")
            except (OSError, ValueError) as exc:
                raise WaveformFileError(f"Metadata cùng tên không hợp lệ: {exc}") from exc
        return cls(str(path.resolve()), hashlib.sha256(path.read_bytes()).hexdigest(), frame, metadata)

    def select(self, v_target, ts_max_ns, weights=(1, 1, 1), p_max_w=None):
        for name, val in (("ts_max_ns", ts_max_ns), ("p_max_w", p_max_w)):
            if val is not None and (not np.isfinite(val) or val <= 0):
                raise InputValidationError(f"{name} phải hữu hạn và > 0.")
        r_axis = np.sort(self.rows.R_ohm.unique())
        c_axis = np.sort(self.rows.C_F.unique())
        if len(r_axis) * len(c_axis) > 100_000:
            raise InputValidationError("Bảng quá lớn (hơn 100.000 ô); chia thành các vùng khảo sát.")
        rr, cc = np.meshgrid(r_axis, c_axis, indexing="ij")
        voltage, power, ts = (np.full(rr.shape, np.nan) for _ in range(3))
        valid = np.zeros(rr.shape, dtype=bool)
        costs, areas = (np.full(rr.shape, np.inf) for _ in range(2))
        supplied = {"cost_vnd", "area_mm2"}.issubset(self.rows.columns)
        if bool("cost_vnd" in self.rows) != bool("area_mm2" in self.rows):
            raise InputValidationError("Nhập cả cost_vnd và area_mm2, hoặc bỏ cả hai để dùng ước lượng danh mục.")
        for row in self.rows.to_dict("records"):
            i, j = int(np.searchsorted(r_axis, row["R_ohm"])), int(np.searchsorted(c_axis, row["C_F"]))
            voltage[i, j], power[i, j], ts[i, j] = row["VDS_MAX_V"], row["P_snubber_W"], row["ts_ns"]
            valid[i, j] = (not row["ts_censored"] and np.isfinite(row["ts_ns"])
                           and row["ts_ns"] <= ts_max_ns
                           and (p_max_w is None or row["P_snubber_W"] <= p_max_w))
            if supplied:
                try:
                    costs[i, j], areas[i, j] = float(row["cost_vnd"]), float(row["area_mm2"])
                except (ValueError, TypeError) as exc:
                    raise InputValidationError("Giá/diện tích phải là số hữu hạn không âm.") from exc
                if not np.isfinite(costs[i, j] + areas[i, j]) or min(costs[i, j], areas[i, j]) < 0:
                    raise InputValidationError("Giá/diện tích phải là số hữu hạn không âm.")
        if not supplied:
            costs, areas, _, _ = OptimizerEngine.compute_part_grids(power, voltage, cc)
            # Danh mục hiện có chỉ tính R+C. RCD cần cung cấp cả diode và phần phụ.
            if "kind" in self.rows and str(self.rows.kind.iloc[0]).upper() == "RCD":
                raise InputValidationError("Bảng RCD cần cost_vnd/area_mm2 của toàn bộ R+C+D; không dùng giá R+C thay thế.")
        result = OptimizerEngine.find_optimum(rr, cc, voltage, power, v_target,
                                              costs, areas, weights, valid_mask=valid)
        objectives = np.column_stack([g[result.feasible_mask] for g in (power, costs, areas)])
        pareto = np.array([not np.any(np.all(objectives <= p, axis=1) & np.any(objectives < p, axis=1))
                           for p in objectives])
        pareto_mask = np.zeros(rr.shape, dtype=bool)
        pareto_mask[result.feasible_mask] = pareto
        i, j = result.opt_index
        rp = cp = "Theo bảng dữ liệu"
        if not supplied:
            _, _, ri, ci = OptimizerEngine.compute_part_grids(power, voltage, cc)
            rp, cp = config.RESISTOR_PARTS[ri[i, j]][0], config.CAPACITOR_PARTS[ci[i, j]][0]
        return replace(result, n_total=len(self.rows), settling_time_grid=ts * 1e-9, settling_time_opt=float(ts[i, j] * 1e-9),
                       pareto_mask=pareto_mask, R_part=rp, C_part=cp)

    def ranked_rows(self, result):
        records = []
        for row in self.rows.to_dict("records"):
            ix = np.argwhere(np.isclose(result.R_grid, row["R_ohm"], rtol=1e-10)
                             & np.isclose(result.C_grid, row["C_F"], rtol=1e-10, atol=0))
            i, j = ix[0]
            records.append(dict(row, feasible=bool(result.feasible_mask[i, j]),
                                score=float(result.score_grid[i, j]),
                                pareto=bool(result.pareto_mask[i, j]),
                                cost_vnd=float(result.cost_grid[i, j]),
                                area_mm2=float(result.area_grid[i, j]),
                                selected=(i, j) == result.opt_index))
        return pd.DataFrame(records).sort_values(["feasible", "score"], ascending=[False, True])

    def export(self, path, result, criteria, circuit, node):
        """Xuất đúng kết quả đã tính; UI khóa snapshot khi người dùng đổi đầu vào."""
        path = Path(path)
        if path.suffix.lower() != ".md":
            raise InputValidationError("Chọn tên báo cáo đuôi .md; app sẽ tạo bảng .csv cùng tên.")
        if Path(self.path).resolve() in (path.resolve(), path.with_suffix(".csv").resolve()):
            raise InputValidationError("Chọn tên báo cáo khác file dữ liệu đầu vào để giữ nguyên bằng chứng.")
        table = self.ranked_rows(result)
        selected = table.loc[table.selected].iloc[0]
        report = f"""# Kết quả thiết kế snubber theo dữ liệu

Mạch/điều kiện: {circuit}

Điểm gắn/đo (hai nút): {node}

File: `{self.path}`

SHA256: `{self.sha256}`

Metadata đầu vào: `{json.dumps(self.metadata, ensure_ascii=False)}`

## Tiêu chí và kết quả

- Vpeak ≤ {criteria['v_target']:.6g} V; ts ≤ {criteria['ts_max_ns']:.6g} ns.
- Psn tối đa: {criteria.get('p_max_w')}; trọng số (công suất, giá, diện tích): {criteria['weights']}.
- R = {result.R_opt:.9g} Ω; C = {result.C_opt * 1e9:.9g} nF.
- Vpeak = {result.V_peak_opt:.9g} V; ts = {result.settling_time_opt * 1e9:.9g} ns.
- Psn = {result.P_loss_opt:.9g} W; giá = {result.cost_opt:.9g} VND; diện tích = {result.area_opt:.9g} mm².
- Khả thi {result.n_feasible}/{len(self.rows)} điểm đã nạp; Pareto {int(result.pareto_mask.sum())} điểm.
- Mức bằng chứng của cặp chọn: {selected.get('evidence', 'Theo dữ liệu người dùng; chưa kiểm chứng nguồn')}.
- Dấu vết dạng sóng: {selected.get('raw', 'Chưa cung cấp')}.

## Phạm vi kết luận

Đây là lựa chọn trong những điểm đã khảo sát của một điều kiện. Ô chưa chạy không được nội suy.
Nếu thiếu giá/diện tích đầu vào, app dùng ước lượng danh mục, chưa xác nhận báo giá hay khả năng chịu xung.
Psn là tổn hao nhánh snubber theo cột dữ liệu, không phải tổng tổn hao hệ thống. Không dùng để khẳng định hiệu suất toàn bộ.
ts phụ thuộc cửa sổ/dải/độ giữ của nguồn dữ liệu; cần thống nhất tiêu chí giữa các lần đo.
Tên mạch và metadata do người dùng/nguồn dữ liệu cung cấp, không phải chứng nhận hỗ trợ mọi topology.
Chưa xác nhận phần cứng, dung sai và lựa chọn linh kiện thực tế.

## Các điểm khả thi (thứ tự điểm số)

| R (Ω) | C (nF) | Vpeak (V) | ts (ns) | Psn (W) | Giá (VND) | mm² | Pareto |
|---|---|---|---|---|---|---|---|
"""
        for row in table.loc[table.feasible].to_dict("records"):
            report += (f"| {row['R_ohm']:.6g} | {row['C_F']*1e9:.6g} | {row['VDS_MAX_V']:.6g} | "
                       f"{row['ts_ns']:.6g} | {row['P_snubber_W']:.6g} | {row['cost_vnd']:.6g} | "
                       f"{row['area_mm2']:.6g} | {row['pareto']} |\n")
        path.write_text(report, encoding="utf-8")
        table.to_csv(path.with_suffix(".csv"), index=False, encoding="utf-8-sig")
        return path, path.with_suffix(".csv")
