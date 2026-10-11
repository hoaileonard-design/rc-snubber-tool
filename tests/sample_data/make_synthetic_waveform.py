"""Sinh file dữ liệu dạng sóng giả lập (damped sinusoid) kiểu LTspice export, dùng để
kiểm thử thủ công Tab 2 (Waveform Survey) với các thông số đã biết trước (Vin, alpha,
omega_d), qua đó so sánh với kết quả WaveformAnalyzer trích xuất được.

Chạy trực tiếp: python tests/sample_data/make_synthetic_waveform.py
"""

import os
import sys

import numpy as np

# Terminal Windows mac dinh dung code page cp1252, khong encode duoc tieng Viet co dau;
# chuyen stdout sang UTF-8 de tranh UnicodeEncodeError khi in thong bao ket qua.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def generate_damped_sinusoid_csv(path: str, Vin: float, v0_overshoot: float,
                                  alpha: float, omega_d: float, pre_time: float,
                                  duration: float, n_points: int, delimiter: str, header: bool):
    """Mô phỏng dạng sóng V_DS thực tế: giữ ở 0V trong lúc MOSFET dẫn (t < pre_time),
    rồi chuyển mạch đột ngột (bậc thang) và dao động tắt dần quanh Vin:

        v(t) = 0                                                          , t < pre_time
        v(t) = Vin + (v0_overshoot - Vin) * exp(-alpha*(t-pre_time)) * cos(omega_d*(t-pre_time)), t >= pre_time

    Cạnh dốc đứng tại t=pre_time mô phỏng đúng thời điểm chuyển mạch (turn-off) để
    WaveformAnalyzer.detect_turnoff_transition (dựa trên |dV/dt| lớn nhất) nhận diện đúng.
    """
    t = np.linspace(0, duration, n_points)
    tau = np.clip(t - pre_time, 0, None)
    ringing = Vin + (v0_overshoot - Vin) * np.exp(-alpha * tau) * np.cos(omega_d * tau)
    v = np.where(t < pre_time, 0.0, ringing)

    with open(path, "w", encoding="utf-8") as f:
        if header:
            f.write(f"time{delimiter}V(vds)\n")
        for ti, vi in zip(t, v):
            f.write(f"{ti:.9e}{delimiter}{vi:.6f}\n")


if __name__ == "__main__":
    out_dir = os.path.dirname(os.path.abspath(__file__))

    # Truoc snubber: dao dong manh, tat dan cham (alpha nho)
    generate_damped_sinusoid_csv(
        path=os.path.join(out_dir, "synthetic_before_snubber.csv"),
        Vin=24.0, v0_overshoot=70.0, alpha=2e6, omega_d=2 * np.pi * 15e6,
        pre_time=0.3e-6, duration=2.3e-6, n_points=600, delimiter=",", header=True,
    )

    # Sau snubber: dao dong yeu hon, tat dan nhanh hon (alpha lon)
    generate_damped_sinusoid_csv(
        path=os.path.join(out_dir, "synthetic_after_snubber.txt"),
        Vin=24.0, v0_overshoot=32.0, alpha=15e6, omega_d=2 * np.pi * 8e6,
        pre_time=0.3e-6, duration=2.3e-6, n_points=600, delimiter="\t", header=True,
    )

    print("Đã sinh file mẫu synthetic_before_snubber.csv và synthetic_after_snubber.txt")
