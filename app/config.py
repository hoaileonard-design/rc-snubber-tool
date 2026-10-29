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
    "duty_percent": 50.84926657397271,
    "l1_uh": 220.0,
    "c1_uf": 100.0,
    "rl_ohm": 10.0,
    "l_stray_nh": 100.1205056312364,
    "c_oss_pf": 273.9260217587687,
    "r_snub_ohm": 10.0,
    "c_snub_pf": 4700.0,
    "v_peak_unprotected_v": 38.843482971191406,
    "c_multiplier": 3.0,
    "zeta_min": 0.7,
    "target_zeta": 1.0,
    "theta_ja_c_per_w": 150.0,
    "overshoot_ratio_max": 1.05,
    # Vùng quét mặc định cho Tab 3 (Optimizer)
    "r_min_ohm": 1.0,
    "r_max_ohm": 50.0,
    "r_steps": 50,
    "c_min_pf": 100.0,
    "c_max_pf": 15000.0,
    "c_steps": 50,
    "v_target_v": 28.251,
    # Trọng số tối ưu đa mục tiêu cho Tab 3: công suất, chi phí, kích thước
    "w_power": 1.0,
    "w_cost": 1.0,
    "w_size": 1.0,
}

# --- Hệ số dự phòng khi chọn linh kiện thật cho mạch snubber ---
R_POWER_DERATING = 2.0    # P_rated >= 2 x P_Rsn (yêu cầu an toàn phần cứng trong đề cương)
C_VOLTAGE_DERATING = 1.5  # V_rated của tụ >= 1.5 x V_peak

# --- Danh mục linh kiện thật cho bài toán chi phí/kích thước (Tab 3) ---
# Mỗi danh mục xếp từ nhỏ/rẻ đến lớn/đắt; optimizer chọn linh kiện ĐẦU TIÊN đạt yêu cầu.
# Diện tích = kích thước chiếm chỗ trên mạch (dài x rộng, mm²).
# ponytail: giá là ước lượng tham khảo (VND); cập nhật theo báo giá nơi mua thực tế trước khi đưa vào báo cáo.
# (tên, công suất định mức W, diện tích mm², giá VND)
RESISTOR_PARTS = [
    ("0603 0.1W", 0.1, 1.28, 50),
    ("0805 0.125W", 0.125, 2.5, 50),
    ("1206 0.25W", 0.25, 5.12, 100),
    ("2010 0.75W", 0.75, 12.5, 500),
    ("2512 1W", 1.0, 20.16, 800),
    ("Cắm 2W (oxit kim loại)", 2.0, 52.0, 1500),
    ("Cắm 5W (sứ)", 5.0, 220.0, 4000),
]
# (tên, điện dung tối đa F, điện áp định mức V, diện tích mm², giá VND)
CAPACITOR_PARTS = [
    ("0603 C0G 50V", 1e-9, 50.0, 1.28, 100),
    ("0805 C0G 50V", 4.7e-9, 50.0, 2.5, 200),
    ("1206 C0G 100V", 10e-9, 100.0, 5.12, 500),
    ("Film PP 630V (P5mm)", 100e-9, 630.0, 18.0, 2500),
    ("Film PP 630V (P10mm)", 470e-9, 630.0, 65.0, 5000),
]

APP_TITLE = "RC Snubber Design & Optimization Tool"
APP_GEOMETRY = "1440x900"
TAB_CALCULATOR = "1. Tính R/C khởi đầu"
TAB_WAVEFORM = "2. Phân tích dạng sóng"
TAB_OPTIMIZER = "3. Tối ưu & kiểm chứng"
TAB_CIRCUIT = "4. Mạch tương tác"
