"""真实 OCR/生成模型的合成格式样本评测，不使用测试替身。"""
import sys
import json
from io import BytesIO
from pathlib import Path
import zipfile
sys.path.insert(0, str(Path('backend').resolve()))
from app.core import config
from app.services.resume_reader import read_resume
from app.services.resume_providers import paddle_ocr, extract_fields
from app.services.resume_validation import validate_extraction
from PIL import Image
from pypdf import PdfWriter
sys.path.insert(0, str(Path('.').resolve()))
from tests.test_resume_reading import text_pdf

root = Path('data/stage-two-evaluation')
image = Image.open(root / 'synthetic-resume.png').convert('RGB')
scan = BytesIO(); image.save(scan, format='PDF')
jpeg = BytesIO(); image.save(jpeg, format='JPEG')
writer = PdfWriter(); writer.append(BytesIO(text_pdf())); writer.append(BytesIO(scan.getvalue()))
mixed = BytesIO(); writer.write(mixed)
docx = BytesIO()
with zipfile.ZipFile(docx, 'w') as archive:
    archive.writestr('[Content_Types].xml', '<Types/>')
    archive.writestr('word/document.xml', '''<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><w:body><w:p><w:r><w:t>合成简历 李测试</w:t></w:r></w:p><w:tbl><w:tr><w:tc><w:p><w:r><w:t>教育 本科 计算机科学</w:t></w:r></w:p></w:tc></w:tr></w:tbl><w:p><w:r><w:drawing><a:blip r:embed="rId1"/></w:drawing></w:r></w:p></w:body></w:document>''')
    archive.writestr('word/_rels/document.xml.rels', '<Relationships><Relationship Id="rId1" Target="media/image1.png"/></Relationships>')
    archive.writestr('word/media/image1.png', (root / 'synthetic-resume.png').read_bytes())
samples = {'text.pdf': text_pdf(), 'scan.pdf': scan.getvalue(), 'mixed.pdf': mixed.getvalue(),
           'synthetic.png': (root / 'synthetic-resume.png').read_bytes(), 'synthetic.jpeg': jpeg.getvalue(), 'table-image.docx': docx.getvalue()}
report = []
for name, content in samples.items():
    (root / name).write_bytes(content)
    try:
        segments = read_resume(name, content, paddle_ocr)
        validated = validate_extraction(extract_fields(segments), segments)
        report.append({'sample': name, 'segments': segments, 'validated': validated})
        print(name, 'read', len(segments), 'fields', len(validated['fields']), 'issues', len(validated['issues']), flush=True)
    except Exception as error:
        report.append({'sample': name, 'error_type': type(error).__name__, 'code': str(error) if type(error).__name__ == 'ResumeError' else 'FAILED'})
        print(name, 'FAILED', type(error).__name__, flush=True)
    (root / 'formats.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
