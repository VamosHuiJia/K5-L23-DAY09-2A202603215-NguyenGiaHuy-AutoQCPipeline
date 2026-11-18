# Báo cáo Day 09 — Nguyễn Gia Huy, 2A202603215

## 1. Kết luận trước

Pipeline kết luận **Hold**, mã thoát **10**. Từ 224 ảnh đầu vào, pipeline loại 19 ảnh ở intake và xuất bản nháp gồm 205 ảnh. Sau khi duyệt 80 ảnh, không còn lỗi bắt buộc nhưng vẫn có **38/205 ảnh (18,54%)** còn cảnh báo chưa duyệt, vượt ngưỡng Hold 10%.

## 2. Lỗi và phân việc

Theo `02_error_list_v1.csv`, intake ghi nhận 19 lỗi trên 224 ảnh; QC trên 205 ảnh còn lại có 36 lỗi bắt buộc và 153 cảnh báo. Một ảnh có thể xuất hiện ở nhiều mã; cần phân biệt số dòng/box với số ảnh.

| Mã lỗi | Số ảnh/dòng | Ai sửa (máy/người) | Vì sao |
|---|---:|---|---|
| `BAD_SIZE` | 3 ảnh | Máy | Loại ảnh không đạt kích thước. |
| `CORRUPT_IMAGE` | 2 ảnh | Máy | Loại ảnh không đọc được. |
| `DUP_IMAGE_EXACT` | 8 ảnh | Máy | Loại bản trùng byte. |
| `DUP_IMAGE_NEAR` | 2 ảnh | Máy | Loại bản gần trùng theo pHash. |
| `LEAK_TEST` | 4 ảnh | Máy | Loại ảnh gần trùng với tập test. |
| `BAD_CLASS_ID` | 6 dòng/6 ảnh | Máy | Xóa dòng có ID lớp không hợp lệ. |
| `BAD_FORMAT` | 3 dòng/3 ảnh | Máy | Xóa dòng không đúng định dạng YOLO. |
| `BOX_ZERO` | 4 dòng/4 ảnh | Máy | Xóa box có chiều rộng hoặc cao không dương. |
| `DUP_BOX` | 7 dòng/7 ảnh | Máy | Xóa dòng box lặp phía sau. |
| `BOX_OUT_OF_IMAGE` | 8 dòng/8 ảnh | Máy | Cắt box về biên ảnh; xóa nếu không còn diện tích. |
| `BAD_CLASS_NAME` | 2 lỗi/1 file | Máy | Sửa tên và thứ tự lớp trong `data.yaml`. |
| `MISSING_LABEL_FILE` | 6 ảnh | Người | Máy không tự tạo nhãn; chuyển người gán. |
| `EMPTY_LABEL` | 12 ảnh | Người | Xác nhận ảnh nền hay thiếu nhãn. |
| `BOX_TINY` | 6 box/4 ảnh | Người | Kiểm tra vật nhỏ có cần giữ nhãn không. |
| `BOX_HUGE` | 3 box/3 ảnh | Người | Kiểm tra box có bao đúng vật thể không. |
| `CLASS_RARE` | 4 cảnh báo cấp dataset | Người | Đánh giá phân bố lớp và ID bất thường. |
| `POSSIBLE_MISSING` | 53 cảnh báo/52 ảnh | Người | Xác nhận và bổ sung vật bị bỏ sót. |
| `POSSIBLE_WRONG_CLASS` | 18 cảnh báo/18 ảnh | Người | Đối chiếu vật thể để sửa lớp. |
| `POSSIBLE_LOOSE_BOX` | 28 cảnh báo/24 ảnh | Người | Kiểm tra độ khít và vị trí box. |
| `POSSIBLE_FALSE_POS` | 29 cảnh báo/27 ảnh | Người | Xác nhận box thừa trước khi xóa. |

**Vì sao `05_review_queue.csv` xếp ảnh đầu hàng như vậy?**

