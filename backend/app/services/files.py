from io import BytesIO
from pathlib import Path
import zipfile
from PIL import Image
from pypdf import PdfReader
from app.core.config import FILE_ROOT, MAX_BYTES
from app.core.security import fail

def safe_path(relative: str) -> Path:
    path = (FILE_ROOT / relative).resolve()
    if not path.is_relative_to(FILE_ROOT) or path == FILE_ROOT:
        fail(404, 'NOT_FOUND', '文件不可用')
    return path

def validate_file(name: str, content: bytes) -> str:
    if len(content) > MAX_BYTES:
        fail(413, 'FILE_TOO_LARGE', '文件超过 10 MiB')
    suffix = Path(name).suffix.lower()
    try:
        if suffix == '.pdf':
            reader = PdfReader(BytesIO(content), strict=True)
            if reader.is_encrypted or not 1 <= len(reader.pages) <= 50:
                raise ValueError()
            return 'application/pdf'
        if suffix in ('.png', '.jpg', '.jpeg'):
            with Image.open(BytesIO(content)) as img:
                expected = 'PNG' if suffix == '.png' else 'JPEG'
                if img.format != expected or img.width * img.height > 25000000:
                    raise ValueError()
                img.verify()
            return 'image/png' if suffix == '.png' else 'image/jpeg'
        if suffix == '.docx':
            with zipfile.ZipFile(BytesIO(content)) as archive:
                entries = archive.infolist()
                if len(entries) > 1000 or sum(e.file_size for e in entries) > 50 * 1024 * 1024:
                    raise ValueError()
                if any(e.flag_bits & 1 or '..' in Path(e.filename).parts or e.filename.startswith('/') for e in entries):
                    raise ValueError()
                if not {'[Content_Types].xml', 'word/document.xml'}.issubset(archive.namelist()) or archive.testzip():
                    raise ValueError()
            return 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    except Exception:
        fail(422, 'INVALID_FILE', '文件损坏、加密、格式不符或超出可读取限制')
    fail(422, 'INVALID_FILE', '仅支持 PDF、PNG、JPEG、DOCX')
