"""BƯỚC 2/4 — Sửa tự động những lỗi bắt buộc mà máy sửa được AN TOÀN.   ★★

Test:  pytest tests/test_autofix.py -q

`fix(ds, issues, cfg) -> list[dict]`: duyệt `issues` (chỉ lỗi severity ERROR), sửa thẳng vào thư mục `ds`,
và trả về danh sách thay đổi; mỗi phần tử có khoá: image, line, action, before, after
(đây chính là file `03_fixes.csv` — bằng chứng pipeline đã làm gì, người có thể kiểm lại).

| code lỗi                                       | cách sửa                                    | action           |
|------------------------------------------------|---------------------------------------------|------------------|
| BAD_FORMAT, BAD_CLASS_ID, BOX_ZERO, DUP_BOX    | xoá dòng đó khỏi file nhãn                  | "drop_line"      |
| BOX_OUT_OF_IMAGE                               | cắt box về trong [0,1] (giữ nguyên lớp)     | "clip_box"       |
| MISSING_LABEL_FILE                             | KHÔNG sửa file (máy không thể bịa nhãn): ghi 1 dòng fix, before="(không có file)", after="chuyển người gán" | "needs_label" |
| BAD_CLASS_NAME                                 | ghi lại `names` trong data.yaml đúng `cfg["classes"]` | "rename_classes" |
| DUP_IMAGE_*, LEAK_TEST, CORRUPT_IMAGE, BAD_SIZE| xoá ảnh + nhãn khỏi `ds`                    | "remove_image"   |

Bẫy cần nghĩ tới (có test cho từng cái)
- Một file có NHIỀU dòng lỗi: số dòng trong `issues` là số dòng GỐC. Nếu xoá từng dòng một thì số dòng lệch.
  Gom theo file, rồi ghi lại MỘT lần.
- Sau khi cắt, box có thể không còn diện tích (nằm hẳn ngoài ảnh): lúc đó xoá dòng thay vì ghi box rỗng.
- Một dòng có 2 lỗi (vd. BOX_OUT_OF_IMAGE + DUP_BOX): xoá dòng thắng, chỉ ghi 1 fix `drop_line`, không ghi thêm `clip_box`. Dòng trống ở giữa file vẫn đếm vào số dòng gốc.
- Ảnh vừa bị xoá (DUP_IMAGE_*...) mà còn issue dòng của chính nó: bỏ qua êm, không được báo lỗi/chết.
- Không động tới lỗi WARN (cảnh báo là việc của người). Không sửa file ở `data/raw/` — chỉ sửa `ds`.
- Chạy lần 2 trên dữ liệu đã sửa phải không làm gì thêm (idempotent) — NGOẠI LỆ duy nhất: `needs_label` được ghi lại mỗi lần còn lỗi `MISSING_LABEL_FILE` (vì ảnh vẫn chưa có nhãn).

- `needs_label` KHÔNG tạo file nhãn rỗng (rỗng = "ảnh nền", khác với "chưa gán"). `review_queue` sẽ đẩy ảnh này lên đầu hàng đợi cho người.

Gợi ý: `yaml.safe_load / safe_dump`.
"""
from collections import defaultdict

import yaml

from ..common import ERROR, ROOT, parse_yolo_line


def _clip_line(text):
    """Trả về dòng đã cắt box; None nếu dòng không thể giữ lại."""
    try:
        class_id, cx, cy, width, height = parse_yolo_line(text)
    except (ValueError, OverflowError):
        return None

    if width <= 0 or height <= 0:
        return None

    left, right = cx - width / 2, cx + width / 2
    top, bottom = cy - height / 2, cy + height / 2
    if 0 <= left <= right <= 1 and 0 <= top <= bottom <= 1:
        return text

    left, right = max(0.0, left), min(1.0, right)
    top, bottom = max(0.0, top), min(1.0, bottom)
    if right <= left or bottom <= top:
        return None

    box = ((left + right) / 2, (top + bottom) / 2,
           right - left, bottom - top)
    return f"{class_id} " + " ".join(f"{value:.12g}" for value in box)


