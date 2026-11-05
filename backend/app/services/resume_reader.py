"""有界读取原始简历；不访问数据库，不执行文档中的外部关系。"""
from dataclasses import dataclass, asdict
from io import BytesIO
from pathlib import Path
from typing import Callable
import zipfile
from xml.etree import ElementTree as ET

from PIL import Image
from pypdf import PdfReader
from app.services.files import validate_file

MAX_TEXT = 120_000
MAX_SEGMENTS = 500
MAX_IMAGES = 100
NS = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
      'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
      'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}


class ResumeError(Exception):
    """只携带稳定错误码，避免供应商异常泄露正文/凭据。"""


@dataclass(frozen=True)
class Segment:
    id: str
    locator: str
    method: str
    text: str


def read_resume(name: str, content: bytes, ocr: Callable[[bytes], str]) -> list[dict]:
    validate_file(name, content)
    segments: list[Segment] = []
    image_count = 0

    def add(locator: str, method: str, text: str) -> None:
        text = text.strip()
        if not text:
            return
        if len(segments) >= MAX_SEGMENTS:
            raise ResumeError('DOCUMENT_SEGMENT_LIMIT')
        if sum(len(s.text) for s in segments) + len(text) > MAX_TEXT:
            raise ResumeError('DOCUMENT_TEXT_LIMIT')
        segments.append(Segment(str(len(segments) + 1), locator, method, text))

    def recognize(data: bytes) -> str:
        nonlocal image_count
        image_count += 1
        if image_count > MAX_IMAGES:
            raise ResumeError('DOCUMENT_IMAGE_LIMIT')
        with Image.open(BytesIO(data)) as img:
            if img.width * img.height > 25_000_000:
                raise ResumeError('IMAGE_PIXEL_LIMIT')
        return ocr(data)

    suffix = Path(name).suffix.lower()
    if suffix == '.pdf':
        reader = PdfReader(BytesIO(content))
        rendered = None
        try:
            for number, page in enumerate(reader.pages, 1):
                text = page.extract_text() or ''
                add(f'page:{number}', 'text', text)
                # 页内含图也识别，避免文字页上的扫描区域被忽略。
                if len(''.join(text.split())) < 30:
                    import pypdfium2 as pdfium
                    if rendered is None:
                        rendered = pdfium.PdfDocument(content)
                    render_page = rendered[number - 1]
                    try:
                        if render_page.get_width() * render_page.get_height() * 4 > 25_000_000:
                            raise ResumeError('IMAGE_PIXEL_LIMIT')
                        bitmap = render_page.render(scale=2)
                        try:
                            buf = BytesIO()
                            bitmap.to_pil().save(buf, format='PNG')
                            add(f'page:{number}', 'ocr', recognize(buf.getvalue()))
                        finally:
                            bitmap.close()
                    finally:
                        render_page.close()
                else:
                    for index, img in enumerate(page.images, 1):
                        add(f'page:{number}/image:{index}', 'ocr', recognize(img.data))
        finally:
            if rendered is not None:
                rendered.close()
    elif suffix == '.docx':
        with zipfile.ZipFile(BytesIO(content)) as archive:
            root = ET.fromstring(archive.read('word/document.xml'))
            rel_name = 'word/_rels/document.xml.rels'
            relationships = ET.fromstring(archive.read(rel_name)) if rel_name in archive.namelist() else []
            rels = {r.attrib['Id']: r.attrib['Target'] for r in relationships if r.attrib.get('TargetMode') != 'External'}
            body = root.find('w:body', NS)
            if body is None:
                raise ResumeError('INVALID_DOCX_BODY')
            for index, paragraph in enumerate(body.iter(f"{{{NS['w']}}}p"), 1):
                # 表格单元格里的段落同样在正文树中，定位号按原文顺序。
                add(f'paragraph:{index}', 'text', ''.join(t.text or '' for t in paragraph.findall('.//w:t', NS)))
                for image_index, blip in enumerate(paragraph.findall('.//a:blip', NS), 1):
                    target = rels.get(blip.attrib.get(f"{{{NS['r']}}}embed", ''))
                    if target is None:
                        raise ResumeError('UNSUPPORTED_EXTERNAL_IMAGE')
                    image_path = 'word/' + target.lstrip('/')
                    if '..' in Path(target).parts or image_path not in archive.namelist():
                        raise ResumeError('INVALID_DOCX_IMAGE')
                    add(f'paragraph:{index}/image:{image_index}', 'ocr', recognize(archive.read(image_path)))
    else:
        add('image:1', 'ocr', recognize(content))
    if not segments:
        raise ResumeError('NO_READABLE_TEXT')
    return [asdict(s) for s in segments]
