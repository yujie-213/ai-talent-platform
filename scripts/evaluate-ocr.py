"""隔离 OCR 环境执行；仅合成样本，结果写入被忽略的 data。"""
import json
import os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

os.environ['PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK'] = 'True'
root = Path('data/stage-two-evaluation')
root.mkdir(parents=True, exist_ok=True)
expected = ['合成简历 李测试', '邮箱 synthetic@example.test', '技能 Python SQL', '教育 本科 计算机科学']
image = Image.new('RGB', (1600, 650), 'white')
draw = ImageDraw.Draw(image)
font = ImageFont.truetype('C:/Windows/Fonts/msyh.ttc', 45)
for i, line in enumerate(expected):
    draw.text((60, 70 + i * 125), line, fill='black', font=font)
path = root / 'synthetic-resume.png'
image.save(path)
from paddleocr import PaddleOCR
engine = PaddleOCR(text_detection_model_name='PP-OCRv5_mobile_det', text_recognition_model_name='PP-OCRv5_mobile_rec', device='cpu', use_doc_orientation_classify=False, use_doc_unwarping=False,
                   use_textline_orientation=False)
texts = [text for result in engine.predict(str(path)) for text in result['rec_texts']]
result = {'sample': 'synthetic-resume.png', 'expected': expected, 'actual': texts,
          'exact_lines': [line in texts for line in expected], 'device': 'cpu'}
(root / 'ocr.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(result, ensure_ascii=False))
