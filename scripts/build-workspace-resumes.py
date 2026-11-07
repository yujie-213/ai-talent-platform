"""用捆绑PDF运行时生成用户指定的虚构履历原文件，不写入业务库。"""
import json
from pathlib import Path
import subprocess
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from PIL import Image, ImageDraw
from workspace_data import people

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data/workspace/resumes'


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    pdfmetrics.registerFont(UnicodeCIDFont('STSong-Light'))
    styles={
        'name':ParagraphStyle('name',fontName='STSong-Light',fontSize=25,leading=34,textColor=colors.HexColor('#172B35'),spaceAfter=7),
        'heading':ParagraphStyle('heading',fontName='STSong-Light',fontSize=12,leading=20,spaceBefore=14,spaceAfter=5,textColor=colors.HexColor('#176657')),
        'body':ParagraphStyle('body',fontName='STSong-Light',fontSize=10.5,leading=18,spaceAfter=6,wordWrap='CJK'),
        'muted':ParagraphStyle('muted',fontName='STSong-Light',fontSize=10,leading=17,textColor=colors.HexColor('#536570'),spaceAfter=5),
    }
    report=[]
    for person in (p for p in people() if p['source']):
        path=OUT/(person['name']+'_'+person['title']+'_简历.pdf')
        content=[Paragraph(escape(person['name']),styles['name']),
            Paragraph(escape(person['title']+'  |  '+str(person['years'])+'年工作经验  |  '+person['degree']),styles['muted']),
            Paragraph(escape('手机 '+person['phone']+'    邮箱 '+person['email']),styles['body']),
            Paragraph(escape('意向城市 杭州或上海    '+person['availability']+'    期望薪资 '+person['expected_salary']),styles['muted'])]
        labels={'education':'教育经历','experience':'工作经历','project':'项目经历','skill':'专业技能','certificate':'证书与语言'}
        for category,label in labels.items():
            facts=[f['content'] for f in person['facts'] if f['category']==category]
            if facts:
                content.append(Paragraph(label,styles['heading']))
                content.extend(Paragraph(escape(fact),styles['body']) for fact in facts)
        document=SimpleDocTemplate(str(path),pagesize=A4,rightMargin=48,leftMargin=48,topMargin=40,bottomMargin=40,
            title=person['name']+' 个人简历',author=person['name'])
        def footer(canvas,doc):
            canvas.setFont('STSong-Light',9);canvas.setFillColor(colors.HexColor('#7A8790'))
            canvas.drawRightString(A4[0]-48,25,str(doc.page))
        document.build(content,onFirstPage=footer,onLaterPages=footer)
        prefix=OUT/(person['name']+'_预览')
        subprocess.run(['pdftoppm','-scale-to','1100','-png',str(path),str(prefix)],check=True,capture_output=True)
        pages=sorted(OUT.glob(prefix.name+'-*.png'))
        assert pages
        report.append({'name':person['name'],'file':path.name,'pages':len(pages),'previews':[p.name for p in pages]})
    images=[]
    for item in report:
        for page in item['previews']:
            picture=Image.open(OUT/page).convert('RGB');picture.thumbnail((360,510))
            tile=Image.new('RGB',(390,550),'#e9edef');tile.paste(picture,((390-picture.width)//2,22))
            images.append(tile)
    collage=Image.new('RGB',(390*4,550*((len(images)+3)//4)),'white')
    for i,picture in enumerate(images):collage.paste(picture,((i%4)*390,(i//4)*550))
    collage.save(OUT/'简历总览.png')
    (OUT/'manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Resume PDFs generated:',len(report),'pages:',sum(r['pages'] for r in report))


if __name__=='__main__':main()
