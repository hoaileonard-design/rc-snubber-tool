"""Hằng số đổi đơn vị và giá trị mặc định cho mạch Buck Converter thử nghiệm.

Nguyên tắc: mọi engine tính toán (app/core/*) chỉ làm việc với đơn vị SI (H, F, Ohm,
s, V, W). Việc quy đổi sang các đơn vị "kỹ thuật" quen thuộc (nH, pF, kHz, mW) chỉ
được thực hiện tại lớp UI, ngay trước khi gọi engine / ngay sau khi nhận kết quả.
"""

# --- Hằng số đổi đơn vị ---
NANO = 1e-9
PICO = 1e-12
KILO = 1e3
MILLI = 1e-3

# --- Giá trị mặc định của mạch Buck Converter thử nghiệm (đơn vị hiển thị trên UI) ---
DEFAULTS = {
    "vin_v": 24.0,
    "fsw_khz": 20.0,
    "duty_percent": 50.0,
    "l1_uh": 100.0,
    "c1_uf": 100.0,
    "rl_ohm": 10.0,
    "l_stray_nh": 67.54,
    "c_oss_pf": 150.0,
    "r_snub_ohm": 12.0,
    "c_snub_pf": 470.0,
    "v_peak_unprotected_v": 70.0,
    "c_multiplier": 2.0,
    "zeta_min": 0.7,
    "target_zeta": 1.0,
    "theta_ja_c_per_w": 150.0,
    "overshoot_ratio_max": 1.05,
    # Vùng quét mặc định cho Tab 3 (Optimizer)
    "r_min_ohm": 1.0,
    "r_max_ohm": 50.0,
    "r_steps": 50,
    "c_min_pf": 100.0,
    "c_max_pf": 2000.0,
    "c_steps": 50,
    "v_target_v": 30.0,
}

APP_TITLE = "RC Snubber Design & Optimization Tool"
APP_GEOMETRY = "1440x900"
