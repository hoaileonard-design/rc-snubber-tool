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

        if np.any(np.diff(t) < 0):
            order = np.argsort(t)
            t = t[order]
            v = v[order]

        return t, v

    # --- Xử lý tín hiệu ---

    @staticmethod
    def detect_turnoff_transition(t: np.ndarray, v: np.ndarray) -> int:
        """Tìm chỉ số thời điểm chuyển mạch (turn-off) bằng cách tìm nơi có độ dốc
        (dV/dt) lớn nhất về trị tuyệt đối — đây là thời điểm điện áp V_DS biến thiên
        nhanh nhất khi MOSFET chuyển từ dẫn sang ngắt."""
        dv = np.gradient(v, t)
        return int(np.argmax(np.abs(dv)))

    @staticmethod
    def _fft_dominant_freq(t: np.ndarray, v_detrended: np.ndarray) -> float:
        """Ước lượng tần số dao động chủ đạo bằng FFT khi không đủ đỉnh để đo trực tiếp
        chu kỳ dao động (dùng khi tín hiệu tắt dần quá nhanh, chỉ còn 0-1 đỉnh rõ ràng)."""
        n = len(t)
        if n < 4:
            return 0.0
        dt_mean = np.mean(np.diff(t))
        if dt_mean <= 0:
            return 0.0
        t_uniform = np.linspace(t[0], t[-1], n)
        v_uniform = np.interp(t_uniform, t, v_detrended)
        spectrum = np.abs(np.fft.rfft(v_uniform))
        freqs = np.fft.rfftfreq(n, d=(t_uniform[1] - t_uniform[0]))
        if len(spectrum) <= 1:
            return 0.0
        spectrum[0] = 0.0  # loai bo thanh phan DC
        dominant_idx = int(np.argmax(spectrum))
        return float(freqs[dominant_idx])

    @staticmethod
    def analyze(t: np.ndarray, v: np.ndarray) -> WaveformMetrics:
        """Trích xuất các chỉ số quá độ từ dạng sóng V_DS(t) sau thời điểm chuyển mạch."""
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
        v_final = float(np.median(post_v[-tail_len:]))

        i_peak = int(np.argmax(post_v))
        v_peak = float(post_v[i_peak])
        t_peak = float(post_t[i_peak])

        if abs(v_final) < 1e-9:
            raise InsufficientDataError(
                "Giá trị xác lập (v_final) xấp xỉ 0, không thể tính % vượt lố. "
                "Kiểm tra lại dữ liệu đầu vào (có thể chưa đủ thời gian sau chuyển mạch)."
            )
        percent_overshoot = (v_peak - v_final) / v_final * 100.0

        # Tan so ringing: tim cac dinh dao dong tren tin hieu da tru muc xac lap.
        detrended = post_v - v_final
        peaks_idx, _ = find_peaks(detrended)
        if len(peaks_idx) >= 2:
            periods = np.diff(post_t[peaks_idx])
            f_ring = float(1.0 / np.mean(periods))
        else:
            f_ring = WaveformAnalyzer._fft_dominant_freq(post_t, detrended)

        # Thoi gian xac lap: thoi diem (tinh tu t_peak) ma tin hieu di vao va o lai trong
        # dai +-2% quanh gia tri xac lap den het cua so du lieu.
        band = 0.02 * abs(v_final)
        within_band = np.abs(post_v - v_final) <= band
        settling_time = t_peak
        for k in range(len(post_t)):
            if np.all(within_band[k:]):
                settling_time = float(post_t[k] - t[idx])
                break
        else:
            settling_time = float(post_t[-1] - t[idx])  # chua xac lap trong cua so quan sat

        return WaveformMetrics(
            v_peak=v_peak,
            t_peak=t_peak,
            f_ring=f_ring,
            percent_overshoot=percent_overshoot,
            settling_time=settling_time,
            v_final=v_final,
            t_transition=float(t[idx]),
        )
