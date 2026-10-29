"""Hàm tiện ích kiểm tra và chuyển đổi input người dùng nhập từ các ô CTkEntry."""

import math

from .errors import InputValidationError


def parse_float(text: str, field_name: str = "Giá trị") -> float:
    """Chuyển chuỗi nhập thành float, báo lỗi tiếng Việt rõ ràng nếu sai định dạng."""
    if text is None:
        raise InputValidationError(f"{field_name} không được để trống.")
    text = text.strip().replace(",", ".")
    if text == "":
        raise InputValidationError(f"{field_name} không được để trống.")
    try:
        value = float(text)
    except ValueError:
        raise InputValidationError(f"{field_name} không hợp lệ: '{text}' không phải là số.")
    if not math.isfinite(value):
        raise InputValidationError(f"{field_name} phải là số hữu hạn.")
    return value


def parse_positive_float(text: str, field_name: str = "Giá trị") -> float:
    """Giống parse_float nhưng bắt buộc giá trị > 0 (dùng cho R, C, L, Vin, f... vật lý)."""
    value = parse_float(text, field_name)
    if value <= 0:
        raise InputValidationError(f"{field_name} phải là số dương lớn hơn 0 (nhận được {value}).")
    return value


def parse_nonnegative_float(text: str, field_name: str = "Giá trị") -> float:
    """Giống parse_float nhưng bắt buộc giá trị >= 0."""
    value = parse_float(text, field_name)
    if value < 0:
        raise InputValidationError(f"{field_name} không được âm (nhận được {value}).")
    return value


def parse_int_positive(text: str, field_name: str = "Giá trị") -> int:
    """Chuyển chuỗi nhập thành số nguyên dương (dùng cho số bước quét lưới)."""
    if text is None or text.strip() == "":
        raise InputValidationError(f"{field_name} không được để trống.")
    try:
        number = parse_float(text, field_name)
        if not number.is_integer():
            raise ValueError
        value = int(number)
    except (ValueError, OverflowError):
        raise InputValidationError(f"{field_name} không hợp lệ: '{text}' không phải là số nguyên.")
    if value < 2:
        raise InputValidationError(f"{field_name} phải >= 2 để tạo được lưới quét (nhận được {value}).")
    return value