Qua `05_review_queue.csv`, em thấy các ảnh được xếp theo điểm ưu tiên từ cao xuống thấp. Điểm được cộng theo loại cảnh báo, độ tin cậy của model và việc ảnh đã bị máy xóa dòng hoặc cắt box. Ảnh `img_0020` có cảnh báo nhầm lớp, thiếu nhãn và từng bị xóa dòng, đạt 11,524 điểm nên được duyệt đầu tiên. Sáu ảnh thiếu file nhãn đạt 10 điểm/ảnh nên xếp sau. Các ảnh bằng điểm được xếp theo tên.

**Với ngân sách 80 ảnh, người xem được bao nhiêu lỗi ngữ nghĩa?**

Trong 80 ảnh đã được duyệt mô phỏng, em thống kê được **74 ảnh có 94 cảnh báo ngữ nghĩa**, gồm 51 cảnh báo thiếu box, 18 nhầm lớp, 12 box lỏng và 13 box thừa. Sáu ảnh còn lại thiếu file nhãn và được gán nhãn mới. Như vậy, bước duyệt đã xử lý **80/125 ảnh** trong hàng đợi. Em ghi 94 là số cảnh báo được xem xét vì log không cho biết bao nhiêu cảnh báo được xác nhận là lỗi thật.

## 3. Calibration (2 ngưỡng)

Hai ngưỡng được chọn từ kết quả kiểm tra trên bộ calib gồm 39 ảnh có đáp án lỗi. **Precision** là tỷ lệ báo lỗi đúng; **recall** là tỷ lệ lỗi đã biết mà công cụ tìm được. Trong bảng, mỗi cặp số được viết theo thứ tự precision / recall.

| Tham số | Khởi đầu | Đã chọn | Precision / Recall (trước → sau) | Lý do (đánh đổi) |
|---|---|---|---|---|
| `duplicates.phash_dist` | 2 | 4 | Gần trùng: 1,000 / 0,500 → 1,000 / 0,667 | Ngưỡng 4 là mức nhỏ nhất giúp tìm thêm ảnh gần trùng: tăng từ 3/6 lên 4/6 ảnh, chưa báo nhầm ảnh sạch. Vẫn bỏ sót 2/6 ảnh. |
| `second_opinion.conf` | 0.25 | 0.6 | Nhầm lớp: 0,556 / 0,833 → 0,625 / 0,833.<br>Thiếu nhãn: 0,500 / 1,000 → 0,571 / 1,000.<br>Box lỏng: 0,286 / 0,400 → 0,200 / 0,200. | Vẫn tìm được 8/8 ca thiếu nhãn và 5/6 ca nhầm lớp, đồng thời giảm báo lỗi nhầm. Tuy nhiên, chỉ tìm được 1/5 ca box lỏng, so với 2/5 ca ở ngưỡng ban đầu. |

Ngưỡng pHash 16 tìm được 5/6 ảnh gần trùng trên calib, nhưng em chưa kiểm tra việc loại ảnh trên raw ở ngưỡng này. Vì vậy, em chọn mức 4 để thận trọng với việc loại ảnh.

Kết quả tốt hơn trên calib chưa chắc đúng với raw. Khi xem hai cặp `img_0042`–`img_0076` và `img_0037`–`img_0143`, em thấy mỗi cặp là cùng một cảnh nên việc loại bản trùng hợp lý. Nhưng cả hai cặp đều có pHash 0, nghĩa là ngưỡng cũ 2 cũng tìm được. Số ảnh bị loại vẫn là 19/224. Vì vậy, em chưa thể kết luận ngưỡng mới tìm thêm được ảnh trùng trên raw. Bảng thử các ngưỡng nằm trong `submission/calibration/`.

## 4. Cửa chặn và điều pipeline KHÔNG bắt được

Để kiểm tra cửa chặn, em chạy pipeline với ngân sách duyệt bằng 0, tức không có người gán hoặc sửa nhãn:

```bash
python -m pipeline.run --budget 0 --work work/run_nb --reports work/rep_nb --export-dir work/exp_nb
```

