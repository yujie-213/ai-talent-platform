"""真实 OCR/生成模型的合成格式样本评测，不使用测试替身。"""
import sys
import os
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
scan = BytesIO(); image.save(scan, format='PDF', save_all=True, append_images=[image])
jpeg = BytesIO(); image.save(jpeg, format='JPEG')
writer = PdfWriter(); writer.append(BytesIO(text_pdf())); writer.append(BytesIO(scan.getvalue()))
mixed = BytesIO(); writer.write(mixed)
docx = BytesIO()
from docx import Document
from docx.shared import Inches
document = Document()
document.add_paragraph('合成简历 李测试')
document.add_table(rows=1, cols=1).cell(0, 0).text = '教育 本科 计算机科学'
document.add_picture(str(root / 'synthetic-resume.png'), width=Inches(6))
document.save(docx)
full_docx=BytesIO()
full=Document()
for line in ['合成简历（仅用于测试）','姓名：王样本','电话：+1 202 555 0123','邮箱：resume-full@example.test','教育：2016年9月-2020年6月 合成大学 计算机科学 本科','经历：2020年7月-2024年6月 合成科技 Python工程师','项目：2023年1月-2024年1月 合成人才检索项目，使用Python、SQL','技能：Python、SQL、Docker','证书：2022年6月 合成云平台工程师证书（测试证书）']:
    full.add_paragraph(line)
full.save(full_docx)
project_docx=BytesIO()
project=Document()
for line in ['合成测试简历','姓名：陈样本','邮箱：project@example.test','项目：2021年3月-2022年5月 合成服务项目，使用Rust编写后端服务。']:
    project.add_paragraph(line)
project.save(project_docx)
samples = {'project-only.docx':project_docx.getvalue(), 'full-fields.docx':full_docx.getvalue(), 'text.pdf': text_pdf(), 'scan.pdf': scan.getvalue(), 'mixed.pdf': mixed.getvalue(),
           'synthetic.png': (root / 'synthetic-resume.png').read_bytes(), 'synthetic.jpeg': jpeg.getvalue(), 'table-image.docx': docx.getvalue()}
targets=set(sys.argv[1:])
report=json.loads((root / 'formats.json').read_text(encoding='utf-8')) if targets and (root / 'formats.json').exists() else []
for name, content in samples.items():
    if targets and name not in targets: continue
    report=[entry for entry in report if entry['sample'] != name]
    (root / name).write_bytes(content)
    try:
        segments = read_resume(name, content, paddle_ocr)
        validated = validate_extraction(extract_fields(segments), segments)
        report.append({'sample': name, 'segments': segments, 'validated': validated, 'model': os.getenv('RESUME_LLM_MODEL','')})
        print(name, 'read', len(segments), 'fields', len(validated['fields']), 'issues', len(validated['issues']), flush=True)
    except Exception as error:
        report.append({'sample': name, 'error_type': type(error).__name__, 'code': str(error) if type(error).__name__ == 'ResumeError' else 'FAILED'})
        print(name, 'FAILED', type(error).__name__, flush=True)
    (root / 'formats.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
