"""Tab 3 - Optimization & RC-Map Engine: quét lưới (R,C) và vẽ bản đồ tối ưu."""

from tkinter import messagebox

import customtkinter as ctk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure

from app import config
from app.core.optimizer_engine import OptimizerEngine
from app.ui.widgets import LabeledEntry, ResultRow
from app.utils.errors import AppError
from app.utils.validation import parse_positive_float, parse_int_positive


class OptimizerTab(ctk.CTkFrame):
    def __init__(self, master, app_ref=None, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.app_ref = app_ref
        self.engine = OptimizerEngine()
        self.last_result = None

        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=3)
        self.rowconfigure(0, weight=1)

        self._build_left_panel()
        self._build_plot_panel()

    def _build_left_panel(self):
        left = ctk.CTkScrollableFrame(self, label_text="Thông số quét & mục tiêu")
        left.grid(row=0, column=0, sticky="nsew", padx=(10, 5), pady=10)

        d = config.DEFAULTS
        ctk.CTkLabel(left, text="Vùng quét R_snub", font=ctk.CTkFont(weight="bold")).pack(anchor="w", pady=(0, 4))
        self.entry_r_min = LabeledEntry(left, "R_min", d["r_min_ohm"], "Ω")
        self.entry_r_max = LabeledEntry(left, "R_max", d["r_max_ohm"], "Ω")
        self.entry_r_steps = LabeledEntry(left, "Số bước R", d["r_steps"], "")
        for w in (self.entry_r_min, self.entry_r_max, self.entry_r_steps):
            w.pack(fill="x", pady=3)

        ctk.CTkLabel(left, text="Vùng quét C_snub", font=ctk.CTkFont(weight="bold")).pack(anchor="w", pady=(15, 4))
        self.entry_c_min = LabeledEntry(left, "C_min", d["c_min_pf"], "pF")
        self.entry_c_max = LabeledEntry(left, "C_max", d["c_max_pf"], "pF")
        self.entry_c_steps = LabeledEntry(left, "Số bước C", d["c_steps"], "")
        for w in (self.entry_c_min, self.entry_c_max, self.entry_c_steps):
            w.pack(fill="x", pady=3)

        ctk.CTkLabel(left, text="Thông số mạch", font=ctk.CTkFont(weight="bold")).pack(anchor="w", pady=(15, 4))
        self.entry_vin = LabeledEntry(left, "Vin", d["vin_v"], "V")
        self.entry_fsw = LabeledEntry(left, "fsw", d["fsw_khz"], "kHz")
        self.entry_lstray = LabeledEntry(left, "L_stray", d["l_stray_nh"], "nH")
        self.entry_coss = LabeledEntry(left, "C_oss", d["c_oss_pf"], "pF")
        self.entry_vpeak_unprot = LabeledEntry(left, "V_peak chưa có snubber", d["v_peak_unprotected_v"], "V")
        for w in (self.entry_vin, self.entry_fsw, self.entry_lstray, self.entry_coss, self.entry_vpeak_unprot):
            w.pack(fill="x", pady=3)

        ctk.CTkLabel(left, text="Mục tiêu", font=ctk.CTkFont(weight="bold")).pack(anchor="w", pady=(15, 4))
        self.entry_v_target = LabeledEntry(left, "V_target (đỉnh cho phép tối đa)", d["v_target_v"], "V")
        self.entry_v_target.pack(fill="x", pady=3)

        self.run_button = ctk.CTkButton(left, text="Chạy tối ưu", command=self._on_run_optimization)
        self.run_button.pack(fill="x", pady=(15, 5))

        self.send_button = ctk.CTkButton(
            left, text="Gửi sang Calculator", command=self._on_send_to_calculator, fg_color="gray40"
        )
        self.send_button.pack(fill="x", pady=(0, 5))

        results_frame = ctk.CTkFrame(left)
        results_frame.pack(fill="x", pady=(15, 5))
        ctk.CTkLabel(results_frame, text="Kết quả tối ưu", font=ctk.CTkFont(weight="bold")).pack(
            anchor="w", padx=10, pady=(10, 5)
        )
        self.result_r_opt = ResultRow(results_frame, "R_opt")
        self.result_c_opt = ResultRow(results_frame, "C_opt")
        self.result_p_opt = ResultRow(results_frame, "P_loss_opt")
        self.result_v_opt = ResultRow(results_frame, "V_peak_opt")
        self.result_n_feasible = ResultRow(results_frame, "Số điểm khả thi")
        for w in (self.result_r_opt, self.result_c_opt, self.result_p_opt, self.result_v_opt, self.result_n_feasible):
            w.pack(fill="x", padx=10, pady=2)
        ctk.CTkFrame(results_frame, fg_color="transparent", height=8).pack()

    def _build_plot_panel(self):
        plot_frame = ctk.CTkFrame(self)
        plot_frame.grid(row=0, column=1, sticky="nsew", padx=(5, 10), pady=10)

        self.figure = Figure(figsize=(9, 6), dpi=100)
        self.ax_vpeak = self.figure.add_subplot(1, 2, 1)
        self.ax_ploss = self.figure.add_subplot(1, 2, 2)
        self.canvas = FigureCanvasTkAgg(self.figure, master=plot_frame)
        toolbar_container = ctk.CTkFrame(plot_frame, fg_color="transparent")
        toolbar_container.pack(fill="x")
        self.nav_toolbar = NavigationToolbar2Tk(self.canvas, toolbar_container)
        self.nav_toolbar.update()
        self.canvas.get_tk_widget().pack(fill="both", expand=True)
        self._draw_empty_plot()

    def _draw_empty_plot(self):
        self.ax_vpeak.clear()
        self.ax_vpeak.set_title("RC-Map: V_peak (V)")
        self.ax_vpeak.set_xlabel("R_snub (Ω)")
        self.ax_vpeak.set_ylabel("C_snub (pF)")
        self.ax_ploss.clear()
        self.ax_ploss.set_title("RC-Map: P_loss (mW)")
        self.ax_ploss.set_xlabel("R_snub (Ω)")
        self.ax_ploss.set_ylabel("C_snub (pF)")
        self.figure.tight_layout()
        self.canvas.draw()

    def _on_run_optimization(self):
        try:
            r_min = parse_positive_float(self.entry_r_min.get(), "R_min")
            r_max = parse_positive_float(self.entry_r_max.get(), "R_max")
            r_steps = parse_int_positive(self.entry_r_steps.get(), "Số bước R")
            c_min = parse_positive_float(self.entry_c_min.get(), "C_min") * config.PICO
            c_max = parse_positive_float(self.entry_c_max.get(), "C_max") * config.PICO
            c_steps = parse_int_positive(self.entry_c_steps.get(), "Số bước C")

            if r_max <= r_min:
                raise AppError("R_max phải lớn hơn R_min.")
            if c_max <= c_min:
                raise AppError("C_max phải lớn hơn C_min.")

            vin = parse_positive_float(self.entry_vin.get(), "Vin")
            fsw_hz = parse_positive_float(self.entry_fsw.get(), "fsw") * config.KILO
            l_stray_h = parse_positive_float(self.entry_lstray.get(), "L_stray") * config.NANO
            c_oss_f = parse_positive_float(self.entry_coss.get(), "C_oss") * config.PICO
            v_peak_unprot = parse_positive_float(self.entry_vpeak_unprot.get(), "V_peak_unprotected")
            v_target = parse_positive_float(self.entry_v_target.get(), "V_target")

            result = self.engine.run_full_sweep(
                R_min=r_min, R_max=r_max, R_steps=r_steps,
                C_min=c_min, C_max=c_max, C_steps=c_steps,
                Vin=vin, fsw_Hz=fsw_hz, L_stray_H=l_stray_h, C_oss_F=c_oss_f,
                V_target=v_target, V_peak_unprotected=v_peak_unprot,
            )
            self.last_result = result
            self._display_result(result, v_target)

        except AppError as exc:
            messagebox.showerror("Lỗi tối ưu hóa", str(exc))
        except (ValueError, ZeroDivisionError) as exc:
            messagebox.showerror("Lỗi tối ưu hóa", f"Đã xảy ra lỗi khi tối ưu hóa: {exc}")

    def _display_result(self, result, v_target: float):
        self.result_r_opt.set_value(f"{result.R_opt:.3f} Ω")
        self.result_c_opt.set_value(f"{result.C_opt / config.PICO:.2f} pF")
        self.result_p_opt.set_value(f"{result.P_loss_opt / config.MILLI:.4f} mW")
        self.result_v_opt.set_value(f"{result.V_peak_opt:.3f} V")
        self.result_n_feasible.set_value(f"{result.n_feasible} / {result.n_total}")

        RR = result.R_grid
        CC_pf = result.C_grid / config.PICO

        self.ax_vpeak.clear()
        contour = self.ax_vpeak.contourf(RR, CC_pf, result.V_peak_grid, levels=20, cmap="viridis")
        self.figure.colorbar(contour, ax=self.ax_vpeak, label="V_peak (V)")
        # Vien phan tach vung kha thi (V_peak = V_target)
        try:
            self.ax_vpeak.contour(RR, CC_pf, result.V_peak_grid, levels=[v_target], colors="black", linewidths=2)
        except ValueError:
            pass  # V_target nam ngoai khoang gia tri cua luoi, khong ve duoc duong vien
        # To xanh "Green Zone" vung kha thi
        self.ax_vpeak.contourf(
            RR, CC_pf, result.feasible_mask.astype(float), levels=[0.5, 1.5],
            colors=["limegreen"], alpha=0.35,
        )
        self.ax_vpeak.plot(result.R_opt, result.C_opt / config.PICO, marker="*", color="red", markersize=18)
        self.ax_vpeak.annotate(
            f"({result.R_opt:.2f}Ω, {result.C_opt / config.PICO:.1f}pF)",
            (result.R_opt, result.C_opt / config.PICO), textcoords="offset points", xytext=(10, 10), color="red",
        )
        self.ax_vpeak.set_title("RC-Map: V_peak (V) — vùng xanh là khả thi")
        self.ax_vpeak.set_xlabel("R_snub (Ω)")
        self.ax_vpeak.set_ylabel("C_snub (pF)")

        self.ax_ploss.clear()
        contour2 = self.ax_ploss.contourf(RR, CC_pf, result.P_loss_grid / config.MILLI, levels=20, cmap="plasma")
        self.figure.colorbar(contour2, ax=self.ax_ploss, label="P_loss (mW)")
        self.ax_ploss.plot(result.R_opt, result.C_opt / config.PICO, marker="*", color="cyan", markersize=18)
        self.ax_ploss.set_title("RC-Map: P_loss (mW)")
        self.ax_ploss.set_xlabel("R_snub (Ω)")
        self.ax_ploss.set_ylabel("C_snub (pF)")

        self.figure.tight_layout()
        self.canvas.draw()

    def _on_send_to_calculator(self):
        if self.last_result is None:
            messagebox.showinfo("Chưa có kết quả", "Hãy bấm 'Chạy tối ưu' trước khi gửi sang Calculator.")
            return
        if self.app_ref is not None:
            self.app_ref.push_params_to_calculator({
                "R_sn": self.last_result.R_opt,
                "C_sn": self.last_result.C_opt,
            })
            messagebox.showinfo("Đã gửi", "Đã gửi (R_opt, C_opt) sang tab Calculator.")

    def load_params_from_dict(self, params: dict):
        """Nhận thông số từ CalculatorTab (qua SnubberApp.push_params_to_optimizer)."""
        if "Vin" in params:
            self.entry_vin.set(params["Vin"])
        if "fsw_Hz" in params:
            self.entry_fsw.set(params["fsw_Hz"] / config.KILO)
        if "L_stray_H" in params:
            self.entry_lstray.set(params["L_stray_H"] / config.NANO)
        if "C_oss_F" in params:
            self.entry_coss.set(params["C_oss_F"] / config.PICO)
        if "V_peak_unprotected" in params:
            self.entry_vpeak_unprot.set(params["V_peak_unprotected"])
