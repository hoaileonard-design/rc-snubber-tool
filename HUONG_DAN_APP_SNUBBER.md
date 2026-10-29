# Dùng tiếp app snubber của nhóm

Mở `CHAY_APP.cmd` trong thư mục này. Đây là app cũ, tiếp tục dùng `main.py`, CustomTkinter và ba tab cũ được bổ sung chức năng.

## Mạch tương tác Falstad (bổ sung 29/10)

1. Chọn tab **4. Mạch tương tác**, bấm **Mở bàn mạch**. Bàn mạch hiển thị ngay trong tab này. Thanh điều khiển bên trái cuộn riêng để sơ đồ luôn hiện trên màn hình.
2. Ở bàn mạch, chọn **A · Chưa có snubber**, bấm **Ghi và gửi về app**. App nhận dạng sóng và chuyển sang tab phân tích.
3. Quay lại bàn mạch, chọn **B · Đã gắn RC**, ghi một lần nữa. Lặp lại với **Tụ thử** để app nhận dạng Lp/Cp. R/C, L/Cp, nguồn, tụ thử có thể chỉnh trên bàn mạch.
4. Muốn thử cặp R/C vừa chọn từ dữ liệu, tại tab 4 bấm **Lấy R/C đang chọn**, rồi **Cập nhật thông số**. Trong bàn mạch bấm **Lấy thông số từ app** để dựng lại mẫu. Nút **Thông số mẫu** hiện các ô nhập của desktop. Các giá trị Lp/Cp và nguồn của mẫu cần được kiểm tra riêng.
5. Chế độ **Mạch tự vẽ / nhập trong CircuitJS** giữ sơ đồ bạn đang sửa, yêu cầu ghi vai trò, tên điều kiện dùng chung và hai điểm đo. Bạn tự đặt snubber và nguồn kích thích. Dùng cùng điều kiện và hai điểm cho bộ A/B/tụ thử. Cửa sổ cần chứa một cạnh điện áp tăng; mạch không có dao động có thể không nhận dạng được L/C.

App dùng Microsoft Edge WebView2 để hiển thị Falstad trong cửa sổ CustomTkinter hiện có. Không mở trình duyệt bên ngoài. Trên máy hiện tại đã cài `tkwry==0.1.9` và có WebView2 Runtime; khi chuyển máy Windows, cài requirements và kiểm tra Runtime. REA và Node chỉ phục vụ phát triển. Tài nguyên Falstad được đóng gói cục bộ. Tab 4 có nút **Đóng bàn mạch**; các bản ghi đã lưu vẫn được giữ. Dữ liệu tạm WebView2 nằm ở `data/webview2/` và tách riêng khỏi CSV.

Mẫu mặc định là **RLC minh họa**, không phải Buck P6: nguồn bước 24 V có thể tạo đỉnh khoảng 48 V khi chưa snubber. Số liệu này được lưu riêng với nhãn Falstad. Thay giá trị mẫu sẽ nạp và chạy lại từ đầu. Dữ liệu lưu trong `data/falstad_captures/`; không chép đè kết quả P6. Xem [phân tích và bằng chứng](docs/PHAN_TICH_REA_FALSTAD.md).

## Thử ngay với kết quả nhóm đã có

1. Ở tab **Phân tích dạng sóng**, bấm **Thử ngay dữ liệu P6** phía trên bên phải. App nạp ba dạng sóng: chưa snubber, sau RC, và chỉ gắn tụ thử 470 pF.
2. Kết quả trước snubber: đỉnh khoảng 38,8435 V, dao động 30,3908 MHz, chưa xác lập trong cửa sổ. App nhận dạng khoảng Lp=100,12 nH, Cp=273,93 pF. Đây là thông số tương đương của ca Buck này.
3. Qua tab **Tối ưu & kiểm chứng**, chọn `L100_Rload10_grid`, bấm **Nạp ví dụ P6 đã có**. Chọn trọng số công suất=1, giá=0, kích thước=0 rồi **Chạy tối ưu**. Kết quả là 10 Ω / 4,7 nF, cùng lựa chọn P6 theo tổn hao nhánh snubber.
4. Đổi trọng số hoặc giới hạn rồi chạy lại để xem vùng khả thi. Vòng xanh: đạt các ràng buộc; hình thoi: Pareto (không có điểm khác tốt hơn hoặc bằng ở cả ba mục tiêu, tốt hơn ở ít nhất một); ngôi sao: cặp được chọn theo trọng số. Chấm màu chỉ là điểm đã khảo sát.
5. Bấm **Xuất báo cáo + bảng CSV** để lưu kết quả đã tính. Báo cáo ghi lại tiêu chí, mạch, hai nút, nguồn, mức kiểm chứng và dấu vân tay file. Nếu đổi ô nhập sau khi tính, cần chạy lại để có kết quả theo giá trị mới.

## Dùng với một mạch khác

Tên Buck/Flyback không làm app tự chọn vị trí gắn snubber. Xác định hai nút cần dập dao động, điều kiện điện áp/tải/tần số, và mục đích RC dập dao động hay RCD kẹp/hạn chế tăng áp.

