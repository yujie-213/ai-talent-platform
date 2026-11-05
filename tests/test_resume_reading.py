"""合成输入；OCR 替身仅验证分流，真实 OCR 另行评测。"""
from io import BytesIO
import zipfile
import pytest
from PIL import Image, ImageDraw
from pypdf import PdfWriter
from app.services.resume_reader import read_resume, ResumeError
from app.services.resume_validation import validate_extraction
from app.services.resume_providers import extract_fields


def image_bytes(format='PNG'):
    image = Image.new('RGB', (800, 300), 'white')
    ImageDraw.Draw(image).text((30, 30), 'SYNTHETIC RESUME Python Engineer', fill='black')
    out = BytesIO()
    image.save(out, format=format)
    return out.getvalue()


def text_pdf():
    from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject
    writer = PdfWriter()
    page = writer.add_blank_page(600, 800)
    font = DictionaryObject({NameObject('/Type'): NameObject('/Font'), NameObject('/Subtype'): NameObject('/Type1'), NameObject('/BaseFont'): NameObject('/Helvetica')})
    page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'): DictionaryObject({NameObject('/F1'): writer._add_object(font)})})
    stream = DecodedStreamObject()
    stream.set_data(b'BT /F1 12 Tf 40 700 Td (Synthetic Resume Python Engineer synthetic@example.test) Tj ET')
    page[NameObject('/Contents')] = writer._add_object(stream)
    out = BytesIO()
    writer.write(out)
    return out.getvalue()


def test_pdf_text_scan_mixed():
    calls = []
    def ocr(data):
        calls.append(data)
        return 'SYNTHETIC SCAN'
    assert read_resume('text.pdf', text_pdf(), ocr)[0]['method'] == 'text'
    assert not calls
    img = Image.open(BytesIO(image_bytes()))
    scan = BytesIO()
    img.save(scan, format='PDF')
    writer = PdfWriter()
    writer.append(BytesIO(text_pdf()))
    writer.append(BytesIO(scan.getvalue()))
    writer.append(BytesIO(scan.getvalue()))
    out = BytesIO()
    writer.write(out)
    result = read_resume('mixed.pdf', out.getvalue(), ocr)
    assert [s['locator'] for s in result] == ['page:1', 'page:2', 'page:3']
    assert [s['method'] for s in result] == ['text', 'ocr', 'ocr']
    assert len(calls) == 2
    for data in calls:
        assert Image.open(BytesIO(data)).width > 0


@pytest.mark.parametrize('suffix,fmt', [('png', 'PNG'), ('jpg', 'JPEG'), ('jpeg', 'JPEG')])
def test_image_path(suffix, fmt):
    result = read_resume('sample.' + suffix, image_bytes(fmt), lambda _: 'synthetic Python')
    assert result[0]['locator'] == 'image:1'


def test_docx_paragraph_table_image():
    # 不依赖 Word，合成一个规范 ZIP/XML；实际走相同读取路径。
    document = '''<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
    xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><w:body>
    <w:p><w:r><w:t>Synthetic name</w:t></w:r></w:p>
    <w:tbl><w:tr><w:tc><w:p><w:r><w:t>Python table skill</w:t></w:r></w:p></w:tc></w:tr></w:tbl>
    <w:p><w:r><w:drawing><a:blip r:embed="rId1"/></w:drawing></w:r></w:p>
    </w:body></w:document>'''
    out = BytesIO()
    with zipfile.ZipFile(out, 'w') as archive:
        archive.writestr('[Content_Types].xml', '<Types/>')
        archive.writestr('word/document.xml', document)
        archive.writestr('word/_rels/document.xml.rels', '<Relationships><Relationship Id="rId1" Target="media/image1.png"/></Relationships>')
        archive.writestr('word/media/image1.png', image_bytes())
    result = read_resume('resume.docx', out.getvalue(), lambda _: 'certificate image')
    assert [s['text'] for s in result] == ['Synthetic name', 'Python table skill', 'certificate image']
    assert result[-1]['locator'] == 'paragraph:3/image:1'


def test_evidence_validation_and_no_invention():
    segments = [{'id': '1', 'text': 'Python bad@email 2024年1月-2020年2月', 'locator': 'page:1'}]
    def field(category, value, quote=None):
        return {'category': category, 'value': value, 'quote': quote or value, 'segment_id': '1'}
    result = validate_extraction({'fields': [field('skill', 'Python'), field('skill', 'Python'),
              field('name', 'invented'), field('email', 'bad@email'),
              field('experience', '2024年1月-2020年2月')]}, segments)
    assert len(result['fields']) == 1
    assert {i['code'] for i in result['issues']} == {'EVIDENCE_MISMATCH', 'INVALID_EMAIL', 'REVERSED_DATE_RANGE'}
    assert result['quality'] == 'needs_review'
    assert 'name' in result['missing']
    with pytest.raises(ResumeError, match='SCHEMA'):
        validate_extraction({'fields': [], 'unexpected': True}, segments)


def test_missing_model_explicit(monkeypatch):
    for key in ['RESUME_LLM_BASE_URL', 'RESUME_LLM_MODEL', 'RESUME_LLM_API_KEY']:
        monkeypatch.delenv(key, raising=False)
    with pytest.raises(ResumeError, match='LLM_NOT_CONFIGURED'):
        extract_fields([])
