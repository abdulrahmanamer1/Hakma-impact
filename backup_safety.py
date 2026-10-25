"""Safe extraction helpers for administrator-uploaded backup archives."""
import os
import shutil
import stat


def safe_extract_backup_zip(archive, destination, max_entries=20000,
                            max_uncompressed=500 * 1024 * 1024):
    """Extract only expected backup members after validating every path and type."""
    infos = archive.infolist()
    if len(infos) > max_entries:
        raise ValueError("النسخة تحتوي عدداً كبيراً جداً من الملفات")
    total_uncompressed = sum(max(0, info.file_size) for info in infos)
    if total_uncompressed > max_uncompressed:
        raise ValueError("حجم الملفات بعد فك الضغط يتجاوز الحد المسموح")

    destination = os.path.abspath(destination)
    seen = set()
    normalized = []
    for info in infos:
        name = info.filename.replace("\\", "/")
        normalized_name = name.rstrip("/")
        parts = normalized_name.split("/")
        if (not normalized_name or name.startswith("/")
                or any(part in ("", ".", "..") for part in parts)
                or "\x00" in name):
            raise ValueError("مسار غير آمن داخل النسخة الاحتياطية")
        if name not in ("manifest.json", "data/ahvt.sqlite") and not name.startswith("uploads/"):
            raise ValueError("النسخة تحتوي ملفاً غير مسموح")
        if normalized_name in seen:
            raise ValueError("النسخة تحتوي أسماء ملفات مكررة")
        seen.add(normalized_name)
        mode = (info.external_attr >> 16) & 0o170000
        if mode == stat.S_IFLNK or (mode not in (0, stat.S_IFREG, stat.S_IFDIR)):
            raise ValueError("نوع ملف غير مسموح داخل النسخة")
        if info.is_dir():
            normalized.append((info, normalized_name, True))
        else:
            normalized.append((info, normalized_name, False))

    if "data/ahvt.sqlite" not in seen:
        raise ValueError("النسخة لا تحتوي قاعدة بيانات AHVT")

    for info, name, is_dir in normalized:
        target = os.path.abspath(os.path.join(destination, *name.split("/")))
        if os.path.commonpath([destination, target]) != destination:
            raise ValueError("مسار غير آمن داخل النسخة الاحتياطية")
        if is_dir:
            os.makedirs(target, exist_ok=True)
            continue
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with archive.open(info, "r") as source_file, open(target, "xb") as target_file:
            shutil.copyfileobj(source_file, target_file)
