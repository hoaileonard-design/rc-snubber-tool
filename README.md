# RC Snubber Design & Optimization Tool

Ứng dụng desktop hỗ trợ tính toán, phân tích dạng sóng và tối ưu hóa mạch RC Snubber
cho MOSFET trong bộ Buck Converter. Đồ án tốt nghiệp IUH — Trần Xuyên Hoài & Nguyễn Minh Khoa.

## Cài đặt

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Chạy ứng dụng

```bash
python main.py
```

## Chạy test

```bash
pytest tests/ -v
```

## Sinh dữ liệu dạng sóng mẫu để thử Tab 2 (Waveform Survey)

```bash
python tests/sample_data/make_synthetic_waveform.py
```

Sẽ tạo 2 file `tests/sample_data/synthetic_before_snubber.csv` và
`synthetic_after_snubber.txt` — nạp vào Tab 2 (nút "Chọn file A" / "Chọn file B") để
kiểm tra tính năng đọc file, trích xuất chỉ số quá độ và so sánh trước/sau snubber.

## Cấu trúc dự án

```
main.py                    Điểm khởi chạy
app/
  app.py                   SnubberApp — cửa sổ chính, ghép 3 tab
  config.py                Hằng số đơn vị + giá trị mặc định của mạch thử nghiệm
  core/                    Tính toán thuần (không phụ thuộc UI) — có thể unit-test độc lập
    rlc_model.py           Mô hình RLC nối tiếp dùng chung
    calculator_engine.py   3 phương pháp tính R_snub/C_snub (Tab 1)
    waveform_analyzer.py   Đọc file + trích xuất chỉ số quá độ (Tab 2)
    optimizer_engine.py    Grid search tối ưu đa mục tiêu (Tab 3)
  ui/                      Các lớp giao diện customtkinter, gọi vào app/core/*
  utils/                   Validation input + exception dùng chung
tests/                     Unit test cho các engine + dữ liệu mẫu
```

## Đóng gói thành file .exe (tùy chọn)

Không bắt buộc để chạy đồ án, nhưng nếu cần bản .exe độc lập để demo:

```bash
pip install pyinstaller
pyinstaller --noconfirm --windowed --name SnubberTool --collect-all customtkinter main.py
```

File thực thi sẽ nằm trong thư mục `dist/SnubberTool/`.
