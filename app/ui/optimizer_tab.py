"""Tab 3 - Optimization & RC-Map Engine: quét lưới (R,C) và vẽ bản đồ tối ưu."""

from tkinter import messagebox, filedialog
from pathlib import Path

import customtkinter as ctk
import numpy as np
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure

from app import config
from app.core.optimizer_engine import OptimizerEngine
from app.core.sweep_data import SweepDataset
from app.ui.widgets import LabeledEntry, ResultRow
from app.utils.errors import AppError
from app.utils.validation import parse_nonnegative_float, parse_positive_float, parse_int_positive


class OptimizerTab(ctk.CTkFrame):
    def __init__(self, master, app_ref=None, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.app_ref = app_ref
        self.engine = OptimizerEngine()
        self.last_result = None
        self.dataset = None
        self.result_snapshot = None

        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=3)
        self.rowconfigure(0, weight=1)

        self._build_left_panel()
        self._build_plot_panel()

    def _build_left_panel(self):
        left = ctk.CTkScrollableFrame(self, label_text="Thông số quét & mục tiêu")
        left.grid(row=0, column=0, sticky="nsew", padx=(10, 5), pady=10)

        d = config.DEFAULTS
        container = left
        ctk.CTkLabel(left, text="Nguồn đánh giá", font=ctk.CTkFont(weight="bold")).pack(anchor="w")
        self.source_mode = ctk.CTkOptionMenu(left, values=["Dữ liệu SPICE / phép đo", "Mô hình RLC tham khảo"],
                                            command=self._on_mode_change)
        self.source_mode.pack(fill="x", pady=5)
        source_slot = ctk.CTkFrame(left, fg_color="transparent")
        source_slot.pack(fill="x")
        self.data_frame = ctk.CTkFrame(source_slot, fg_color="transparent")
        self.data_frame.pack(fill="x")
        self.entry_circuit = LabeledEntry(self.data_frame, "Mạch / điều kiện", "", "")
        self.entry_node = LabeledEntry(self.data_frame, "Điểm gắn (hai nút)", "", "")
        self.entry_circuit.pack(fill="x", pady=3)
        self.entry_node.pack(fill="x", pady=3)
        ctk.CTkButton(self.data_frame, text="Nạp bảng khảo sát CSV", command=self._browse_sweep).pack(fill="x", pady=5)
        self.dataset_label = ctk.CTkLabel(self.data_frame, text="Chưa nạp dữ liệu. Mỗi bảng: một mạch,\nmột điều kiện và một loại RC/RCD.",
                                           wraplength=310, justify="left")
        self.dataset_label.pack(fill="x", pady=3)
        self.demo_files = sorted((Path(__file__).resolve().parents[2] / "examples" / "p6_buck").glob("*_grid.csv"))
        self.demo_selector = ctk.CTkOptionMenu(self.data_frame, values=[p.stem for p in self.demo_files] or ["Chưa có ví dụ"])
        self.demo_selector.pack(fill="x", pady=3)
        ctk.CTkButton(self.data_frame, text="Nạp ví dụ P6 đã có", command=self._load_demo).pack(fill="x", pady=3)
        self.model_frame = ctk.CTkFrame(source_slot, fg_color="transparent")
        left = self.model_frame
        ctk.CTkLabel(left, text="Mô hình RLC rút gọn, chưa khớp Buck có driver.\n"
            "Không dùng kết quả này làm xác nhận mạch đạt.", wraplength=310, justify="left").pack(fill="x", pady=5)
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

        left = container
        ctk.CTkLabel(left, text="Mục tiêu", font=ctk.CTkFont(weight="bold")).pack(anchor="w", pady=(15, 4))
        self.entry_v_target = LabeledEntry(left, "V_target (đỉnh cho phép tối đa)", d["v_target_v"], "V")
        self.entry_v_target.pack(fill="x", pady=3)
        self.entry_ts_max = LabeledEntry(left, "Thời gian xác lập tối đa", 200, "ns")
        self.entry_p_max = LabeledEntry(left, "Psn tối đa (trống = bỏ qua)", "", "W")
        self.entry_ts_max.pack(fill="x", pady=3)
        self.entry_p_max.pack(fill="x", pady=3)

        ctk.CTkLabel(left, text="Trọng số tối ưu (0 = bỏ qua)", font=ctk.CTkFont(weight="bold")).pack(
            anchor="w", pady=(15, 4)
        )
        self.entry_w_power = LabeledEntry(left, "Công suất tổn hao", d["w_power"], "")
        self.entry_w_cost = LabeledEntry(left, "Chi phí linh kiện", d["w_cost"], "")
        self.entry_w_size = LabeledEntry(left, "Kích thước linh kiện", d["w_size"], "")
        for w in (self.entry_w_power, self.entry_w_cost, self.entry_w_size):
            w.pack(fill="x", pady=3)

        self.run_button = ctk.CTkButton(left, text="Chạy tối ưu", command=self._on_run_optimization)
        self.run_button.pack(fill="x", pady=(15, 5))

        self.send_button = ctk.CTkButton(
            left, text="Gửi sang Calculator", command=self._on_send_to_calculator, fg_color="gray40"
        )
        self.send_button.pack(fill="x", pady=(0, 5))
        self.export_button = ctk.CTkButton(left, text="Xuất báo cáo + bảng CSV", command=self._export_result)
        self.export_button.pack(fill="x", pady=5)
        self.source_label = ctk.CTkLabel(left, text="Chỉ kết luận trong các điểm đã khảo sát.\nGiá/diện tích danh mục là ước lượng.",
                                          wraplength=310, justify="left")
        self.source_label.pack(fill="x", pady=5)

        results_frame = ctk.CTkFrame(left)
        results_frame.pack(fill="x", pady=(15, 5))
        ctk.CTkLabel(results_frame, text="Kết quả tối ưu", font=ctk.CTkFont(weight="bold")).pack(
            anchor="w", padx=10, pady=(10, 5)
        )
        self.result_r_opt = ResultRow(results_frame, "R_opt")
        self.result_c_opt = ResultRow(results_frame, "C_opt")
        self.result_p_opt = ResultRow(results_frame, "P_loss_opt")
        self.result_v_opt = ResultRow(results_frame, "V_peak_opt")
        self.result_cost_opt = ResultRow(results_frame, "Chi phí R+C")
        self.result_area_opt = ResultRow(results_frame, "Diện tích R+C")
        self.result_r_part = ResultRow(results_frame, "Gói R dự kiến")
        self.result_c_part = ResultRow(results_frame, "Gói C dự kiến")
        self.result_n_feasible = ResultRow(results_frame, "Số điểm khả thi")
        self.result_ts = ResultRow(results_frame, "ts (theo dữ liệu)")
        self.result_pareto = ResultRow(results_frame, "Điểm Pareto")
        for w in (self.result_r_opt, self.result_c_opt, self.result_p_opt, self.result_v_opt,
                  self.result_cost_opt, self.result_area_opt, self.result_r_part, self.result_c_part,
                  self.result_n_feasible, self.result_ts, self.result_pareto):
            w.pack(fill="x", padx=10, pady=2)
        ctk.CTkFrame(results_frame, fg_color="transparent", height=8).pack()

    def _build_plot_panel(self):
        plot_frame = ctk.CTkFrame(self)
        plot_frame.grid(row=0, column=1, sticky="nsew", padx=(5, 10), pady=10)

        self.figure = Figure(figsize=(9, 6), dpi=100)
        self.canvas = FigureCanvasTkAgg(self.figure, master=plot_frame)
        toolbar_container = ctk.CTkFrame(plot_frame, fg_color="transparent")
        toolbar_container.pack(fill="x")
        self.nav_toolbar = NavigationToolbar2Tk(self.canvas, toolbar_container)
        self.nav_toolbar.update()
        self.canvas.get_tk_widget().pack(fill="both", expand=True)
        self._draw_empty_plot()

    def _new_axes(self):
        # Xóa cả figure (kể cả colorbar cũ) để colorbar không bị chồng sau mỗi lần chạy
        self.figure.clear()
        self.ax_vpeak, self.ax_ploss, self.ax_cost, self.ax_size = (
            self.figure.add_subplot(2, 2, k) for k in range(1, 5)
        )

    def _draw_empty_plot(self):
        self._new_axes()
        for ax, title in ((self.ax_vpeak, "RC-Map: V_peak (V)"), (self.ax_ploss, "RC-Map: P_loss (mW)"),
                          (self.ax_cost, "Chi phí R+C (VND)"), (self.ax_size, "Diện tích R+C (mm²)")):
            ax.set_title(title)
            ax.set_xlabel("R_snub (Ω)")
            ax.set_ylabel("C_snub (pF)")
        self.figure.tight_layout()
        self.canvas.draw()

    def _clear_result(self):
        self.last_result = self.result_snapshot = None
        for row in (self.result_r_opt, self.result_c_opt, self.result_p_opt, self.result_v_opt,
                    self.result_cost_opt, self.result_area_opt, self.result_r_part, self.result_c_part,
                    self.result_n_feasible, self.result_ts, self.result_pareto):
            row.set_value("—")
        self.source_label.configure(text="Chưa có kết quả cho đầu vào mới; bấm Chạy tối ưu.")
        self._draw_empty_plot()

    def _on_mode_change(self, mode):
        self.data_frame.pack_forget()
        self.model_frame.pack_forget()
        (self.data_frame if mode == "Dữ liệu SPICE / phép đo" else self.model_frame).pack(fill="x")
        self._clear_result()

    def _browse_sweep(self):
        path = filedialog.askopenfilename(title="Bảng R/C của một mạch / điều kiện", filetypes=[("Bảng khảo sát", "*.csv")])
        if path:
            self._load_dataset(path)

    def _load_demo(self):
        match = next((p for p in self.demo_files if p.stem == self.demo_selector.get()), None)
        if match:
            self._load_dataset(match)

    def _load_dataset(self, path):
        self.dataset = None
        self._clear_result()
        try:
            self.dataset = SweepDataset.load(path)
            m = self.dataset.metadata
            self.dataset_label.configure(text=f"{Path(path).name}\n{len(self.dataset.rows)} điểm đã chạy; ô trống không nội suy.")
            self.entry_circuit.set(m.get("circuit", ""))
            self.entry_node.set(m.get("node", ""))
            if "v_target" in m:
                self.entry_v_target.set(m["v_target"])
            self.source_mode.set("Dữ liệu SPICE / phép đo")
            self._on_mode_change("Dữ liệu SPICE / phép đo")
        except AppError as exc:
            self.dataset_label.configure(text="Nạp dữ liệu thất bại; chưa có bảng để tối ưu.")
            messagebox.showerror("Lỗi bảng khảo sát", str(exc))

    def _run_data_optimization(self):
        if self.dataset is None:
            raise AppError("Hãy nạp bảng CSV hoặc ví dụ P6 trước.")
        circuit, node = self.entry_circuit.get().strip(), self.entry_node.get().strip()
        if not circuit or not node:
            raise AppError("Ghi rõ mạch/điều kiện và hai nút gắn snubber để kết quả có thể đối chiếu.")
        criteria = dict(v_target=parse_positive_float(self.entry_v_target.get(), "V_target"),
                        ts_max_ns=parse_positive_float(self.entry_ts_max.get(), "ts tối đa"),
                        weights=tuple(parse_nonnegative_float(w.get(), "Trọng số") for w in
                                      (self.entry_w_power, self.entry_w_cost, self.entry_w_size)),
                        p_max_w=parse_positive_float(self.entry_p_max.get(), "Psn tối đa") if self.entry_p_max.get().strip() else None)
        result = self.dataset.select(**criteria)
        self.last_result = result
        self.result_snapshot = (self.dataset, result, criteria, circuit, node)
        selected = self.dataset.ranked_rows(result).query("selected").iloc[0]
        self.source_label.configure(text=f"Đã tính: V ≤ {criteria['v_target']:.4g} V; ts ≤ {criteria['ts_max_ns']:.4g} ns\n"
            f"Trọng số {criteria['weights']}; đổi ô nhập cần chạy lại.\n"
            + str(selected.get("evidence", "Nguồn người dùng; chưa kiểm chứng"))
            + "\nPsn: nhánh snubber; giá/diện tích cần đối chiếu nguồn.")
        self._display_result(result, criteria["v_target"])

    def _export_result(self):
        if self.result_snapshot is None:
            messagebox.showinfo("Chưa có kết quả từ dữ liệu", "Chạy tối ưu theo bảng dữ liệu trước khi xuất.")
            return
        path = filedialog.asksaveasfilename(title="Xuất kết quả đã tính (Markdown + CSV cùng tên)",
                                           defaultextension=".md", filetypes=[("Báo cáo Markdown", "*.md")])
        if path:
            try:
                dataset, result, criteria, circuit, node = self.result_snapshot
                paths = dataset.export(path, result, criteria, circuit, node)
                messagebox.showinfo("Đã xuất", "\n".join(map(str, paths)))
            except (OSError, AppError) as exc:
                messagebox.showerror("Không xuất được", str(exc))

    def _on_run_optimization(self):
        self._clear_result()
        try:
            if self.source_mode.get() == "Dữ liệu SPICE / phép đo":
                self._run_data_optimization()
                return
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
            weights = (
                parse_nonnegative_float(self.entry_w_power.get(), "Trọng số công suất"),
                parse_nonnegative_float(self.entry_w_cost.get(), "Trọng số chi phí"),
                parse_nonnegative_float(self.entry_w_size.get(), "Trọng số kích thước"),
            )
            if sum(weights) == 0:
                raise AppError("Cần ít nhất một trọng số lớn hơn 0.")

            result = self.engine.run_full_sweep(
                R_min=r_min, R_max=r_max, R_steps=r_steps,
                C_min=c_min, C_max=c_max, C_steps=c_steps,
                Vin=vin, fsw_Hz=fsw_hz, L_stray_H=l_stray_h, C_oss_F=c_oss_f,
                V_target=v_target, V_peak_unprotected=v_peak_unprot, weights=weights,
            )
            self.last_result = result
            self.source_label.configure(text="ƯỚC LƯỢNG MÔ HÌNH RLC.\nChưa kiểm chứng mạch SPICE/phần cứng; chưa lọc ts.")
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
        self.result_cost_opt.set_value(f"{result.cost_opt:,.0f} đ")
        self.result_area_opt.set_value(f"{result.area_opt:.1f} mm²")
        self.result_r_part.set_value(result.R_part)
        self.result_c_part.set_value(result.C_part)
        self.result_n_feasible.set_value(f"{result.n_feasible} / {result.n_total}")
        self.result_ts.set_value(f"{result.settling_time_opt * 1e9:.2f} ns" if np.isfinite(result.settling_time_opt) else "Chưa đánh giá")
        self.result_pareto.set_value(str(int(result.pareto_mask.sum())) if result.pareto_mask is not None else "Chưa đánh giá")

        RR = result.R_grid
        CC_pf = result.C_grid / config.PICO

        self._new_axes()
        if result.pareto_mask is not None:
            # Điểm đã chạy: không vẽ nội suy màu giữa các cặp chưa được mô phỏng.
            present = np.isfinite(result.V_peak_grid)
            for ax, values, title in ((self.ax_vpeak, result.V_peak_grid, "Vpeak (V)"),
                    (self.ax_ploss, result.P_loss_grid / config.MILLI, "Psn (mW)"),
                    (self.ax_cost, result.cost_grid, "Giá ước lượng/nhập (VND)"),
                    (self.ax_size, result.area_grid, "Diện tích (mm²)")):
                mesh = ax.scatter(RR[present], CC_pf[present], c=np.ma.masked_invalid(values[present]),
                                  cmap="viridis", marker="s", s=85)
                self.figure.colorbar(mesh, ax=ax)
                ax.scatter(RR[result.feasible_mask], CC_pf[result.feasible_mask], facecolors="none",
                           edgecolors="limegreen", s=125, linewidths=1.5, label="Khả thi")
                ax.scatter(RR[result.pareto_mask], CC_pf[result.pareto_mask], marker="D", facecolors="none",
                           edgecolors="black", s=150, label="Pareto")
                ax.plot(result.R_opt, result.C_opt / config.PICO, "r*", markersize=17, label="Cặp chọn")
                ax.set(title=title, xlabel="R (Ω)", ylabel="C (pF)")
            self.ax_vpeak.legend(fontsize=8)
            self.figure.tight_layout()
            self.canvas.draw()
            return
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

        contour2 = self.ax_ploss.contourf(RR, CC_pf, result.P_loss_grid / config.MILLI, levels=20, cmap="plasma")
        self.figure.colorbar(contour2, ax=self.ax_ploss, label="P_loss (mW)")
        self.ax_ploss.plot(result.R_opt, result.C_opt / config.PICO, marker="*", color="cyan", markersize=18)
        self.ax_ploss.set_title("RC-Map: P_loss (mW)")
        self.ax_ploss.set_xlabel("R_snub (Ω)")
        self.ax_ploss.set_ylabel("C_snub (pF)")

        # Chi phí/diện tích thay đổi theo bậc (từng loại linh kiện) nên vẽ pcolormesh; inf -> ô trắng
        for ax, grid, title, unit in ((self.ax_cost, result.cost_grid, "Chi phí R+C (VND)", "VND"),
                                      (self.ax_size, result.area_grid, "Diện tích R+C (mm²)", "mm²")):
            mesh = ax.pcolormesh(RR, CC_pf, np.where(np.isfinite(grid), grid, np.nan), shading="auto", cmap="cividis")
            self.figure.colorbar(mesh, ax=ax, label=unit)
            ax.plot(result.R_opt, result.C_opt / config.PICO, marker="*", color="red", markersize=14)
            ax.set_title(f"{title} — ô trắng: không có linh kiện")
            ax.set_xlabel("R_snub (Ω)")
            ax.set_ylabel("C_snub (pF)")

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
        self._clear_result()
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
