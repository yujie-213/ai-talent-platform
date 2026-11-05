"""在隔离 OCR Python 中运行，标准输出最后一行为机器可读结果。"""
import json
import os
import sys
os.environ['PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK'] = 'True'
os.environ['PADDLE_PDX_MODEL_SOURCE'] = 'modelscope'
from paddleocr import PaddleOCR

engine = PaddleOCR(text_detection_model_name='PP-OCRv5_mobile_det',
                   text_recognition_model_name='PP-OCRv5_mobile_rec', device='cpu',
                   use_doc_orientation_classify=False, use_doc_unwarping=False,
                   use_textline_orientation=False)
texts = [text for result in engine.predict(sys.argv[1]) for text in result['rec_texts']]
print(json.dumps({'text': '\n'.join(texts)}, ensure_ascii=True))
