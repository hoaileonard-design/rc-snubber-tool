"""Các exception dùng riêng cho ứng dụng, giúp UI bắt lỗi và hiển thị thông báo tiếng Việt."""


class AppError(Exception):
    """Lớp cơ sở cho mọi lỗi nghiệp vụ của ứng dụng."""


class InputValidationError(AppError):
    """Dữ liệu người dùng nhập vào không hợp lệ (sai định dạng, âm, bằng 0 khi không cho phép, v.v.)."""


class WaveformFileError(AppError):
    """File dạng sóng (.txt/.csv) không đọc được hoặc sai định dạng LTspice."""


class InsufficientDataError(AppError):
    """Không đủ điểm dữ liệu để phân tích tín hiệu."""


class NoFeasibleRegionError(AppError):
    """Không tìm thấy điểm (R, C) nào thỏa ràng buộc V_peak <= V_target trong vùng quét."""
