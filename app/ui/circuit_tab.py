"""Falstad embedded in the existing desktop waveform workflow."""

import math
import os
import tkinter as tk
from pathlib import Path
from tkinter import messagebox
from urllib.parse import urlsplit

import customtkinter as ctk

from app import config
from app.core.circuit_bridge import CircuitBridge
from app.ui.widgets import LabeledEntry
from app.utils.errors import AppError
from app.utils.validation import parse_positive_float


class CircuitTab(ctk.CTkFrame):
    def __init__(self, master, app_ref=None, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.app_ref = app_ref
        self.bridge = None
        self._poll_id = None
        self._context = None
        self.last_capture = None
        self.webview = None
        root = Path(__file__).resolve().parents[2]
        self._web_root = root / "app" / "web" / "falstad"
        self._vendor_root = root / "app" / "vendor" / "circuitjs"
        self._capture_root = root / "data" / "falstad_captures"

        self.columnconfigure(1, weight=1)
        self.rowconfigure(1, weight=1)
        toolbar = ctk.CTkFrame(self, fg_color="transparent")
        toolbar.grid(row=0, column=0, columnspan=2, sticky="ew", padx=10, pady=8)
        ctk.CTkLabel(toolbar, text="Mạch tương tác · Falstad trong ứng dụng", font=ctk.CTkFont(size=17, weight="bold")).pack(anchor="w")
        actions = ctk.CTkFrame(toolbar, fg_color="transparent")
        actions.pack(fill="x", pady=(5, 0))
        for text, command in (("Mở bàn mạch", self.open_circuit), ("Lấy R/C đang chọn", self.load_selected),
                ("Cập nhật thông số", self.update_parameters), ("Thông số mẫu", self.toggle_parameters), ("Đóng bàn mạch", self.close)):
            ctk.CTkButton(actions, text=text, command=command, width=130).pack(side="left", padx=(0, 6))
        box = ctk.CTkScrollableFrame(self, label_text="Thông số mẫu RLC", width=325)
        self.params_panel = box
        box.grid(row=1, column=0, sticky="nsew", padx=(10, 4), pady=(0, 4))
        box.grid_remove()
        self.web_host = tk.Frame(self, bg="#eef3f7")
        self.web_host.grid(row=1, column=1, sticky="nsew", padx=(4, 10), pady=(0, 4))
        self.placeholder = tk.Label(self.web_host, text="Bấm Mở bàn mạch để thao tác ngay trong ứng dụng.\n"
            "Mẫu RLC minh họa được giữ riêng với kết quả LTspice P6.", bg="#eef3f7", fg="#24445c", font=("Segoe UI", 12))
        self.placeholder.place(relx=.5, rely=.5, anchor="center")
        ctk.CTkLabel(box, text="Chỉnh mạch → ghi dạng sóng → phân tích snubber", font=ctk.CTkFont(size=22, weight="bold")).pack(
            anchor="w", padx=18, pady=(18, 8))
        ctk.CTkLabel(box, text="Bàn mạch hiển thị trực tiếp trong ứng dụng. Chạy bằng tài nguyên cục bộ.\n"
            "Mẫu RLC giúp hiểu cơ chế dập dao động; đây là mô hình minh họa riêng, khác mạch Buck P6.",
            justify="left", wraplength=1000).pack(anchor="w", padx=18, pady=8)
        params = ctk.CTkFrame(box)
        params.pack(fill="x", padx=18, pady=10)
        self.entries = {}
        for key, title, value, unit in (
                ("R_ohm", "R snubber", 10, "Ω"), ("C_F", "C snubber", 4700, "pF"),
                ("Lp_H", "L ký sinh minh họa", 100, "nH"), ("Cp_F", "C ký sinh minh họa", 274, "pF"),
                ("Vin", "Bước điện áp minh họa", 24, "V"), ("added_cap_F", "Tụ thử", 470, "pF")):
            entry = LabeledEntry(params, title, value, unit)
            entry.pack(fill="x", padx=14, pady=5)
            self.entries[key] = entry
        ctk.CTkButton(box, text="Lấy R/C từ kết quả đang chọn", command=self.load_selected).pack(fill="x", padx=18, pady=6)
        ctk.CTkButton(box, text="Mở bàn mạch Falstad", command=self.open_circuit, height=44).pack(fill="x", padx=18, pady=6)
        ctk.CTkButton(box, text="Cập nhật thông số cho bàn mạch đang mở", command=self.update_parameters).pack(fill="x", padx=18, pady=6)
        self.status = ctk.CTkLabel(self, text="Chưa mở bàn mạch.", justify="left", wraplength=1200)
        self.status.grid(row=2, column=0, columnspan=2, sticky="w", padx=12, pady=5)
        ctk.CTkLabel(box, text="Cách dùng\n"
            "1. Mở bàn mạch, chọn Chưa snubber / Có RC / Tụ thử.\n"
            "2. Bấm Ghi và gửi dạng sóng. App tự nhận file vào tab Phân tích dạng sóng.\n"
            "3. Ghi đủ ba trường hợp để so sánh và nhận dạng Lp/Cp.\n"
            "4. Với mạch tự vẽ, chọn đúng hai điểm đo và ghi rõ điều kiện; chưa có chức năng tự thiết kế snubber cho mọi mạch.\n\n"
            "Khi thay thông số của mẫu, Falstad nạp lại mạch và chạy từ đầu. Muốn chốt linh kiện cần đối chiếu LTspice và phép đo.",
            justify="left", wraplength=1000).pack(anchor="w", padx=18, pady=12)
        ctk.CTkButton(box, text="Đóng kết nối bàn mạch", command=self.close, fg_color="gray40").pack(fill="x", padx=18, pady=(8, 18))

    def toggle_parameters(self):
        if self.params_panel.winfo_ismapped():
            self.params_panel.grid_remove()
        else:
            self.params_panel.grid()

    def _state(self):
        values = {key: parse_positive_float(entry.get(), key) for key, entry in self.entries.items()}
        for key, scale in (("C_F", 1e-12), ("Lp_H", 1e-9), ("Cp_F", 1e-12), ("added_cap_F", 1e-12)):
            values[key] *= scale
        return values

    def load_selected(self):
        if self.app_ref is None:
            return
        result = self.app_ref.optimizer_tab.last_result
        calc = self.app_ref.calculator_tab
        if result is not None:
            self.entries["R_ohm"].set(result.R_opt)
            self.entries["C_F"].set(result.C_opt * 1e12)
        elif calc.last_result:
            self.entries["R_ohm"].set(calc.last_result["R_sn"])
            self.entries["C_F"].set(calc.last_result["C_sn"] * 1e12)
        else:
            messagebox.showinfo("Chưa có kết quả", "Tính hoặc chọn một cặp R/C trước; cũng có thể nhập trực tiếp tại đây.")
            return
        self.status.configure(text="Đã lấy R/C. Lp/Cp và bước nguồn dùng giá trị đang nhập của mô hình minh họa; kiểm tra lại trước khi chạy.")

    def update_parameters(self):
        try:
            values = self._state()
            if self.bridge:
                self.bridge.update_state(values)
                self.status.configure(text="Đã gửi thông số. Trên bàn mạch bấm Lấy thông số từ app rồi nạp lại mẫu để áp dụng.")
            else:
                self.status.configure(text="Thông số hợp lệ; bấm Mở bàn mạch để bắt đầu.")
        except (AppError, ValueError) as exc:
            messagebox.showerror("Thông số không hợp lệ", str(exc))

    def open_circuit(self):
        try:
            # WebView2's default profile can point beside the Python runtime, outside app data.
            profile = self._capture_root.parent / "webview2"
            profile.mkdir(parents=True, exist_ok=True)
            os.environ.setdefault("WEBVIEW2_USER_DATA_FOLDER", str(profile))
            from tkwry import WebView

            values = self._state()
            if self.bridge is None:
                self.bridge = CircuitBridge(self._web_root, self._vendor_root, self._capture_root, values)
            else:
                self.bridge.update_state(values)
            url = self.bridge.start()
            if self.webview is None:
                self.placeholder.place_forget()
                expected_origin = self.bridge.origin
                def local_navigation(event):
                    target = urlsplit(event.url)
                    return event.url == "about:blank" or (f"{target.scheme}://{target.netloc}" == expected_origin)
                self.webview = WebView(self.web_host, url=url, untrusted=True,
                                       on_navigation=local_navigation, user_agent="SnubberTool/1.0")
                self.webview.when_failed(self._webview_failed)
                self.webview.when_ready(lambda: self.status.configure(text="Bàn mạch đã nhúng trong tab này. Ghi dạng sóng để chuyển về phần phân tích."))
                self.status.configure(text="Đang nạp bàn mạch ngay trong ứng dụng…")
            if self._poll_id is None:
                self._poll_id = self.after(400, self._poll)
        except ImportError:
            messagebox.showerror("Thiếu thành phần hiển thị", "Cần cài tkwry trong môi trường Python của app để mở bàn mạch bên trong ứng dụng.")
        except (OSError, AppError, ValueError) as exc:
            messagebox.showerror("Không mở được bàn mạch", str(exc))

    def _webview_failed(self, error):
        self.close()
        self.placeholder.configure(text="Không tạo được khung mạch. Kiểm tra Microsoft Edge WebView2 Runtime.")
        self.status.configure(text=f"Không mở được bàn mạch nhúng: {error}")

    def _poll(self):
        self._poll_id = None
        if not self.bridge:
            return
        while capture := self.bridge.pop_capture():
            self.accept_capture(capture)
        self._poll_id = self.after(400, self._poll)

    def accept_capture(self, capture):
        self.last_capture = capture
        if self.app_ref is None:
            return
        metadata = capture["metadata"]
        role = metadata.get("role")
        if role not in ("before", "after", "test_cap"):
            self.status.configure(text="Đã lưu dạng sóng, chưa phân loại trước/sau/tụ thử; chưa chuyển sang phân tích.")
            return
        waveform = self.app_ref.waveform_tab
        context = metadata.get("context_id")
        if not context or self._context != context or waveform.external_context != context:
            waveform.path_a = waveform.path_b = waveform.path_cap = None
            waveform.label_file_a.configure(text="(chưa nhận file trước)")
            waveform.label_file_b.configure(text="(chưa nhận file sau)")
            waveform.label_cap.configure(text="(chưa nhận file tụ thử)")
        self._context = context
        waveform.external_context = context
        waveform.source_note = "Nguồn: Falstad/CircuitJS — mô hình minh họa, chưa kiểm chứng LTspice/phần cứng."
        waveform._clear_results()
        path = capture["path"]
        attr, label = {"before": ("path_a", waveform.label_file_a), "after": ("path_b", waveform.label_file_b),
                       "test_cap": ("path_cap", waveform.label_cap)}[role]
        setattr(waveform, attr, path)
        label.configure(text=f"Falstad: {Path(path).name}")
        waveform.entry_start.set("")
        waveform.entry_end.set("")
        plateau = metadata.get("plateau_V")
        waveform.entry_plateau.set(plateau if isinstance(plateau, (int, float)) and math.isfinite(plateau) and plateau > 0 else "")
        added = metadata.get("added_cap_F")
        if isinstance(added, (int, float)) and math.isfinite(added) and added > 0:
            waveform.entry_added_cap.set(added * 1e12)
        waveform._on_analyze()
        self.status.configure(text=f"Đã nhận {role}: {Path(path).name}. CSV và nguồn mạch được lưu riêng, không ghi vào P6.")
        self.app_ref.tabview.set(config.TAB_WAVEFORM)

    def close(self):
        if self._poll_id is not None:
            self.after_cancel(self._poll_id)
            self._poll_id = None
        if self.webview is not None:
            self.webview.destroy()
            self.webview = None
        if self.bridge is not None:
            self.bridge.stop()
            self.bridge = None
        self.status.configure(text="Đã đóng kết nối. Dạng sóng đã ghi vẫn được giữ.")
        self.placeholder.place(relx=.5, rely=.5, anchor="center")