- Xuất file CSV/TXT hai cột **thời gian (s), điện áp (V)**. Dữ liệu phải hữu hạn, thời gian tăng và không trùng. App đọc hai cột đầu; nếu file có nhiều kênh, xuất riêng kênh điện áp cần khảo sát trước. Nếu oscilloscope xuất thời gian theo ns/µs, đổi về giây trước khi nạp.
- Chọn cửa sổ **một cạnh điện áp tăng** bằng các ô Từ/Đến (ns). Không trộn nhiều sự kiện, chu kỳ PWM hoặc tín hiệu âm vào phép nhận dạng này. Plateau là điện áp nền sau chuyển mạch, không mặc định là Vin. Có thể lấy plateau từ đoạn ổn định dài hơn và nhập tay.
- **File A**: chưa snubber. **File B**: sau snubber, dùng so sánh. **File tụ thử**: cùng mạch và điều kiện với A, chỉ thêm tụ biết trước song song vào cùng hai nút; đây là phép thử khác B.
- Phép dịch tần: Cp=Cthử/[(f0/f1)²−1], Lp=1/[(2πf0)²Cp]. R≈√(Lp/Cp), C≈3Cp chỉ là giá trị khởi đầu, không phải bộ tối ưu đã đạt.
- Tạo bảng khảo sát từ SPICE hoặc phép đo của chính mạch đó. App hiện nhận **kết quả đã chạy**, chưa tự đọc sơ đồ bất kỳ để gắn snubber và chạy LTspice thay người dùng.
- Nạp bảng ở tab Tối ưu, ghi mạch/điều kiện và hai nút, đặt giới hạn áp/ts/công suất và trọng số. Mỗi bảng chỉ được chứa **một điều kiện vận hành và một loại RC hoặc RCD**.

## Bảng CSV khảo sát

Các cột bắt buộc:

| Cột | Ý nghĩa/đơn vị |
|---|---|
| `R_ohm` | Điện trở snubber, Ω |
| `C_F` | Tụ snubber, F (4,7 nF nhập `4.7e-9`) |
| `VDS_MAX_V` | Đỉnh điện áp tại hai nút khảo sát, V; giữ tên này để tương thích dữ liệu P6 |
| `ts_ns` | Thời gian xác lập, ns; thống nhất dải và thời gian giữ trong cả bảng |
| `ts_censored` | `True` nếu chưa xác lập/không đo đủ, `False` nếu ts quan sát được |
| `P_snubber_W` | Tổng công suất nhánh snubber, W; RCD bao gồm diode |

Cột tùy chọn: `kind` (RC/RCD), `case`, `topology`, `node`, `evidence`, `raw`, `cost_vnd`, `area_mm2`. Nếu dùng giá/diện tích thực tế, nhập đủ cả hai cột. Với RCD bắt buộc cung cấp giá/diện tích toàn bộ R+C+D, tránh bỏ quên diode. Không chọn điểm bị censored dù trọng số thời gian bằng gì; thời gian là ràng buộc cứng.

File JSON cùng tên CSV (tùy chọn) chứa `circuit`, `node`, `v_target` và thông tin điều kiện/kiểm chứng. Đây là khai báo của nguồn dữ liệu, app không chứng thực nội dung. Xem các ví dụ P6.

## Cần hiểu đúng kết quả

- App tìm lựa chọn tốt trong các điểm đã nạp, không chứng minh cực tiểu toàn cục. Giá/diện tích danh mục là ước lượng theo gói linh kiện, không phải mã mua hàng đã xác nhận chịu xung.
- Psn không phải tổng tổn hao bộ nguồn. Muốn so hiệu suất cần thêm tổn hao đóng/mở, dẫn, cuộn cảm, driver và nguồn phụ trong cùng điều kiện.
- Chín bộ dữ liệu P6 là chín điều kiện của **một cấu trúc Buck**. App có thể nhận cùng định dạng cho mạch khác, nhưng cần dữ liệu mạch khác để kiểm chứng.
- Dữ liệu P6 gồm sàng lọc 1 ns, một số điểm chạy 0,5 ns và điểm chọn đã đối chiếu 0,25 ns. Kết quả mịn, kể cả điểm không đạt, được ưu tiên thay số sàng lọc. Mức bằng chứng hiện ngay dưới nút xuất.
- Mô hình RLC ở chế độ tham khảo giữ điều kiện hợp lệ cũ. Ca Vpeak<2Vin không phù hợp phép suy dòng của mô hình này; dùng nhánh đánh giá theo dữ liệu. Không thay Vpeak đo bằng số giả.
- ζ từ suy giảm các đỉnh là ước lượng một mode; nhiễu, thiếu băng thông, nhiều mode và Coss phi tuyến có thể làm sai. Không đủ đỉnh thì app báo chưa nhận dạng.
- Chưa có xác nhận trên phần cứng hoặc tự động tổng hợp mọi loại RCD. Chưa kiểm chứng Flyback/cầu bằng dữ liệu độc lập trong bản này.
