"""Tab 2 - Waveform Survey: đọc file LTspice và phân tích dạng sóng V_DS."""

import os
import math
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure

from app.core.waveform_analyzer import WaveformAnalyzer
from app import config
from app.ui.widgets import ResultRow, LabeledEntry
from app.utils.errors import AppError
from app.utils.validation import parse_float, parse_positive_float


class WaveformTab(ctk.CTkFrame):
    def __init__(self, master, app_ref=None, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.app_ref = app_ref
        self.analyzer = WaveformAnalyzer()

        self.path_a = None
        self.path_b = None
        self.metrics_a = None
        self.metrics_b = None
        self.path_cap = None
        self.parasitics = None
        self.external_context = None
        self.source_note = None

        self.columnconfigure(0, weight=3)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(1, weight=1)

        self._build_toolbar()
        self._build_plot()
        self._build_results_panel()

    def _build_toolbar(self):
        toolbar = ctk.CTkFrame(self, fg_color="transparent")
        toolbar.grid(row=0, column=0, columnspan=2, sticky="ew", padx=10, pady=(10, 5))
        first = ctk.CTkFrame(toolbar, fg_color="transparent")
        first.pack(fill="x", pady=2)
        second = ctk.CTkFrame(toolbar, fg_color="transparent")
        second.pack(fill="x", pady=2)

        self.btn_file_a = ctk.CTkButton(first, text="Chọn file A (trước snubber)", command=self._browse_a)
        self.btn_file_a.pack(side="left", padx=(0, 8))
        self.label_file_a = ctk.CTkLabel(first, text="(chưa chọn file)")
        self.label_file_a.pack(side="left", padx=(0, 20))

        self.btn_file_b = ctk.CTkButton(second, text="Chọn file B (sau snubber, tùy chọn)", command=self._browse_b)
        self.btn_file_b.pack(side="left", padx=(0, 8))
        self.label_file_b = ctk.CTkLabel(second, text="(chưa chọn file)")
        self.label_file_b.pack(side="left", padx=(0, 20))

        self.btn_analyze = ctk.CTkButton(second, text="Phân tích", command=self._on_analyze, fg_color="#2a7d2e")
        self.btn_analyze.pack(side="right")
        ctk.CTkButton(first, text="Thử ngay dữ liệu P6", command=self._load_demo).pack(side="right")

    def _build_plot(self):
        plot_frame = ctk.CTkFrame(self)
        plot_frame.grid(row=1, column=0, sticky="nsew", padx=(10, 5), pady=(0, 10))

        self.figure = Figure(figsize=(7, 5), dpi=100)
        self.ax = self.figure.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.figure, master=plot_frame)
        toolbar_container = ctk.CTkFrame(plot_frame, fg_color="transparent")
        toolbar_container.pack(fill="x")
        self.nav_toolbar = NavigationToolbar2Tk(self.canvas, toolbar_container)
        self.nav_toolbar.update()
        self.canvas.get_tk_widget().pack(fill="both", expand=True)
        self._draw_empty_plot()

    def _draw_empty_plot(self):
        self.ax.clear()
        self.ax.set_title("Dạng sóng V_DS(t)")
        self.ax.set_xlabel("Thời gian (s)")
        self.ax.set_ylabel("V_DS (V)")
        self.ax.grid(True, alpha=0.3)
        self.canvas.draw()

    def _build_results_panel(self):
        results = ctk.CTkScrollableFrame(self, label_text="Kết quả phân tích")
        results.grid(row=1, column=1, sticky="nsew", padx=(5, 10), pady=(0, 10))

        ctk.CTkLabel(results, text="File A (trước)", font=ctk.CTkFont(weight="bold")).pack(anchor="w", pady=(5, 2))
        self.rows_a = {
            "v_peak": ResultRow(results, "V_peak"),
            "f_ring": ResultRow(results, "f_ring"),
            "percent_overshoot": ResultRow(results, "%OS"),
            "settling_time": ResultRow(results, "t_settle"),
            "v_final": ResultRow(results, "V_final"),
            "zeta": ResultRow(results, "ζ (ước lượng)"),
        }
        for w in self.rows_a.values():
            w.pack(fill="x", pady=1)

        ctk.CTkLabel(results, text="File B (sau)", font=ctk.CTkFont(weight="bold")).pack(anchor="w", pady=(15, 2))
        self.rows_b = {
            "v_peak": ResultRow(results, "V_peak"),
            "f_ring": ResultRow(results, "f_ring"),
            "percent_overshoot": ResultRow(results, "%OS"),
            "settling_time": ResultRow(results, "t_settle"),
            "v_final": ResultRow(results, "V_final"),
            "zeta": ResultRow(results, "ζ (ước lượng)"),
        }
        for w in self.rows_b.values():
            w.pack(fill="x", pady=1)

        ctk.CTkLabel(results, text="Một cạnh tăng / cửa sổ tùy chọn", font=ctk.CTkFont(weight="bold")).pack(
            anchor="w", pady=(15, 4))
        self.entry_start = LabeledEntry(results, "Từ (trống = đầu file)", "", "ns")
        self.entry_end = LabeledEntry(results, "Đến (trống = cuối file)", "", "ns")
        self.entry_plateau = LabeledEntry(results, "Plateau (trống = tự ước lượng)", "", "V")
        self.entry_hold = LabeledEntry(results, "Giữ trong dải ±5%", 500, "ns")
        for widget in (self.entry_start, self.entry_end, self.entry_plateau, self.entry_hold):
            widget.pack(fill="x", pady=2)
        ctk.CTkLabel(results, text="Nhận dạng Lp/Cp bằng tụ thử", font=ctk.CTkFont(weight="bold")).pack(
            anchor="w", pady=(15, 4))
        ctk.CTkButton(results, text="Chọn file có thêm tụ thử", command=self._browse_cap).pack(fill="x", pady=3)
        self.label_cap = ctk.CTkLabel(results, text="Chưa chọn; khác file B sau snubber", wraplength=300)
        self.label_cap.pack(fill="x")
        self.entry_added_cap = LabeledEntry(results, "Tụ thử (cùng hai nút)", 470, "pF")
        self.entry_added_cap.pack(fill="x", pady=3)
        self.identification_label = ctk.CTkLabel(results, text="Lp/Cp chưa nhận dạng", justify="left", wraplength=310)
        self.identification_label.pack(fill="x", pady=5)
        self.warning_label = ctk.CTkLabel(results, text="Thời gian theo giây trong file. Chỉ phân tích một cạnh tăng.\n"
            "Plateau tại nút đo không nhất thiết bằng Vin.", wraplength=310, justify="left")
        self.warning_label.pack(fill="x", pady=5)

        btn_frame = ctk.CTkFrame(results, fg_color="transparent")
        btn_frame.pack(fill="x", padx=0, pady=(24, 5))

        self.btn_send_calculator = ctk.CTkButton(
            btn_frame, text="Gửi thông số sang Calculator", fg_color="#1f538d",
            command=self.send_to_calculator,
        )
        self.btn_send_calculator.pack(fill="x", pady=(0, 8))

        self.btn_send_optimizer = ctk.CTkButton(
            btn_frame, text="Gửi thông số sang Optimizer", fg_color="#2ba02b",
            command=self.send_to_optimizer,
        )
        self.btn_send_optimizer.pack(fill="x")

    # ------------------------------------------------------------- Actions
    def _clear_results(self):
        self.metrics_a = self.metrics_b = self.parasitics = None
        for rows in (self.rows_a, self.rows_b):
            for row in rows.values():
                row.set_value("—")
        self.identification_label.configure(text="Lp/Cp chưa nhận dạng; bấm Phân tích sau khi đổi đầu vào.")

    def _load_demo(self):
        self.external_context = self.source_note = None
        example = Path(__file__).resolve().parents[2] / "examples" / "p6_buck"
        self.path_a = str(example / "before.csv")
        self.path_b = str(example / "after_RC.csv")
        self.path_cap = str(example / "with_470pF.csv")
        self.label_file_a.configure(text="before.csv (P6)")
        self.label_file_b.configure(text="after_RC.csv (P6)")
        self.label_cap.configure(text="with_470pF.csv (P6)")
        self.entry_start.set("")
        self.entry_end.set("")
        self.entry_plateau.set(24.55164337158203)
        self.entry_added_cap.set(470)
        self.entry_hold.set(500)
        self._on_analyze()

    def _browse_a(self):
        path = filedialog.askopenfilename(
            title="Chọn file dạng sóng A (trước snubber)",
            filetypes=[("Data files", "*.txt *.csv"), ("All files", "*.*")],
        )
        if path:
            self.path_a = path
            self.external_context = self.source_note = None
            self._clear_results()
            self.label_file_a.configure(text=os.path.basename(path))

    def _browse_b(self):
        path = filedialog.askopenfilename(
            title="Chọn file dạng sóng B (sau snubber)",
            filetypes=[("Data files", "*.txt *.csv"), ("All files", "*.*")],
        )
        if path:
            self.path_b = path
            self.external_context = self.source_note = None
            self._clear_results()
            self.label_file_b.configure(text=os.path.basename(path))

    def _browse_cap(self):
        path = filedialog.askopenfilename(title="Cùng mạch và điều kiện, chỉ thêm tụ thử song song",
                                          filetypes=[("Dạng sóng", "*.txt *.csv")])
        if path:
            self.path_cap = path
            self.external_context = self.source_note = None
            self._clear_results()
            self.label_cap.configure(text=os.path.basename(path))

    def _on_analyze(self):
        if not self.path_a and not self.path_b:
            messagebox.showinfo("Chưa chọn file", "Hãy chọn ít nhất file A để phân tích.")
            return

        self.ax.clear()
        self._clear_results()
        any_plotted = False
        try:
            options = {name: parse_float(entry.get(), name) * 1e-9 if entry.get().strip() else None
                       for name, entry in (("start", self.entry_start), ("end", self.entry_end))}
            options["plateau"] = parse_positive_float(self.entry_plateau.get(), "Plateau") if self.entry_plateau.get().strip() else None
            options["settling_hold"] = parse_positive_float(self.entry_hold.get(), "Thời gian giữ") * 1e-9
            if self.path_a:
                t_a, v_a = self.analyzer.load_file(self.path_a)
                metrics_a = self.analyzer.analyze(t_a, v_a, **options)
                self.metrics_a = metrics_a
                self._fill_result_rows(self.rows_a, metrics_a)
                self.ax.plot(t_a, v_a, label="Trước snubber", color="#d62728")
                self.ax.plot(metrics_a.t_peak, metrics_a.v_peak, "ro", markersize=8)
                self.ax.annotate(
                    f"V_peak={metrics_a.v_peak:.2f}V", (metrics_a.t_peak, metrics_a.v_peak),
                    textcoords="offset points", xytext=(8, 8), color="#d62728",
                )
                any_plotted = True

            if self.path_b:
                t_b, v_b = self.analyzer.load_file(self.path_b)
                metrics_b = self.analyzer.analyze(t_b, v_b, **options)
                self.metrics_b = metrics_b
                self._fill_result_rows(self.rows_b, metrics_b)
                self.ax.plot(t_b, v_b, label="Sau snubber", color="#2ca02c")
                self.ax.plot(metrics_b.t_peak, metrics_b.v_peak, "ro", markersize=8)
                self.ax.annotate(
                    f"V_peak={metrics_b.v_peak:.2f}V", (metrics_b.t_peak, metrics_b.v_peak),
                    textcoords="offset points", xytext=(8, -14), color="#2ca02c",
                )
                any_plotted = True

            if self.path_cap and self.metrics_a:
                t_cap, v_cap = self.analyzer.load_file(self.path_cap)
                cap_metrics = self.analyzer.analyze(t_cap, v_cap, **options)
                added_cap = parse_positive_float(self.entry_added_cap.get(), "Tụ thử") * 1e-12
                self.parasitics = self.analyzer.identify_parasitics(self.metrics_a, cap_metrics, added_cap)
                p = self.parasitics
                self.identification_label.configure(text=f"f0 = {p.f0_Hz/1e6:.4f} MHz; f1 = {p.f1_Hz/1e6:.4f} MHz\n"
                    f"Lp ≈ {p.Lp_H/1e-9:.3f} nH; Cp ≈ {p.Cp_F/1e-12:.3f} pF\n"
                    f"Khởi đầu: {p.R_start_ohm:.3f} Ω / {p.C_start_F/1e-12:.2f} pF\n" + "\n".join(p.warnings))
                self.ax.plot(t_cap, v_cap, label="Có tụ thử", alpha=0.55)
            messages = [warning for m in (self.metrics_a, self.metrics_b) if m for warning in m.warnings]
            if self.source_note:
                messages.insert(0, self.source_note)
            self.warning_label.configure(text="\n".join(dict.fromkeys(messages)))

            self.ax.set_title("Dạng sóng V_DS(t)")
            self.ax.set_xlabel("Thời gian (s)")
            self.ax.set_ylabel("V_DS (V)")
            self.ax.grid(True, alpha=0.3)
            if any_plotted:
                self.ax.legend()
            self.canvas.draw()

        except AppError as exc:
            self._clear_results()
            messagebox.showerror("Lỗi phân tích dạng sóng", str(exc))
            self._draw_empty_plot()
        except Exception as exc:  # bat them loi khong luong truoc duoc tu pandas/scipy
            self._clear_results()
            messagebox.showerror("Lỗi phân tích dạng sóng", f"Đã xảy ra lỗi không mong muốn: {exc}")
            self._draw_empty_plot()

    @staticmethod
    def _fill_result_rows(rows: dict, metrics) -> None:
        rows["v_peak"].set_value(f"{metrics.v_peak:.4f} V")
        rows["f_ring"].set_value(f"{metrics.f_ring / 1e6:.4f} MHz" if math.isfinite(metrics.f_ring) else "Chưa nhận dạng")
        rows["percent_overshoot"].set_value(f"{metrics.percent_overshoot:.2f} %")
        rows["settling_time"].set_value("Chưa xác lập" if metrics.settling_censored else f"{metrics.settling_time * 1e9:.2f} ns (±5%)")
        rows["v_final"].set_value(f"{metrics.v_final:.4f} V")
        rows["zeta"].set_value(f"{metrics.zeta:.5f}" if math.isfinite(metrics.zeta) else "Chưa nhận dạng")

    def _identified_params(self):
        params = {"V_peak_unprotected": self.metrics_a.v_peak}
        if self.parasitics:
            params.update(L_stray_H=self.parasitics.Lp_H, C_oss_F=self.parasitics.Cp_F)
        return params

    def send_to_calculator(self):
        """Gửi V_peak và V_in đo được từ File A sang Tab 1 (Calculator)."""
        if self.metrics_a is None:
            messagebox.showwarning(
                "Chưa có dữ liệu",
                "Hãy chọn file A (trước snubber) và bấm 'Phân tích' trước khi gửi thông số sang Calculator.",
            )
            return

        if self.app_ref is None:
            return
        try:
            self.app_ref.calculator_tab.load_waveform_params(self._identified_params())
            self.app_ref.tabview.set(config.TAB_CALCULATOR)
        except AttributeError as exc:
            messagebox.showerror("Lỗi", f"Không thể gửi thông số sang Calculator: {exc}")

    def send_to_optimizer(self):
        """Gửi V_peak và V_in đo được từ File A sang Tab 3 (Optimizer)."""
        if self.metrics_a is None:
            messagebox.showwarning(
                "Chưa có dữ liệu",
                "Hãy chọn file A (trước snubber) và bấm 'Phân tích' trước khi gửi thông số sang Optimizer.",
            )
            return

        if self.app_ref is None:
            return
        try:
            self.app_ref.push_params_to_optimizer(self._identified_params())
        except AttributeError as exc:
            messagebox.showerror("Lỗi", f"Không thể gửi thông số sang Optimizer: {exc}")
