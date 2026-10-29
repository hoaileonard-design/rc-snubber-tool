"""WaveformAnalyzer: đọc file dạng sóng xuất từ LTspice/oscilloscope và trích xuất
các chỉ số quá độ (V_peak, tần số ringing, %overshoot, thời gian xác lập).

Module này KHÔNG import tkinter/matplotlib để có thể unit-test độc lập.
"""

import csv
import os
from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.signal import find_peaks

from app.utils.errors import WaveformFileError, InsufficientDataError


@dataclass
class WaveformMetrics:
    v_peak: float
    t_peak: float
    f_ring: float
    percent_overshoot: float
    settling_time: float
    v_final: float
    t_transition: float
    zeta: float = float("nan")
    settling_censored: bool = True
    settling_band: float = 0.05
    settling_hold: float = 500e-9
    warnings: tuple = ()
    frequency_reliable: bool = False


@dataclass
class ParasiticEstimate:
    Lp_H: float
    Cp_F: float
    R_start_ohm: float
    C_start_F: float
    f0_Hz: float
    f1_Hz: float
    warnings: tuple = ()


class WaveformAnalyzer:
    MIN_POINTS = 10

    # --- Đọc file ---

    @staticmethod
    def load_file(path: str):
        """Đọc file .txt/.csv xuất từ LTspice (2 cột: Time, V(DS)).

        Trả về: (t_seconds: np.ndarray, v_volts: np.ndarray)
        """
        if not os.path.isfile(path):
            raise WaveformFileError(f"File không tồn tại: {path}")
        if os.path.getsize(path) == 0:
            raise WaveformFileError(f"File rỗng: {path}")

        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            sample_lines = []
            for _ in range(10):
                line = f.readline()
                if not line:
                    break
                if line.strip():
                    sample_lines.append(line)
        if not sample_lines:
            raise WaveformFileError(f"File không có dữ liệu: {path}")
        sample = "".join(sample_lines)

        # Dò delimiter: thử csv.Sniffer truoc, fallback dem tab/comma, cuoi cung whitespace.
        sep = None
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters="\t,;")
            sep = dialect.delimiter
        except csv.Error:
            first_line = sample_lines[0]
            tab_count = first_line.count("\t")
            comma_count = first_line.count(",")
            if tab_count > 0 and tab_count >= comma_count:
                sep = "\t"
            elif comma_count > 0:
                sep = ","
            else:
                sep = None  # None -> whitespace, xu ly rieng ben duoi

        first_data_line = sample_lines[0].strip()
        tokens = first_data_line.split(sep) if sep else first_data_line.split()
        has_header = False
        for tok in tokens[:2]:
            try:
                float(tok.strip())
            except ValueError:
                has_header = True
                break

        try:
            if sep:
                df = pd.read_csv(
                    path, sep=sep, header=0 if has_header else None,
                    engine="python", usecols=[0, 1],
                )
            else:
                df = pd.read_csv(
                    path, sep=r"\s+", header=0 if has_header else None,
                    engine="python", usecols=[0, 1],
                )
        except Exception as exc:
            raise WaveformFileError(
                f"Không đọc được file '{os.path.basename(path)}': định dạng không đúng chuẩn "
                f"LTspice (2 cột Time, V(DS)). Chi tiết: {exc}"
            )

        df.columns = ["time", "vds"]
        n_before = len(df)
        df["time"] = pd.to_numeric(df["time"], errors="coerce")
        df["vds"] = pd.to_numeric(df["vds"], errors="coerce")
        df = df.dropna()
        n_after = len(df)

        if n_before == 0 or (n_before - n_after) > 0.5 * n_before:
            raise WaveformFileError(
                f"File '{os.path.basename(path)}' có quá nhiều dòng không hợp lệ "
                f"({n_before - n_after}/{n_before} dòng bị loại bỏ). Kiểm tra lại định dạng file."
            )

        if n_after < WaveformAnalyzer.MIN_POINTS:
            raise InsufficientDataError(
                f"File '{os.path.basename(path)}' chỉ có {n_after} điểm dữ liệu hợp lệ, "
                f"cần tối thiểu {WaveformAnalyzer.MIN_POINTS} điểm để phân tích."
            )

        t = df["time"].to_numpy()
        v = df["vds"].to_numpy()

        WaveformAnalyzer._validate(t, v)
        return t, v

    # --- Xử lý tín hiệu ---

    @staticmethod
    def detect_turnoff_transition(t: np.ndarray, v: np.ndarray) -> int:
        """Cạnh tăng trước đỉnh lớn nhất; không dùng dV/dt của chính dao động."""
        WaveformAnalyzer._validate(t, v)
        peak = int(np.argmax(v))
        final = float(np.median(v[-max(5, len(v) // 10):]))
        initial = float(np.quantile(v[:peak + 1], 0.05))
        level = initial + 0.5 * (final - initial)
        crosses = np.flatnonzero((v[:peak] < level) & (v[1:peak + 1] >= level))
        return int(crosses[-1] + 1) if len(crosses) else 0

    @staticmethod
    def _validate(t, v):
        if len(t) != len(v) or len(t) < WaveformAnalyzer.MIN_POINTS:
            raise InsufficientDataError("Cần ít nhất 10 cặp thời gian/điện áp.")
        if not np.all(np.isfinite(t)) or not np.all(np.isfinite(v)):
            raise WaveformFileError("Dữ liệu chứa NaN hoặc vô cực.")
        if np.any(np.diff(t) <= 0):
            raise WaveformFileError("Thời gian phải tăng liên tục, không trùng điểm hoặc ghép nhiều lần quét.")

    @staticmethod
    def analyze(t: np.ndarray, v: np.ndarray, *, start=None, end=None,
                plateau=None, settling_band=0.05, settling_hold=500e-9) -> WaveformMetrics:
        """Một cạnh tăng trong cửa sổ đã chọn. ζ là ước lượng cộng hưởng đơn mode.

        Không suy ra L/C độc lập từ một file. Plateau có thể nhập từ đoạn ổn định
        khác; không đồng nhất nó với Vin của mạch.
        """
        t, v = np.asarray(t, dtype=float), np.asarray(v, dtype=float)
        WaveformAnalyzer._validate(t, v)
        if not 0 < settling_band < 1 or not np.isfinite(settling_hold) or settling_hold <= 0:
            raise WaveformFileError("Dải xác lập và thời gian giữ phải hợp lệ.")
        if start is not None and not np.isfinite(start) or end is not None and not np.isfinite(end):
            raise WaveformFileError("Giới hạn cửa sổ phải hữu hạn.")
        window = np.ones(len(t), dtype=bool)
        if start is not None:
            window &= t >= start
        if end is not None:
            window &= t <= end
        t, v = t[window], v[window]
        WaveformAnalyzer._validate(t, v)
        idx = WaveformAnalyzer.detect_turnoff_transition(t, v)
        post_t = t[idx:]
        post_v = v[idx:]

        if len(post_t) < WaveformAnalyzer.MIN_POINTS:
            raise InsufficientDataError(
                f"Chỉ có {len(post_t)} điểm dữ liệu sau thời điểm chuyển mạch, "
                f"cần tối thiểu {WaveformAnalyzer.MIN_POINTS} điểm để phân tích quá độ."
            )

        # Gia tri xac lap: lay trung vi cua doan duoi tin hieu (10% cuoi, toi thieu 5 diem)
        tail_len = max(5, len(post_v) // 10)
        v_final = float(np.median(post_v[-tail_len:])) if plateau is None else float(plateau)
        if not np.isfinite(v_final):
            raise WaveformFileError("Điện áp plateau phải hữu hạn.")

        i_peak = int(np.argmax(post_v))
        v_peak = float(post_v[i_peak])
        t_peak = float(post_t[i_peak])

        if abs(v_final) < 1e-9:
            raise InsufficientDataError(
                "Giá trị xác lập (v_final) xấp xỉ 0, không thể tính % vượt lố. "
                "Kiểm tra lại dữ liệu đầu vào (có thể chưa đủ thời gian sau chuyển mạch)."
            )
        percent_overshoot = (v_peak - v_final) / v_final * 100.0

        warnings = []
        if plateau is None:
            warnings.append("Plateau ước lượng từ đuôi cửa sổ; kiểm tra lại nếu tín hiệu chưa ổn định.")
        # Các đỉnh đầu tránh sai lệch do nhiễu đuôi và tần số biến đổi theo Coss.
        detrended = post_v - v_final
        peaks_idx, _ = find_peaks(detrended, prominence=max(0.003 * abs(v_final), 0.02))
        peaks_idx = peaks_idx[detrended[peaks_idx] > max(0.01 * abs(v_final), 0.02)][:8]
        if post_v[0] > post_v[1] and detrended[0] > 0.01 * abs(v_final):
            peaks_idx = np.r_[0, peaks_idx][:8]
        zeta = float("nan")
        reliable = False
        if len(peaks_idx) >= 2:
            peak_times = []
            for k in peaks_idx:
                pt = post_t[k]
                if 0 < k < len(post_t) - 1:
                    local = (post_t[k-1:k+2] - pt) * 1e9
                    fit = np.polyfit(local, post_v[k-1:k+2], 2)
                    offset = -fit[1] / (2 * fit[0]) if fit[0] < 0 else 0.0
                    pt += float(np.clip(offset, local[0], local[-1])) * 1e-9
                peak_times.append(pt)
            periods = np.diff(peak_times)
            f_ring = float(1.0 / np.mean(periods))
            reliable = len(peaks_idx) >= 3
            if np.std(periods) / np.mean(periods) > 0.15:
                reliable = False
                warnings.append("Chu kỳ không đều: có thể nhiều mode cộng hưởng hoặc cửa sổ chưa phù hợp.")
            if len(peaks_idx) >= 3:
                delta = float(np.median(np.log(detrended[peaks_idx[:-1]] / detrended[peaks_idx[1:]])))
                if delta >= 0:
                    zeta = delta / np.sqrt(4 * np.pi**2 + delta**2)
            if f_ring * float(np.max(np.diff(post_t))) > 0.1:
                reliable = False
                warnings.append("Có khoảng lấy mẫu dưới 10 điểm/chu kỳ; cần xuất dạng sóng dày hơn.")
        else:
            f_ring = float("nan")
            warnings.append("Không đủ đỉnh để nhận dạng tần số/ζ; không suy tần số từ cạnh đơn.")

        # Tính từ cạnh tăng; cần ở lại trong dải tới cuối cửa sổ và đủ thời gian giữ.
        band = settling_band * abs(v_final)
        within_band = np.abs(post_v - v_final) <= band
        outside = np.flatnonzero(~within_band)
        k = int(outside[-1] + 1) if len(outside) else 0
        censored = k >= len(post_t) or post_t[-1] - post_t[min(k, len(post_t)-1)] < settling_hold
        settling_time = float("nan") if censored else float(post_t[k] - t[idx])
        if censored:
            warnings.append("Chưa xác lập trong cửa sổ với thời gian giữ yêu cầu.")

        return WaveformMetrics(
            v_peak=v_peak,
            t_peak=t_peak,
            f_ring=f_ring,
            percent_overshoot=percent_overshoot,
            settling_time=settling_time,
            v_final=v_final,
            t_transition=float(t[idx]),
            zeta=float(zeta), settling_censored=bool(censored),
            settling_band=settling_band, settling_hold=settling_hold, warnings=tuple(warnings),
            frequency_reliable=reliable,
        )

    @staticmethod
    def identify_parasitics(before: WaveformMetrics, with_cap: WaveformMetrics,
                            added_cap_F: float) -> ParasiticEstimate:
        """Phép dịch tần, cùng mode Lp/Cp và chỉ thêm tụ tại cùng hai nút."""
        f0, f1 = before.f_ring, with_cap.f_ring
        if not all(np.isfinite(x) and x > 0 for x in (f0, f1, added_cap_F)):
            raise InsufficientDataError("Cần hai tần số dao động hợp lệ và tụ thử > 0.")
        if not before.frequency_reliable or not with_cap.frequency_reliable:
            raise InsufficientDataError("Chưa đủ độ tin cậy để suy L/C: cần ≥3 đỉnh, chu kỳ đều và lấy mẫu đủ dày.")
        if f1 >= f0:
            raise InsufficientDataError("Tụ thử phải làm giảm tần số (f1 < f0). Kiểm tra cùng điểm mạch và cùng điều kiện.")
        cp = added_cap_F / ((f0 / f1)**2 - 1)
        lp = 1 / ((2 * np.pi * f0)**2 * cp)
        warnings = ["Lp/Cp tương đương; R/C khởi đầu phải quét và kiểm chứng trên mạch gốc."]
        if f1 / f0 > 0.95:
            warnings.append("Dịch tần quá nhỏ, phép nhận dạng nhạy với sai số đo.")
        if any(np.isfinite(m.zeta) and m.zeta > 0.2 for m in (before, with_cap)):
            warnings.append("Dao động tắt mạnh; công thức dịch tần không hiệu chỉnh damping có thể sai lệch.")
        return ParasiticEstimate(lp, cp, float(np.sqrt(lp / cp)), 3 * cp, f0, f1, tuple(warnings))
