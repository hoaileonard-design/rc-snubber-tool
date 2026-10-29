"""Mô hình vật lý RLC nối tiếp dùng chung cho CalculatorEngine và OptimizerEngine.

Bối cảnh: khi MOSFET tắt, dòng điện ký sinh I0 (đang chạy trong L_stray) bị chuyển
hướng nạp vào tụ ký sinh C_oss của MOSFET, gây dao động (ringing) trên điện áp V_DS.
Khi gắn snubber R_sn nối tiếp C_sn song song với MOSFET, với giả thiết chuẩn
C_sn >> C_oss (snubber áp đảo tụ ký sinh), mạch được xấp xỉ thành một vòng RLC nối
tiếp: L_stray - R_sn - C_sn, kích thích bởi bước nhảy áp 0 -> Vin và dòng cảm ban
đầu I0. Điện áp trên C_sn xấp xỉ chính là V_DS cần khảo sát.

Toàn bộ hàm trong module này dùng đơn vị SI (H, F, Ohm, s, V, A).
"""

import numpy as np

from app.utils.errors import InputValidationError


def undamped_omega(L: float, C: float) -> float:
    """Tần số góc tự nhiên không tắt dần: omega0 = 1/sqrt(L*C)."""
    return 1.0 / np.sqrt(L * C)


def damping_ratio(R: float, C: float, L: float) -> float:
    """Hệ số tắt dần của mạch RLC nối tiếp: zeta = (R/2)*sqrt(C/L)."""
    return (R / 2.0) * np.sqrt(C / L)


def characteristic_impedance(L: float, C: float) -> float:
    """Trở kháng đặc tính: Z0 = sqrt(L/C). Dùng làm giá trị tham chiếu chọn R_sn."""
    return np.sqrt(L / C)


def estimate_drive_current(Vin: float, V_peak_unprotected: float, L: float, C_oss: float) -> float:
    """Ước lượng dòng kích thích I0 từ đỉnh điện áp đo được khi CHƯA có snubber (R=0).

    Khi R=0 (zeta=0, khong tat dan), nghiem la dao dong thuan tuy quanh Vin voi bien do
    B = I0/(C_oss*omega0), nen dinh dien ap la:
        V_peak_unprotected = Vin + sqrt(Vin^2 + B^2)
    Giai nguoc lai:
        I0 = omega0 * C_oss * sqrt((V_peak_unprotected - Vin)^2 - Vin^2)
    Yeu cau V_peak_unprotected >= 2*Vin de bieu thuc duoi can khong am (ve vat ly, tank LC
    phai vot qua it nhat mot lan Vin so voi muc Vin).
    Mo hinh gia dinh MOSFET tat tuc thoi. Buck co driver (P5/P6) tat cham, dinh < 2*Vin: kiem chung
    tren 72 diem LTspice cho sai so V_peak 8 % trung binh, 21 % lon nhat
    (tools/kiem_chung_mo_hinh_rut_gon.py) -> dung bang quet LTspice/do o tab 3 cho truong hop nay.
    """
    if V_peak_unprotected < 2.0 * Vin:
        raise InputValidationError(
            "Mô hình RLC rút gọn (Park/Luo) giả định MOSFET tắt tức thời nên chỉ áp dụng khi đỉnh chưa "
            f"snubber >= 2·Vin (nhận được {V_peak_unprotected:.3g} V < {2 * Vin:.3g} V). Mạch này tắt chậm "
            "(thường do driver/Rg), quá áp do L·di/dt quyết định: hãy chọn R–C từ bảng quét LTspice hoặc "
            "dữ liệu đo ở tab \"3. Tối ưu & kiểm chứng\"."
        )
    omega0 = undamped_omega(L, C_oss)
    inner = (V_peak_unprotected - Vin) ** 2 - Vin ** 2
    return omega0 * C_oss * np.sqrt(inner)


