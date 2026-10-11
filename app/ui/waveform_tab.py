"""Tab 2 - Waveform Survey: đọc file LTspice và phân tích dạng sóng V_DS."""

import os
from tkinter import filedialog, messagebox

import customtkinter as ctk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure

from app.core.waveform_analyzer import WaveformAnalyzer
from app.ui.widgets import ResultRow
from app.utils.errors import AppError


class WaveformTab(ctk.CTkFrame):
    def __init__(self, master, app_ref=None, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.app_ref = app_ref
        self.analyzer = WaveformAnalyzer()

        self.path_a = None
        self.path_b = None
        self.metrics_a = None
        self.metrics_b = None

        self.columnconfigure(0, weight=3)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(1, weight=1)

        self._build_toolbar()
        self._build_plot()
        self._build_results_panel()

    def _build_toolbar(self):
        toolbar = ctk.CTkFrame(self, fg_color="transparent")
        toolbar.grid(row=0, column=0, columnspan=2, sticky="ew", padx=10, pady=(10, 5))

        self.btn_file_a = ctk.CTkButton(toolbar, text="Chọn file A (trước snubber)", command=self._browse_a)
        self.btn_file_a.pack(side="left", padx=(0, 8))
        self.label_file_a = ctk.CTkLabel(toolbar, text="(chưa chọn file)")
        self.label_file_a.pack(side="left", padx=(0, 20))

        self.btn_file_b = ctk.CTkButton(toolbar, text="Chọn file B (sau snubber, tùy chọn)", command=self._browse_b)
        self.btn_file_b.pack(side="left", padx=(0, 8))
        self.label_file_b = ctk.CTkLabel(toolbar, text="(chưa chọn file)")
        self.label_file_b.pack(side="left", padx=(0, 20))

        self.btn_analyze = ctk.CTkButton(toolbar, text="Phân tích", command=self._on_analyze, fg_color="#2a7d2e")
        self.btn_analyze.pack(side="left")

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
        }
        for w in self.rows_b.values():
            w.pack(fill="x", pady=1)

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
    def _browse_a(self):
        path = filedialog.askopenfilename(
            title="Chọn file dạng sóng A (trước snubber)",
            filetypes=[("Data files", "*.txt *.csv"), ("All files", "*.*")],
        )
        if path:
            self.path_a = path
            self.label_file_a.configure(text=os.path.basename(path))

    def _browse_b(self):
        path = filedialog.askopenfilename(
            title="Chọn file dạng sóng B (sau snubber)",
            filetypes=[("Data files", "*.txt *.csv"), ("All files", "*.*")],
        )
        if path:
            self.path_b = path
            self.label_file_b.configure(text=os.path.basename(path))

    def _on_analyze(self):
        if not self.path_a and not self.path_b:
            messagebox.showinfo("Chưa chọn file", "Hãy chọn ít nhất file A để phân tích.")
            return

        self.ax.clear()
        any_plotted = False
        try:
            if self.path_a:
                t_a, v_a = self.analyzer.load_file(self.path_a)
                metrics_a = self.analyzer.analyze(t_a, v_a)
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
                metrics_b = self.analyzer.analyze(t_b, v_b)
                self.metrics_b = metrics_b
                self._fill_result_rows(self.rows_b, metrics_b)
                self.ax.plot(t_b, v_b, label="Sau snubber", color="#2ca02c")
                self.ax.plot(metrics_b.t_peak, metrics_b.v_peak, "ro", markersize=8)
                self.ax.annotate(
                    f"V_peak={metrics_b.v_peak:.2f}V", (metrics_b.t_peak, metrics_b.v_peak),
                    textcoords="offset points", xytext=(8, -14), color="#2ca02c",
                )
                any_plotted = True

            self.ax.set_title("Dạng sóng V_DS(t)")
            self.ax.set_xlabel("Thời gian (s)")
            self.ax.set_ylabel("V_DS (V)")
            self.ax.grid(True, alpha=0.3)
            if any_plotted:
                self.ax.legend()
            self.canvas.draw()

        except AppError as exc:
            messagebox.showerror("Lỗi phân tích dạng sóng", str(exc))
            self._draw_empty_plot()
        except Exception as exc:  # bat them loi khong luong truoc duoc tu pandas/scipy
            messagebox.showerror("Lỗi phân tích dạng sóng", f"Đã xảy ra lỗi không mong muốn: {exc}")
            self._draw_empty_plot()

    @staticmethod
    def _fill_result_rows(rows: dict, metrics) -> None:
        rows["v_peak"].set_value(f"{metrics.v_peak:.4f} V")
        rows["f_ring"].set_value(f"{metrics.f_ring:.4e} Hz")
        rows["percent_overshoot"].set_value(f"{metrics.percent_overshoot:.2f} %")
        rows["settling_time"].set_value(f"{metrics.settling_time:.4e} s")
        rows["v_final"].set_value(f"{metrics.v_final:.4f} V")

    def send_to_calculator(self):
        """Gửi V_peak và V_in đo được từ File A sang Tab 1 (Calculator)."""
        if self.metrics_a is None:
            messagebox.showwarning(
                "Chưa có dữ liệu",
                "Hãy chọn file A (trước snubber) và bấm 'Phân tích' trước khi gửi thông số sang Calculator.",
            )
            return

        v_peak = self.metrics_a.v_peak
        v_in = self.metrics_a.v_final

        if self.app_ref is None:
            return
        try:
            self.app_ref.push_from_waveform_to_calculator(v_peak, v_in)
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

        v_peak = self.metrics_a.v_peak
        v_in = self.metrics_a.v_final

        if self.app_ref is None:
            return
        try:
            self.app_ref.push_from_waveform_to_optimizer(v_peak, v_in)
        except AttributeError as exc:
            messagebox.showerror("Lỗi", f"Không thể gửi thông số sang Optimizer: {exc}")
