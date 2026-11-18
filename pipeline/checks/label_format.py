"""CHECK 2 — Dòng nhãn YOLO: sai định dạng, ID lớp lạ, box tràn ảnh, box rỗng, box lặp.   (Script 2 trong slide)   ★★

Test:  pytest tests/test_label_format.py -q

Mỗi dòng nhãn: `id cx cy w h` (5 số, toạ độ 0–1). Trả về list[Issue]; `Issue.line` = số dòng (đếm từ 1).

| code             | severity | khi nào                                                                  |
|------------------|----------|--------------------------------------------------------------------------|
| BAD_FORMAT       | ERROR    | không đúng 5 cột số (dùng `parse_yolo_line`, bắt `ValueError`)           |
| BAD_CLASS_ID     | ERROR    | id lớp ngoài 0..len(ds.classes)-1                                        |
| BOX_ZERO         | ERROR    | w <= 0 hoặc h <= 0                                                       |
| BOX_OUT_OF_IMAGE | ERROR    | mép box vượt [0,1] quá `cfg["label_format"]["overflow_tol"]`; extra={"overflow": mức tràn} |
| DUP_BOX          | ERROR    | cùng lớp với một dòng TRƯỚC ĐÓ và IoU > `dup_box_iou`; báo ở dòng SAU    |
| BOX_TINY         | WARN     | cạnh ngắn của box (px) < `min_box_px`  (cần `ds.image_size(stem)`)       |
| BOX_HUGE         | WARN     | w*h > `max_box_frac`                                                     |

Gợi ý
- Mép trái = x - w/2, mép phải = x + w/2 (xem câu hỏi "dòng YOLO nào lỗi?" trong slide).
- Một dòng hỏng (BAD_FORMAT, BAD_CLASS_ID, BOX_ZERO) thì `continue`, đừng kiểm tiếp hình học của dòng đó.
- Dòng thiếu cột làm script của slide dừng giữa chừng: đây là lý do phải `try/except`.
- `iou_xywh(a, b)` có sẵn trong common.py.
- Ngưỡng nằm trong `cfg["label_format"]` — đừng viết cứng số vào code.
"""
from ..common import ERROR, WARN, Issue, iou_xywh, parse_yolo_line


def run(ds, cfg):
    limits = cfg["label_format"]
    issues = []

    for label_file in ds.label_files():
        stem = label_file.stem
        image_size = ds.image_size(stem)
        previous_boxes = {}

        # Dataset bỏ dòng trống nhưng giữ nguyên số dòng trong file gốc.
        for line, text in ds.read_label_lines(stem) or []:
            try:
                class_id, cx, cy, width, height = parse_yolo_line(text)
            except (ValueError, OverflowError) as exc:
                issues.append(Issue(
                    "label_format", ERROR, "BAD_FORMAT", stem,
                    f"dòng nhãn không hợp lệ: {exc}", line,
                ))
                continue

            if not 0 <= class_id < len(ds.classes):
                issues.append(Issue(
                    "label_format", ERROR, "BAD_CLASS_ID", stem,
                    f"id lớp {class_id} ngoài phạm vi 0..{len(ds.classes) - 1}", line,
                ))
                continue

            if width <= 0 or height <= 0:
                issues.append(Issue(
                    "label_format", ERROR, "BOX_ZERO", stem,
                    f"box có rộng/cao không dương: w={width:g}, h={height:g}", line,
                ))
                continue

            left, right = cx - width / 2, cx + width / 2
            top, bottom = cy - height / 2, cy + height / 2
            overflow = max(0.0, -left, -top, right - 1, bottom - 1)
            if overflow > limits["overflow_tol"]:
                issues.append(Issue(
                    "label_format", ERROR, "BOX_OUT_OF_IMAGE", stem,
                    f"box tràn {overflow:g}, vượt dung sai {limits['overflow_tol']:g}",
                    line, {"overflow": overflow},
                ))

            # Chỉ so với các dòng trước đó có cùng lớp; mỗi dòng báo trùng một lần.
            box = (cx, cy, width, height)
            same_class_boxes = previous_boxes.setdefault(class_id, [])
            if any(iou_xywh(box, old_box) > limits["dup_box_iou"]
                   for old_box in same_class_boxes):
                issues.append(Issue(
                    "label_format", ERROR, "DUP_BOX", stem,
                    f"box cùng lớp trùng dòng trước với IoU > {limits['dup_box_iou']:g}",
                    line,
                ))
            same_class_boxes.append(box)

            # Không có kích thước ảnh thì vẫn kiểm các quy tắc tọa độ ở trên.
            if image_size is not None:
                image_width, image_height = image_size
                short_side_px = min(width * image_width, height * image_height)
                if short_side_px < limits["min_box_px"]:
                    issues.append(Issue(
                        "label_format", WARN, "BOX_TINY", stem,
                        f"cạnh ngắn {short_side_px:g}px < {limits['min_box_px']:g}px",
                        line,
                    ))

            area_frac = width * height
            if area_frac > limits["max_box_frac"]:
                issues.append(Issue(
                    "label_format", WARN, "BOX_HUGE", stem,
                    f"diện tích box {area_frac:g} > {limits['max_box_frac']:g} diện tích ảnh",
                    line,
                ))

    return issues
