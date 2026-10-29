# RC Snubber Design & Optimization Tool

Ứng dụng desktop hỗ trợ tính toán, phân tích dạng sóng và tối ưu hóa mạch RC Snubber
theo dạng sóng và bảng khảo sát của từng mạch. Buck hiện là bộ đối chứng đã có dữ liệu.
Đồ án tốt nghiệp IUH — Trần Xuyên Hoài & Nguyễn Minh Khoa.

Đây là bản phát triển tiếp của app hiện có. Xem [hướng dẫn](HUONG_DAN_APP_SNUBBER.md),
[kế hoạch](KE_HOACH_VIBE_CODING_SNUBBER.md) và [trạng thái kiểm tra](TRANG_THAI_P8.md).
Trên máy hiện tại có thể mở `CHAY_APP.cmd` để dùng môi trường Python sẵn có của dự án.

Bổ sung 29/10: tab **4. Mạch tương tác** nhúng Falstad v115 cục bộ ngay trong app qua WebView2,
nhận dạng sóng qua cầu nối loopback. Windows cần WebView2 Runtime và `tkwry==0.1.9` (đã có trong requirements).
Đã kiểm tra khung nhúng thật, đổi tab, co giãn, đóng/mở lại và ba bản ghi; bằng chứng `verification/falstad_embedded/result.json`.
Có mẫu RLC trước/sau RC/tụ thử và chế độ tự vẽ/nhập mạch. Dữ liệu
minh họa có nhãn riêng và không thay thế LTspice/P6. Xem [phân tích REA/Falstad](docs/PHAN_TICH_REA_FALSTAD.md)
và [thông tin thành phần bên thứ ba](THIRD_PARTY_NOTICES.md).

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

## Giá và kích thước linh kiện (Tab 3)

Tab 3 chọn gói linh kiện dự kiến cho từng cặp (R, C) và tối ưu theo 3 trọng số: công suất, chi phí,
kích thước. Danh mục linh kiện, giá (VND, ước lượng) và diện tích nằm trong `app/config.py`
(`RESISTOR_PARTS`, `CAPACITOR_PARTS`) — cập nhật theo báo giá thực tế trước khi dùng số liệu cho báo cáo.

Tab 2 bổ sung file tụ thử riêng, tự suy Lp/Cp, ước lượng ζ, cửa sổ một cạnh tăng và trạng thái
chưa xác lập trong dải ±5% (giữ mặc định 500 ns). File B vẫn dùng so sánh trước/sau.
Tab 3 mặc định dùng bảng dữ liệu SPICE/phép đo, lọc Vpeak/ts/Psn, hiển thị Pareto và xuất Markdown/CSV.
Mô hình RLC cũ là chế độ tham khảo, chưa khớp mạch Buck có driver trong P6.

`examples/p6_buck/` chứa bản sao đối chứng của nhóm; công suất chỉ là nhánh snubber,
các mức kiểm chứng được ghi riêng. Không tuyên bố mọi topology hoặc phần cứng đã đạt từ dữ liệu này.

## Đóng gói thành file .exe (tùy chọn)

Không bắt buộc để chạy đồ án, nhưng nếu cần bản .exe độc lập để demo:

```bash
pip install pyinstaller
pyinstaller --noconfirm --windowed --name SnubberTool --collect-all customtkinter main.py
```

File thực thi sẽ nằm trong thư mục `dist/SnubberTool/`.
