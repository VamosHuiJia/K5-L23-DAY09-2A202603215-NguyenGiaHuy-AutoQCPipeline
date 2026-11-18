# Phân tích train raw vs clean

Em so sánh raw và clean bằng `yolo26n.pt`, 20 epoch, batch 16, ảnh 640 px và seed 0, 1 trên Colab T4. Hai biến thể dùng chung validation 40 ảnh và test 100 ảnh.

## 1. Chênh mAP50 so với độ lệch chuẩn giữa các seed

Từ `comparison.json`, em tính được chênh mAP50 trung bình **clean − raw = −0,0254**, tức clean thấp hơn raw 2,54 điểm phần trăm. Raw đạt **0,7258 ± 0,0002**, còn clean đạt **0,7004 ± 0,0305**.

Em thấy clean thấp hơn raw ở cả hai seed, nhưng mức chênh trung bình nhỏ hơn độ lệch chuẩn của clean là 0,0305. Vì chỉ có hai seed, em chưa thể kết luận mức giảm này ổn định. Kết quả hiện tại không cho thấy clean tốt hơn raw.

## 2. Raw thật sự train trên bao nhiêu ảnh?

Em đối chiếu log của cả hai seed và xác nhận raw thực tế dùng **213 ảnh**, sau khi loại **11 ảnh/nhãn lỗi** trong 224 ảnh đầu vào. Log ghi:

```text
Using 213 train, 40 val images for fraction=1.0 at imgsz=640
```

Các ảnh bị loại có lỗi như ảnh hỏng, ID lớp sai, box tràn ảnh hoặc dòng nhãn sai định dạng. Em lưu ý `train_images: 224` trong JSON chỉ đếm file đầu vào, trước khi loader loại lỗi. Clean thực tế dùng **205 ảnh**, có 4 ảnh nền và 0 ảnh/nhãn lỗi bị loại.

## 3. Raw có ảnh trùng với test không? Điểm bị thổi phồng bao nhiêu?

Theo `01_intake.csv`, em tìm thấy **4 ảnh raw gần trùng với test**:

| Ảnh raw | Ảnh test |
|---|---|
| `img_0049.jpg` | `test_033.jpg` |
| `img_0167.jpg` | `test_044.jpg` |
| `img_0174.jpg` | `test_085.jpg` |
| `img_0221.jpg` | `test_009.jpg` |

Em đã xem bốn cặp ảnh và thấy cùng cảnh, cùng vị trí vật thể nhưng khác kích thước. Cả bốn ảnh vẫn nằm trong tập train raw và đã được loại khỏi clean.

Em **chưa xác định được điểm raw bị tăng bao nhiêu do rò rỉ**. Em không thể quy chênh 0,0254 giữa raw và clean chỉ cho bốn ảnh này, vì hai tập còn khác nhau về ảnh bị loại và nhãn đã sửa.

Để kiểm tra, em sẽ so sánh raw với một bản sao chỉ loại bốn ảnh trên, giữ nguyên các nhãn còn lại, cấu hình và tập đánh giá. Em chưa chạy phép so sánh này.

## 4. Lớp nào được lợi hoặc bị giảm nhiều nhất?

Em tính AP50 trung bình hai seed từ `ap50_per_class`:

| Lớp | Raw | Clean | Clean − raw |
|---|---:|---:|---:|
| car | 0,73750 | 0,74845 | +0,01095 |
| person | 0,82205 | 0,82735 | +0,00530 |
| truck | 0,64845 | 0,55880 | −0,08965 |
| bus | 0,69490 | 0,66665 | −0,02825 |

Em thấy **car tăng nhiều nhất**, khoảng 1,095 điểm phần trăm AP50; truck giảm nhiều nhất, khoảng 8,965 điểm phần trăm.

Trong `02_error_list_v1.csv`, em ghi nhận 18 cảnh báo nhầm lớp và 53 cảnh báo thiếu nhãn. Ví dụ, `img_0019` và `img_0037` có nhãn truck nhưng checker dự đoán car. Việc xác nhận và sửa những nhầm lẫn này có thể giúp model nhận diện car tốt hơn. Tuy nhiên, em chưa có phép so sánh riêng để khẳng định đây là nguyên nhân tăng AP50.

## 5. Clean còn lỗi gì? Có phải chặn trên của dữ liệu sạch không?

Theo `07_error_list_v3.csv`, em ghi nhận clean không còn lỗi bắt buộc, nhưng vẫn có **42 cảnh báo trên 38/205 ảnh chưa duyệt**:

| Mã cảnh báo | Số cảnh báo | Số ảnh |
|---|---:|---:|
| `POSSIBLE_LOOSE_BOX` | 16 | 16 |
| `POSSIBLE_FALSE_POS` | 11 | 11 |
| `POSSIBLE_MISSING` | 2 | 2 |
| `BOX_TINY` | 6 | 4 |
| `BOX_HUGE` | 3 | 3 |
| `EMPTY_LABEL` | 4 | 4 |

Em chỉ xem các cảnh báo này là nghi vấn, cần kiểm tra ảnh để xác nhận lỗi. Một ảnh có thể mang nhiều mã nên không cộng số ảnh giữa các hàng.

Hàng đợi có **125 ảnh**, nhưng chỉ duyệt được 80 ảnh, còn 45 ảnh chưa xem. Tỷ lệ ảnh cảnh báo chưa duyệt là **38/205 = 18,54%**, nên pipeline kết luận **Hold**.

Vì vậy, em **chưa coi clean là chặn trên của dữ liệu sạch**. Bộ này vẫn còn ảnh chưa được kiểm tra và có thể còn lỗi mà checker bỏ sót. Em cần xác minh các cảnh báo, sửa lỗi được xác nhận và kiểm tra lại trước khi phát hành.