def fix(ds, issues, cfg):
    errors = [issue for issue in issues if issue.severity == ERROR]
    if not errors:
        return []

    # Pipeline phải truyền bản sao làm việc, không được truyền bộ raw gốc.
    raw_root = (ROOT / "data" / "raw").resolve()
    dataset_root = ds.root.resolve()
    if dataset_root == raw_root or raw_root in dataset_root.parents:
        raise ValueError("autofix chỉ được sửa bản sao dataset, không được sửa raw")

    drop_codes = {"BAD_FORMAT", "BAD_CLASS_ID", "BOX_ZERO", "DUP_BOX"}
    remove_codes = {"LEAK_TEST", "CORRUPT_IMAGE", "BAD_SIZE"}
    remove_stems = set()
    needs_label = set()
    line_issues = defaultdict(lambda: defaultdict(set))
    rename_classes = False

    for issue in errors:
        if issue.code.startswith("DUP_IMAGE_") or issue.code in remove_codes:
            remove_stems.add(issue.image)
        elif issue.code == "BAD_CLASS_NAME":
            rename_classes = True
        elif issue.code == "MISSING_LABEL_FILE":
            needs_label.add(issue.image)
        elif (issue.code in drop_codes or issue.code == "BOX_OUT_OF_IMAGE"):
            if isinstance(issue.line, int) and issue.line > 0:
                line_issues[issue.image][issue.line].add(issue.code)

    changes = []

    def record(image, line, action, before, after):
        changes.append(dict(image=image, line=line, action=action,
                            before=before, after=after))

    image_paths = {path.stem: path for path in ds.image_files()}

    # Loại ảnh trước để không còn sửa nhãn của chính ảnh vừa bị loại.
    for stem in sorted(remove_stems):
        paths = [image_paths.get(stem), ds.label_path(stem)]
        existing = [path for path in paths if path is not None and path.exists()]
        if not existing:
            continue
        before = "; ".join(path.name for path in existing)
        for path in existing:
            path.unlink()
        record(stem, None, "remove_image", before, "(đã loại ảnh và nhãn)")

    if rename_classes:
        if ds.yaml_path.exists():
            data = yaml.safe_load(ds.yaml_path.read_text(encoding="utf-8")) or {}
        else:
            data = {}
        if not isinstance(data, dict):
            data = {}
        names = dict(enumerate(cfg["classes"]))
        old_names = data.get("names")
        if old_names != names and old_names != cfg["classes"]:
            data["names"] = names
            ds.yaml_path.write_text(
                yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )
            record("data.yaml", None, "rename_classes",
                   yaml.safe_dump(old_names, allow_unicode=True).strip(),
                   yaml.safe_dump(names, allow_unicode=True).strip())

    for stem in sorted(needs_label - remove_stems):
        if stem in image_paths and not ds.label_path(stem).exists():
            record(stem, None, "needs_label",
                   "(không có file)", "chuyển người gán")

    for stem in sorted(line_issues):
        label_path = ds.label_path(stem)
        if stem in remove_stems or not label_path.exists():
            continue

        original = label_path.read_text(encoding="utf-8", errors="replace")
        updated = []
        # Giữ cả dòng trống khi đếm, và giữ nguyên các dòng không cần sửa.
        for line, raw_line in enumerate(original.splitlines(keepends=True), 1):
            codes = line_issues[stem].get(line, set())
            if not codes:
                updated.append(raw_line)
                continue

            before = raw_line.rstrip("\r\n")
            # Xóa dòng thắng cắt box, mỗi dòng chỉ có tối đa một bản ghi sửa.
            after = None if codes & drop_codes else _clip_line(before)
            if after is None:
                record(stem, line, "drop_line", before, "")
            elif after == before:
                updated.append(raw_line)
            else:
                ending = raw_line[len(before):]
                updated.append(after + ending)
                record(stem, line, "clip_box", before, after)

        new_text = "".join(updated)
        if new_text != original:
            label_path.write_text(new_text, encoding="utf-8")

    return changes
