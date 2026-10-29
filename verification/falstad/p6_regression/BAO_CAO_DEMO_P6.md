# Kết quả thiết kế snubber theo dữ liệu

Mạch/điều kiện: Buck 24 V, Lstray=100 nH, tải 10 Ω

Điểm gắn/đo (hai nút): drain – sw

File: `C:\Doantotnghiep\APP_khoiphuc\examples\p6_buck\L100_Rload10_grid.csv`

SHA256: `4cd194a3639410cf8f8900672ffed6109ed30dc24b2c5e6b7929392bba188bd3`

Metadata đầu vào: `{"circuit": "Buck 24 V, Lstray=100 nH, tải 10 Ω", "topology": "Buck", "node": "drain – sw", "source": "P6, mô hình chức năng gần đúng", "v_target": 28.251003074645993, "ts_max_ns": 200, "settling_band": 0.05, "settling_hold_ns": 500, "operating_point": {"Vin": 24, "Lout_uH": 220, "fsw_kHz": 20, "duty_percent": 50.84926657397271}, "evidence_scope": "Chỉ mạch Buck; sàng lọc và điểm chọn có mức kiểm chứng khác nhau", "source_csv_sha256": "21e43330ca3b9be3058c9cb78e67d9e336e16ad189a5fdc354daf0e270b0d7c8", "source_json_sha256": "18abcde2c3650421e1809e3977fbd58312e5249458076f8422042d9e2a975c4c", "selected_reference": {"R_ohm": 10.0, "C_F": 4.700000000000001e-09}}`

## Tiêu chí và kết quả

- Vpeak ≤ 28.251 V; ts ≤ 200 ns.
- Psn tối đa: None; trọng số (công suất, giá, diện tích): (1.0, 0.0, 0.0).
- R = 10 Ω; C = 4.7 nF.
- Vpeak = 27.5426273 V; ts = 77.7071227 ns.
- Psn = 0.041770571 W; giá = 250 VND; diện tích = 3.78 mm².
- Khả thi 10/42 điểm đã nạp; Pareto 1 điểm.
- Mức bằng chứng của cặp chọn: LTspice 0.5 ns; đã đối chiếu 0.25 ns và giữ dải ±5% 500 ns (P6).
- Dấu vết dạng sóng: khao_sat_p6\L100_Rload10_fine_R10_C4.7n.raw.

## Phạm vi kết luận

Đây là lựa chọn trong những điểm đã khảo sát của một điều kiện. Ô chưa chạy không được nội suy.
Nếu thiếu giá/diện tích đầu vào, app dùng ước lượng danh mục, chưa xác nhận báo giá hay khả năng chịu xung.
Psn là tổn hao nhánh snubber theo cột dữ liệu, không phải tổng tổn hao hệ thống. Không dùng để khẳng định hiệu suất toàn bộ.
ts phụ thuộc cửa sổ/dải/độ giữ của nguồn dữ liệu; cần thống nhất tiêu chí giữa các lần đo.
Tên mạch và metadata do người dùng/nguồn dữ liệu cung cấp, không phải chứng nhận hỗ trợ mọi topology.
Chưa xác nhận phần cứng, dung sai và lựa chọn linh kiện thực tế.

## Các điểm khả thi (thứ tự điểm số)

| R (Ω) | C (nF) | Vpeak (V) | ts (ns) | Psn (W) | Giá (VND) | mm² | Pareto |
|---|---|---|---|---|---|---|---|
| 10 | 4.7 | 27.5426 | 77.7071 | 0.0417706 | 250 | 3.78 | True |
| 4.7 | 6.8 | 28.1027 | 114.407 | 0.0481804 | 550 | 6.4 | False |
| 2.2 | 10 | 27.9714 | 160.183 | 0.0502521 | 550 | 7.62 | False |
| 10 | 6.8 | 26.566 | 82.8173 | 0.0648387 | 600 | 10.24 | False |
| 4.7 | 10 | 27.1272 | 145.296 | 0.0758822 | 600 | 10.24 | False |
| 10 | 10 | 26.0511 | 79.3145 | 0.100837 | 600 | 10.24 | False |
| 15 | 10 | 27.9259 | 35.8664 | 0.108466 | 600 | 10.24 | False |
| 4.7 | 15 | 26.39 | 183.554 | 0.121222 | 2600 | 23.12 | False |
| 10 | 15 | 25.6225 | 33.4852 | 0.158515 | 3000 | 30.5 | False |
| 15 | 15 | 27.2167 | 32.6134 | 0.167651 | 3000 | 30.5 | False |