def series_rlc_step_response(t: np.ndarray, Vin: float, I0: float, R: float, C: float, L: float) -> np.ndarray:
    """Tính điện áp Vc(t) trên tụ snubber của mạch RLC nối tiếp, kích thích bởi bước
    nhảy áp 0->Vin và dòng cảm ban đầu I0 (Vc(0)=0, Vc'(0)=I0/C).

    Rẽ 3 nhánh nghiệm tùy theo he so tat dan zeta (< 1: underdamped, ~= 1: critical,
    > 1: overdamped), theo dung ly thuyet mach RLC bac 2 co dien.
    """
    omega0 = undamped_omega(L, C)
    zeta = damping_ratio(R, C, L)
    alpha = zeta * omega0

    if abs(zeta - 1.0) < 1e-6:
        # Tat dan toi han
        A = -Vin
        B = I0 / C - alpha * Vin
        return Vin + np.exp(-alpha * t) * (A + B * t)
    elif zeta < 1.0:
        # Tat dan duoi muc (dao dong tat dan - truong hop thuong gap khi chua/it snubber)
        omega_d = omega0 * np.sqrt(1.0 - zeta ** 2)
        A = -Vin
        B = (I0 / C - alpha * Vin) / omega_d
        return Vin + np.exp(-alpha * t) * (A * np.cos(omega_d * t) + B * np.sin(omega_d * t))
    else:
        # Tat dan qua muc. Viet lai cosh/sinh duoi dang 2 ham mu suy giam rieng biet
        # (r1=alpha-beta, r2=alpha+beta deu > 0) de tranh tran so: cosh/sinh(beta*t) co
        # the vuot qua gioi han float64 voi t lon, trong khi exp(-alpha*t) lai tien ve 0,
        # gay ra 0*inf = nan. Viet theo r1, r2 giu moi so hang bi chan trong (0, 1].
        beta = np.sqrt(alpha ** 2 - omega0 ** 2)
        A = -Vin
        B = (I0 / C - alpha * Vin) / beta
        r1 = alpha - beta  # toc do tat dan cham (cuc gan 0 hon)
        r2 = alpha + beta  # toc do tat dan nhanh (cuc xa 0 hon)
        return Vin + 0.5 * (A + B) * np.exp(-r1 * t) + 0.5 * (A - B) * np.exp(-r2 * t)


def peak_of_response(Vin: float, I0: float, R: float, C: float, L: float,
                      n_periods: float = 5.0, n_samples: int = 800):
    """Tìm V_peak bằng cách lấy mẫu dày Vc(t) trên một khoảng thời gian đủ dài rồi lấy max.

    Cach nay on dinh o ca 3 che do tat dan (khong can giai giai tich phuong trinh
    Vc'(t)=0), de vector hoa cho grid-search, va tra luon duoc mang thoi gian/dien ap
    de ve do thi minh hoa.

    Trả về: (V_peak, t_peak, t_array, v_array)
    """
    omega0 = undamped_omega(L, C)
    zeta = damping_ratio(R, C, L)
    alpha = zeta * omega0

    # Khoang thoi gian khao sat: dinh cua dap ung luon xuat hien som (trong khoang 1 chu ky
    # dau tien doi voi tat dan duoi muc, vi bien do dao dong giam don dieu theo thoi gian).
    # Vi vay KHONG duoc tron lan cong thuc chu ky (omega_d) va cong thuc suy giam (alpha)
    # giua cac che do khac nhau — lam vay se khien mot trong hai gia tri bang 0 (omega_d=0
    # khi zeta>=1, hoac alpha=0 khi zeta=0) lam khoang thoi gian khao sat "no" ra vo cung,
    # lam mat do phan giai dung luc can thiet quanh dinh dap ung.
    if zeta < 1.0:
        # Tat dan duoi muc: dinh dap ung nam trong vai chu ky dao dong dau tien, bat ke
        # toc do tat dan alpha nhanh hay cham.
        omega_d = omega0 * np.sqrt(1.0 - zeta ** 2)
        t_span = n_periods * 2 * np.pi / omega_d
    else:
        # Tat dan toi han/qua muc: khong co dao dong, dinh dap ung (neu co) nam trong
        # khoang vai lan hang so thoi gian tat dan cham nhat (r1 = alpha - beta).
        beta = np.sqrt(alpha ** 2 - omega0 ** 2)
        r1 = alpha - beta
        t_span = n_periods / max(r1, 1e-9 * omega0)

    t_array = np.linspace(0.0, t_span, n_samples)
    v_array = series_rlc_step_response(t_array, Vin, I0, R, C, L)

    i_peak = int(np.argmax(v_array))
    return float(v_array[i_peak]), float(t_array[i_peak]), t_array, v_array