Khi không có người duyệt, **6/205 ảnh vẫn thiếu file nhãn**. Pipeline kết luận **Rework**, trả mã thoát **20** và không xuất dataset. File `work/rep_nb/08_summary.json` ghi `exported: null`; kiểm tra thư mục `work/exp_nb/clean_v1` trả **False**. Kết quả này cho thấy cửa chặn đã ngăn xuất dữ liệu khi còn lỗi bắt buộc.

Pipeline vẫn bỏ sót lỗi. Kết quả trên calib cho thấy:

- **Box lỏng hoặc lệch:** ở `second_opinion.conf = 0.6`, chỉ tìm được 1/5 ca, bỏ sót **4/5 ca**. Box có thể đúng định dạng nhưng chưa bao đúng vật thể.
- **Ảnh gần trùng:** ở `duplicates.phash_dist = 4`, chỉ tìm được 4/6 ảnh, bỏ sót **2/6 ảnh**. Không bị báo trùng chưa đủ để khẳng định ảnh là duy nhất.

## 5. Train: raw vs clean (tùy chọn, chấm riêng)

Hai biến thể train trên Colab T4, cùng `yolo26n.pt`, 20 epoch, batch 16, ảnh 640 px, seed 0 và 1; dùng chung `gold_val` 40 ảnh chọn checkpoint và test 100 ảnh đo cuối. Bảng từ `submission/results/comparison.md`:

| biến thể | #ảnh train | số seed | map50 (TB ± độ lệch) | map50_95 (TB ± độ lệch) | precision (TB ± độ lệch) | recall (TB ± độ lệch) |
|---|---|---|---|---|---|---|
| raw | 224 | 2 | 0.726 ± 0.000 | 0.512 ± 0.004 | 0.764 ± 0.061 | 0.649 ± 0.028 |
| clean | 205 | 2 | 0.700 ± 0.030 | 0.486 ± 0.013 | 0.715 ± 0.073 | 0.615 ± 0.017 |

Cột số ảnh đếm file đầu vào. Log cả hai seed xác nhận raw thực tế dùng **213 ảnh**, loại 11 ảnh/nhãn lỗi; clean dùng **205 ảnh**, 0 corrupt.

Chênh mAP50 trung bình **clean − raw = −0,0254**; độ lệch chuẩn giữa seed là **0,0002** ở raw và **0,0305** ở clean. Bảng làm tròn độ lệch raw thành 0,000. Clean thấp hơn ở cả hai seed, nhưng chênh trung bình nhỏ hơn độ lệch chuẩn của clean. Hai seed chưa đủ khẳng định tác động ổn định; kết quả không cho thấy clean tốt hơn raw.

Hai giả thuyết cần kiểm: **(1)** raw có 4 ảnh gần trùng test, có thể làm điểm cao hơn; đối chứng bằng bản sao raw chỉ loại bốn ảnh này, giữ nguyên test và cấu hình. **(2)** clean còn 38/205 ảnh cảnh báo chưa duyệt, có thể còn lỗi ngữ nghĩa; cần xác minh, sửa lỗi được xác nhận và đo lại. Các đối chứng chưa chạy. Phân tích năm câu hỏi notebook tại `results/ANALYSIS.md`.

## 6. Quyết định và ghi chú AI

Giữ **Hold**, chuyển ảnh còn nghi vấn về bước kiểm và sửa nhãn ở vòng tiếp theo. Release yêu cầu 0 lỗi bắt buộc và tối đa 20/205 ảnh cảnh báo chưa duyệt; hiện còn 38 ảnh. Giữ nguyên ngân sách 80 ảnh và ngưỡng Hold 10%.

- **Prompt chính:** hỗ trợ vibecode bốn module theo docstring và test; kiểm tra các nhận xét/review, phần còn thiếu và câu văn báo cáo.
- **Kiểm chứng:** chạy test riêng từng module và toàn bộ bộ test đạt 79/79; đối chiếu nhận xét với báo cáo pipeline, calibration và log train.
- **Sai sót và khắc phục:** bản nháp đầu đổi các cột bảng của mẫu; đã đối chiếu và khôi phục đúng các tiêu đề mục, cột bảng ban đầu.
