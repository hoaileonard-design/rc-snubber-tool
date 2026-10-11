"""Các widget composite dùng chung cho 3 tab: ô nhập có nhãn, dòng hiển thị kết quả."""

import customtkinter as ctk


class LabeledEntry(ctk.CTkFrame):
    """Một hàng gồm nhãn (label) + ô nhập liệu (CTkEntry), có thể đặt giá trị mặc định
    và đơn vị hiển thị bên phải."""

    def __init__(self, master, label_text: str, default_value="", unit: str = "", width: int = 120, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.columnconfigure(0, weight=1)

        self.label = ctk.CTkLabel(self, text=label_text, anchor="w")
        self.label.grid(row=0, column=0, sticky="w", padx=(0, 8), pady=2)

        self.entry = ctk.CTkEntry(self, width=width)
        self.entry.grid(row=0, column=1, sticky="e", pady=2)
        if default_value != "":
            self.entry.insert(0, str(default_value))

        if unit:
            self.unit_label = ctk.CTkLabel(self, text=unit, width=40, anchor="w")
            self.unit_label.grid(row=0, column=2, sticky="w", padx=(6, 0), pady=2)

    def get(self) -> str:
        return self.entry.get()

    def set(self, value) -> None:
        self.entry.delete(0, "end")
        self.entry.insert(0, str(value))


class ResultRow(ctk.CTkFrame):
    """Một hàng hiển thị kết quả: nhãn bên trái, giá trị (đổi được) bên phải."""

    def __init__(self, master, label_text: str, initial_value: str = "—", **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.columnconfigure(0, weight=1)

        self.label = ctk.CTkLabel(self, text=label_text, anchor="w", font=ctk.CTkFont(weight="bold"))
        self.label.grid(row=0, column=0, sticky="w", padx=(0, 8), pady=3)

        self.value_label = ctk.CTkLabel(self, text=initial_value, anchor="e")
        self.value_label.grid(row=0, column=1, sticky="e", pady=3)

    def set_value(self, value: str) -> None:
        self.value_label.configure(text=value)
