"""Tab 1 - Calculator: tính toán lý thuyết R_snub, C_snub theo 3 phương pháp."""

from tkinter import messagebox

import customtkinter as ctk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from app import config
from app.core.calculator_engine import CalculatorEngine
from app.ui.widgets import LabeledEntry, ResultRow
from app.utils.errors import AppError
from app.utils.validation import parse_positive_float, parse_float

METHODS = ["Standard Hart/Erickson", "Luo et al. (RC-Map)", "Park et al. (Transient)"]


class CalculatorTab(ctk.CTkFrame):
    def __init__(self, master, app_ref=None, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.app_ref = app_ref
        self.engine = CalculatorEngine()
        self.last_result = None

        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        self._build_left_panel()
        self._build_right_panel()

    # ------------------------------------------------------------------ UI
    def _build_left_panel(self):
        left = ctk.CTkScrollableFrame(self, label_text="Thông số đầu vào")
        left.grid(row=0, column=0, sticky="nsew", padx=(10, 5), pady=10)

        d = config.DEFAULTS
        self.entry_vin = LabeledEntry(left, "Điện áp vào Vin", d["vin_v"], "V")
        self.entry_fsw = LabeledEntry(left, "Tần số đóng cắt fsw", d["fsw_khz"], "kHz")
        self.entry_lstray = LabeledEntry(left, "Điện cảm ký sinh L_stray", d["l_stray_nh"], "nH")
        self.entry_coss = LabeledEntry(left, "Điện dung ký sinh C_oss", d["c_oss_pf"], "pF")
        self.entry_vpeak_unprot = LabeledEntry(left, "V_peak chưa có snubber", d["v_peak_unprotected_v"], "V")
        for w in (self.entry_vin, self.entry_fsw, self.entry_lstray, self.entry_coss, self.entry_vpeak_unprot):
            w.pack(fill="x", pady=3)

        ctk.CTkLabel(left, text="Phương pháp tính", font=ctk.CTkFont(weight="bold")).pack(
            anchor="w", pady=(15, 4)
        )
        self.method_selector = ctk.CTkSegmentedButton(
            left, values=METHODS, command=self._on_method_change
        )
        self.method_selector.set(METHODS[0])
        self.method_selector.pack(fill="x", pady=(0, 10))

        self.method_params_frame = ctk.CTkFrame(left, fg_color="transparent")
        self.method_params_frame.pack(fill="x", pady=(0, 10))
        self._build_method_param_widgets()
        self._on_method_change(METHODS[0])

        self.calc_button = ctk.CTkButton(left, text="Tính toán", command=self._on_calculate)
        self.calc_button.pack(fill="x", pady=(10, 5))

        self.send_button = ctk.CTkButton(
            left, text="Gửi sang Optimizer", command=self._on_send_to_optimizer, fg_color="gray40"
        )
        self.send_button.pack(fill="x", pady=(0, 5))

    def _build_method_param_widgets(self):
        d = config.DEFAULTS
        # Hart & Luo dung chung tham so c_multiplier
        self.entry_c_multiplier = LabeledEntry(self.method_params_frame, "Hệ số nhân C_sn/C_oss", d["c_multiplier"], "x")
        self.entry_zeta_min = LabeledEntry(self.method_params_frame, "Hệ số tắt dần tối thiểu (zeta_min)", d["zeta_min"], "")
        # Park
        self.entry_target_zeta = LabeledEntry(self.method_params_frame, "Hệ số tắt dần mục tiêu (zeta)", d["target_zeta"], "")
        self.entry_theta_ja = LabeledEntry(self.method_params_frame, "Trở nhiệt theta_JA", d["theta_ja_c_per_w"], "°C/W")
        self.entry_overshoot_max = LabeledEntry(self.method_params_frame, "Tỉ lệ vượt lố tối đa (x Vin)", d["overshoot_ratio_max"], "")

    def _on_method_change(self, selected_method: str):
        for w in self.method_params_frame.winfo_children():
            w.pack_forget()
        if selected_method == METHODS[0]:  # Hart/Erickson
            self.entry_c_multiplier.pack(fill="x", pady=3)
        elif selected_method == METHODS[1]:  # Luo
            self.entry_c_multiplier.pack(fill="x", pady=3)
            self.entry_zeta_min.pack(fill="x", pady=3)
        else:  # Park
            self.entry_target_zeta.pack(fill="x", pady=3)
            self.entry_theta_ja.pack(fill="x", pady=3)
            self.entry_overshoot_max.pack(fill="x", pady=3)

    def _build_right_panel(self):
        right = ctk.CTkFrame(self)
        right.grid(row=0, column=1, sticky="nsew", padx=(5, 10), pady=10)
        right.rowconfigure(1, weight=1)
        right.columnconfigure(0, weight=1)

        results_frame = ctk.CTkFrame(right)
        results_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        ctk.CTkLabel(results_frame, text="Kết quả tính toán", font=ctk.CTkFont(weight="bold", size=14)).pack(
            anchor="w", padx=10, pady=(10, 5)
        )
        self.result_r = ResultRow(results_frame, "R_snub")
        self.result_c = ResultRow(results_frame, "C_snub")
        self.result_p = ResultRow(results_frame, "P_Rsnub")
        self.result_dt = ResultRow(results_frame, "ΔT (nhiệt độ tăng)")
        for w in (self.result_r, self.result_c, self.result_p, self.result_dt):
            w.pack(fill="x", padx=10, pady=2)

        self.recommend_box = ctk.CTkTextbox(results_frame, height=70, wrap="word")
        self.recommend_box.pack(fill="x", padx=10, pady=(8, 10))
        self.recommend_box.configure(state="disabled")

        # Do thi minh hoa dang song damped tai diem tinh duoc
        plot_frame = ctk.CTkFrame(right)
        plot_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.figure = Figure(figsize=(5, 3.5), dpi=100)
        self.ax = self.figure.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.figure, master=plot_frame)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)
        self._draw_empty_plot()

    def _draw_empty_plot(self):
        self.ax.clear()
        self.ax.set_title("Dạng sóng V_DS ước tính (sau khi tính toán)")
        self.ax.set_xlabel("Thời gian (s)")
        self.ax.set_ylabel("V_DS (V)")
        self.ax.grid(True, alpha=0.3)
        self.canvas.draw()

    # ------------------------------------------------------------- Actions
    def _read_common_inputs(self):
        vin = parse_positive_float(self.entry_vin.get(), "Vin")
        fsw_hz = parse_positive_float(self.entry_fsw.get(), "fsw") * config.KILO
        l_stray_h = parse_positive_float(self.entry_lstray.get(), "L_stray") * config.NANO
        c_oss_f = parse_positive_float(self.entry_coss.get(), "C_oss") * config.PICO
        v_peak_unprot = parse_positive_float(self.entry_vpeak_unprot.get(), "V_peak_unprotected")
        return vin, fsw_hz, l_stray_h, c_oss_f, v_peak_unprot

    def _on_calculate(self):
        try:
            vin, fsw_hz, l_stray_h, c_oss_f, v_peak_unprot = self._read_common_inputs()
            method = self.method_selector.get()

            if method == METHODS[0]:
                c_mult = parse_positive_float(self.entry_c_multiplier.get(), "Hệ số nhân C_sn/C_oss")
                result = self.engine.method_hart_erickson(vin, fsw_hz, l_stray_h, c_oss_f, c_mult)
            elif method == METHODS[1]:
                c_mult = parse_positive_float(self.entry_c_multiplier.get(), "Hệ số nhân C_sn/C_oss")
                zeta_min = parse_positive_float(self.entry_zeta_min.get(), "zeta_min")
                result = self.engine.method_luo_rcmap(
                    vin, v_peak_unprot, fsw_hz, l_stray_h, c_oss_f, c_mult, zeta_min
                )
            else:
                target_zeta = parse_positive_float(self.entry_target_zeta.get(), "zeta mục tiêu")
                theta_ja = parse_positive_float(self.entry_theta_ja.get(), "theta_JA")
                overshoot_max = parse_float(self.entry_overshoot_max.get(), "Tỉ lệ vượt lố tối đa")
                result = self.engine.method_park_transient(
                    vin, v_peak_unprot, fsw_hz, l_stray_h, c_oss_f, target_zeta, theta_ja, overshoot_max
                )

            self._display_result(result, vin, fsw_hz, l_stray_h, c_oss_f, v_peak_unprot)
            self.last_result = {
                "R_sn": result["R_sn"], "C_sn": result["C_sn"], "Vin": vin, "fsw_Hz": fsw_hz,
                "L_stray_H": l_stray_h, "C_oss_F": c_oss_f, "V_peak_unprotected": v_peak_unprot,
            }
        except AppError as exc:
            messagebox.showerror("Lỗi tính toán", str(exc))
        except (ValueError, ZeroDivisionError) as exc:
            messagebox.showerror("Lỗi tính toán", f"Đã xảy ra lỗi khi tính toán: {exc}")

    def _display_result(self, result, vin, fsw_hz, l_stray_h, c_oss_f, v_peak_unprot):
        r_sn = result["R_sn"]
        c_sn = result["C_sn"]
        p_rsn = result["P_Rsn"]
        delta_t = result.get("delta_T_C")

        self.result_r.set_value(f"{r_sn:.3f} Ω")
        self.result_c.set_value(f"{c_sn / config.PICO:.2f} pF")
        self.result_p.set_value(f"{p_rsn / config.MILLI:.4f} mW")
        self.result_dt.set_value(f"{delta_t:.2f} °C" if delta_t is not None else "— (không áp dụng)")

        recommendation = self.engine.recommend_component(p_rsn, vin)
        self.recommend_box.configure(state="normal")
        self.recommend_box.delete("1.0", "end")
        self.recommend_box.insert("1.0", recommendation)
        self.recommend_box.configure(state="disabled")

        # Ve dang song minh hoa: dung cung mo hinh RLC voi I0 uoc luong tu V_peak_unprotected
        from app.core import rlc_model
        try:
            i0 = rlc_model.estimate_drive_current(vin, v_peak_unprot, l_stray_h, c_oss_f)
            _, _, t_arr, v_arr = rlc_model.peak_of_response(vin, i0, r_sn, c_sn, l_stray_h)
            self.ax.clear()
            self.ax.plot(t_arr * 1e9, v_arr, color="#1f77b4")
            self.ax.axhline(vin, color="gray", linestyle="--", linewidth=1, label="Vin")
            self.ax.set_title("Dạng sóng V_DS ước tính sau khi lắp snubber")
            self.ax.set_xlabel("Thời gian (ns)")
            self.ax.set_ylabel("V_DS (V)")
            self.ax.grid(True, alpha=0.3)
            self.ax.legend()
            self.canvas.draw()
        except AppError:
            self._draw_empty_plot()

    def _on_send_to_optimizer(self):
        if self.last_result is None:
            messagebox.showinfo("Chưa có kết quả", "Hãy bấm 'Tính toán' trước khi gửi sang Optimizer.")
            return
        if self.app_ref is not None:
            self.app_ref.push_params_to_optimizer(self.last_result)
            messagebox.showinfo("Đã gửi", "Đã gửi thông số sang tab Optimization & RC-Map.")

    def load_params_from_dict(self, params: dict):
        """Nhận cặp (R_sn, C_sn) tối ưu từ OptimizerTab để hiển thị lại kết quả/dạng
        sóng minh họa trên tab Calculator, dùng các thông số mạch hiện có trên tab này
        (Vin, fsw, L_stray, C_oss, V_peak_unprotected) để kiểm chứng chéo."""
        if "R_sn" not in params or "C_sn" not in params:
            return
        try:
            vin, fsw_hz, l_stray_h, c_oss_f, v_peak_unprot = self._read_common_inputs()
        except AppError as exc:
            messagebox.showerror("Lỗi", f"Không thể hiển thị kết quả từ Optimizer: {exc}")
            return

        r_sn = params["R_sn"]
        c_sn = params["C_sn"]
        p_rsn = c_sn * vin ** 2 * fsw_hz
        result = {"R_sn": r_sn, "C_sn": c_sn, "P_Rsn": p_rsn, "delta_T_C": None}
        self._display_result(result, vin, fsw_hz, l_stray_h, c_oss_f, v_peak_unprot)
        self.last_result = {
            "R_sn": r_sn, "C_sn": c_sn, "Vin": vin, "fsw_Hz": fsw_hz,
            "L_stray_H": l_stray_h, "C_oss_F": c_oss_f, "V_peak_unprotected": v_peak_unprot,
        }