def peak_of_response_grid(Vin: float, I0: float, R_grid: np.ndarray, C_grid: np.ndarray,
                           L: float, n_samples: int = 300) -> np.ndarray:
    """Phiên bản vector hóa của peak_of_response cho lưới (R, C) 2D dùng trong Optimizer.

    R_grid, C_grid: mang 2D cung shape (nR, nC), tao boi np.meshgrid(..., indexing='ij').
    Tra ve: V_peak_grid, shape (nR, nC).
    """
    omega0 = undamped_omega(L, C_grid)
    zeta = damping_ratio(R_grid, C_grid, L)
    alpha = zeta * omega0

    underdamped = zeta < (1.0 - 1e-6)
    critical = np.abs(zeta - 1.0) <= 1e-6
    overdamped = ~underdamped & ~critical

    # Dinh dap ung luon xuat hien som (trong vai chu ky dau tien voi tat dan duoi muc,
    # hoac trong vai lan hang so thoi gian tat dan cham nhat voi tat dan toi han/qua muc).
    # Tinh khoang thoi gian khao sat RIENG cho tung che do, KHONG tron lan cong thuc chu ky
    # va cong thuc suy giam voi nhau (xem giai thich chi tiet trong peak_of_response).
    omega_d_full = omega0 * np.sqrt(np.clip(1.0 - zeta ** 2, 0.0, None))
    beta_full = np.sqrt(np.clip(alpha ** 2 - omega0 ** 2, 0.0, None))
    r1_full = alpha - beta_full  # toc do tat dan cham nhat (chi dung cho critical/overdamped)

    t_span_underdamped = 5.0 * 2 * np.pi / np.maximum(omega_d_full, 1e-30)
    t_span_damped = 5.0 / np.maximum(r1_full, 1e-9 * omega0)
    t_span = np.where(underdamped, t_span_underdamped, t_span_damped)  # shape (nR, nC)

    # Xay truc thoi gian rieng cho tung o luoi bang cach chuan hoa theo t_span, sau do
    # nhan lai: t[i,j,k] = frac[k] * t_span[i,j], voi frac la ti le tuyen tinh 0..1.
    frac = np.linspace(0.0, 1.0, n_samples)  # shape (n_samples,)
    t = t_span[:, :, None] * frac[None, None, :]  # shape (nR, nC, n_samples)

    C3 = C_grid[:, :, None]
    alpha3 = alpha[:, :, None]
    omega0_3 = omega0[:, :, None]
    zeta3 = zeta[:, :, None]

    underdamped3 = zeta3 < (1.0 - 1e-6)
    critical3 = np.abs(zeta3 - 1.0) <= 1e-6
    overdamped3 = ~underdamped3 & ~critical3

    # Nhanh underdamped
    omega_d3 = np.where(underdamped3, omega0_3 * np.sqrt(np.clip(1.0 - zeta3 ** 2, 1e-30, None)), 1e-9)
    A_under = -Vin
    B_under = (I0 / C3 - alpha3 * Vin) / omega_d3
    v_under = Vin + np.exp(-alpha3 * t) * (A_under * np.cos(omega_d3 * t) + B_under * np.sin(omega_d3 * t))

    # Nhanh critical
    A_crit = -Vin
    B_crit = I0 / C3 - alpha3 * Vin
    v_crit = Vin + np.exp(-alpha3 * t) * (A_crit + B_crit * t)

    # Nhanh overdamped: viet cosh/sinh duoi dang 2 ham mu suy giam rieng biet (r1, r2 > 0)
    # de tranh tran so khi t lon (xem giai thich trong series_rlc_step_response).
    beta3 = np.where(overdamped3, np.sqrt(np.clip(alpha3 ** 2 - omega0_3 ** 2, 1e-30, None)), 1e-9)
    A_over = -Vin
    B_over = (I0 / C3 - alpha3 * Vin) / beta3
    r1 = alpha3 - beta3
    r2 = alpha3 + beta3
    v_over = Vin + 0.5 * (A_over + B_over) * np.exp(-r1 * t) + 0.5 * (A_over - B_over) * np.exp(-r2 * t)

    v_array = np.select([underdamped3, critical3, overdamped3], [v_under, v_crit, v_over])
    return np.max(v_array, axis=-1)
