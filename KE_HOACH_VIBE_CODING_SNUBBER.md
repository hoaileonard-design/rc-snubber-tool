# Phát triển tiếp app snubber hiện có

Ngày 27/10/2026. Mã nguồn tiếp tục tại `C:\Doantotnghiep\APP_khoiphuc`, dùng CustomTkinter, các engine và ba tab hiện có. Không dựng app khác.

## Đích sử dụng

Người dùng chọn một điểm chuyển mạch và một điều kiện vận hành, nạp dạng sóng chưa snubber, nhận dạng dao động, bổ sung phép đo với tụ thử nếu muốn suy ra Lp/Cp, rồi đánh giá nhiều R/C bằng dữ liệu của chính mạch đó. Đề xuất phải nêu rõ giới hạn điện áp, thời gian xác lập, tổn hao snubber, trọng số giá/diện tích và nguồn bằng chứng.

Phương pháp không cố định Buck hoặc Flyback. Điều này không có nghĩa một bộ R/C dùng cho mọi mạch, hoặc app tự biết vị trí gắn snubber từ tên mạch. RC dập dao động và RCD kẹp áp cần thiết kế đúng mục đích. App nhận bảng khảo sát RC hoặc RCD; nhận dạng hai tần số chỉ là ước lượng mạch cộng hưởng tương đương.

## Các vòng làm việc và điều kiện đạt

1. **Giữ nền cũ.** Ghi lại thay đổi chưa commit và chạy bộ test gốc. Giữ tính toán lý thuyết, các bảng giá/kích thước đang có, tài liệu và dữ liệu P5/P6 gốc.
2. **Sửa phân tích dạng sóng.** Chọn cửa sổ một sự kiện, không bỏ đỉnh đầu, đo tần số từ những chu kỳ đầu, thêm ζ từ suy giảm biên độ, thống nhất dải ±5%. Nếu chưa ở trong dải đủ lâu thì báo chưa xác lập, không trả cuối cửa sổ như kết quả đo. Kiểm tra dữ liệu hữu hạn, thời gian tăng và mẫu đủ dày.
3. **Nhận dạng Lp/Cp trong app.** Giữ file B để so trước/sau; thêm file tụ thử riêng. Dùng f0, f1 và Cthử cùng điểm mạch, cùng điều kiện để tính Cp, Lp và R/C khởi đầu. Từ chối khi f1 không giảm hoặc không nhận diện được dao động. Không đồng nhất điện áp plateau với điện áp nguồn vào khi đổi loại mạch.
4. **Tối ưu bằng dữ liệu.** Mở rộng tab Optimizer hiện có bằng chế độ nhập bảng SPICE/phép đo. Lọc cả Vpeak, ts, trạng thái chưa xác lập và giới hạn công suất. Chuẩn hóa công suất/giá/diện tích theo trọng số, hiển thị vùng khả thi và tập Pareto. Không nội suy ô chưa chạy thành số liệu đã kiểm chứng. Giữ mô hình RLC cũ ở chế độ tham khảo, giải thích phạm vi áp dụng.
5. **Kết quả có thể kiểm tra.** Xuất Markdown và CSV chứa thông tin mạch/điểm gắn, tên và dấu vân tay file đầu vào, tiêu chí, cặp chọn, các điểm khả thi, trạng thái kiểm chứng và giới hạn. Giá/diện tích mặc định là ước lượng danh mục, công suất snubber không đồng nghĩa tổng tổn hao hệ thống.
6. **Demo và kiểm tra.** Đưa bản sao dữ liệu P6 vào thư mục ví dụ của app; giữ riêng chín điều kiện Buck và đánh dấu điểm sàng lọc 1 ns so với điểm đã kiểm tra bước thời gian nhỏ hơn. Kiểm thử hồi quy lỗi đỉnh đầu, nhận dạng, kiểm tra dữ liệu xấu, ràng buộc ts, thay đổi trọng số và xuất báo cáo. Chạy smoke test giao diện nếu môi trường cho phép; ghi rõ mức kiểm tra.

## Quy tắc triển khai theo vibe coding

Mỗi vòng là một thay đổi dùng được, có ví dụ và kiểm tra độc lập. Dùng lại engine và widget sẵn có; không đổi framework, không thêm backend hoặc tài khoản. Kế hoạch và trạng thái cập nhật cùng mã nguồn. Không dùng số test đạt để tuyên bố mô hình vật lý đúng.

## Nguồn kỹ thuật

- TI, *Power Tips: Calculate an R-C Snubber in Seven Steps*: https://www.ti.com/document-viewer/lit/html/SSZTBC7 — phép dịch tần với tụ thử, các giá trị khởi đầu cần kiểm chứng.
- Analog Devices, *R-C Snubbing for the Lab*: https://www.analog.com/en/resources/technical-articles/2022/07/16/07/30/rc-snubbing-for-the-lab.html
- Analog Devices, *Snubber Circuits Suppress Voltage Transient Spikes*: https://www.analog.com/en/resources/technical-articles/snubber-circuits-suppress-voltage-transient-spikes.html — phân biệt dập dao động, hạn chế tốc độ tăng áp và kẹp áp.
- Đối chứng nội bộ: `..\LTspice\Driver\khao_sat_p6\CAC_VAN_DE_APP_CHO_P8.md` và dữ liệu P6, không sửa các bằng chứng này.

## Phần cần bằng chứng tiếp theo

Dữ liệu hiện có kiểm chứng trên Buck. Muốn tuyên bố hỗ trợ đã kiểm chứng cho Flyback/cầu/loại khác phải bổ sung mô phỏng hoặc phép đo của chúng. Nhập được dữ liệu không chứng minh đã thiết kế đúng mọi topology. Chọn diode/kẹp RCD, khả năng chịu xung, dung sai linh kiện và phần cứng vẫn cần kiểm chứng riêng. Tự động dựng/mô phỏng mọi sơ đồ bất kỳ không thuộc năng lực đã có của app.

Trạng thái vòng đầu: đã triển khai sáu vòng theo phạm vi nhận dạng và tối ưu bằng dữ liệu. Kết quả 62/62 test, hồi quy 9/9 điều kiện P6 và smoke test callback ba tab. Chi tiết và giới hạn ở `TRANG_THAI_P8.md`; chưa coi toàn bộ P8 hoặc phạm vi mọi topology là hoàn tất.

## Vòng bổ sung 29/10 — mạch tương tác

Theo yêu cầu tiếp theo, đã cài REA cho Codex/Claude Code, phân tích bản Falstad v115 phát hành và bổ sung tab 4 trên app hiện có. Bản đầu mở trình duyệt; bản hiện tại nhúng WebView2/tkwry trực tiếp vào tab, giữ cầu nối loopback. Đã kiểm tra khung con Windows, đổi tab, co giãn, đóng/mở lại và ba dạng sóng RLC gửi về phần phân tích. Hỗ trợ chọn hai điểm và ghi mạch tự vẽ với điều kiện rõ ràng; chưa tự đặt snubber hoặc chuyển mọi sơ đồ sang LTspice. Bằng chứng và giới hạn trong `docs/PHAN_TICH_REA_FALSTAD.md`, `verification/falstad_embedded/result.json`.
