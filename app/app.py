"""SnubberApp: cửa sổ chính, khởi tạo CTkTabview và liên kết 3 tab với nhau."""

from tkinter import messagebox

import customtkinter as ctk

from app import config
from app.ui.calculator_tab import CalculatorTab
from app.ui.waveform_tab import WaveformTab
from app.ui.optimizer_tab import OptimizerTab
from app.ui.circuit_tab import CircuitTab


class SnubberApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")

        self.title(config.APP_TITLE)
        self.geometry(config.APP_GEOMETRY)
        self.minsize(1100, 700)

        self._build_header()

        self.tabview = ctk.CTkTabview(self)
        self.tabview.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        tab1 = self.tabview.add(config.TAB_CALCULATOR)
        tab2 = self.tabview.add(config.TAB_WAVEFORM)
        tab3 = self.tabview.add(config.TAB_OPTIMIZER)
        tab4 = self.tabview.add(config.TAB_CIRCUIT)

        self.calculator_tab = CalculatorTab(tab1, app_ref=self)
        self.calculator_tab.pack(fill="both", expand=True)

        self.waveform_tab = WaveformTab(tab2, app_ref=self)
        self.waveform_tab.pack(fill="both", expand=True)

        self.optimizer_tab = OptimizerTab(tab3, app_ref=self)
        self.optimizer_tab.pack(fill="both", expand=True)
        self.circuit_tab = CircuitTab(tab4, app_ref=self)
        self.circuit_tab.pack(fill="both", expand=True)
        self.tabview.set(config.TAB_WAVEFORM)

    def destroy(self):
        if hasattr(self, "circuit_tab"):
            self.circuit_tab.close()
        super().destroy()

    def _build_header(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=10, pady=10)

        ctk.CTkLabel(
            header, text=config.APP_TITLE, font=ctk.CTkFont(size=18, weight="bold")
        ).pack(side="left")

        self.appearance_switch = ctk.CTkSegmentedButton(
            header, values=["Light", "System", "Dark"], command=self._on_appearance_change
        )
        self.appearance_switch.set("System")
        self.appearance_switch.pack(side="right")

    def _on_appearance_change(self, mode: str):
        ctk.set_appearance_mode(mode)

    # ------------------------------------------------------- Cross-tab wiring
    def push_params_to_optimizer(self, params: dict):
        self.optimizer_tab.load_params_from_dict(params)
        self.tabview.set(config.TAB_OPTIMIZER)

    def push_params_to_calculator(self, params: dict):
        self.calculator_tab.load_params_from_dict(params)
        self.tabview.set(config.TAB_CALCULATOR)

    def push_from_waveform_to_calculator(self, v_peak: float, v_in: float = None):
        """Giữ API cũ, chỉ chuyển Vpeak. Plateau không được suy thành Vin."""
        try:
            self.calculator_tab.entry_vpeak_unprot.set(v_peak)
        except AttributeError as exc:
            messagebox.showerror(
                "Lỗi", f"Không thể cập nhật thông số sang Calculator: {exc}"
            )
            return
        self.tabview.set(config.TAB_CALCULATOR)

    def push_from_waveform_to_optimizer(self, v_peak: float, v_in: float = None):
        """Giữ API cũ, chỉ chuyển Vpeak. Plateau không được suy thành Vin."""
        try:
            self.optimizer_tab.entry_vpeak_unprot.set(v_peak)
        except AttributeError as exc:
            messagebox.showerror(
                "Lỗi", f"Không thể cập nhật thông số sang Optimizer: {exc}"
            )
            return
        self.tabview.set(config.TAB_OPTIMIZER)
