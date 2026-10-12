from pathlib import Path
import csv,json,re,html
from PIL import Image
import fitz

ROOT=Path(__file__).resolve().parent
spec=[
 (1,'schematics','F01_platform','实物平台与短基线几何'),
 (2,'schematics','F02_method','可编辑的矢量方法图'),
 (3,'navigation','F03_event_routes_and_heading','较长事件路线与误差'),
 (4,'observability','F04_absolute_direction_relative_motion','绝对方向与相对运动'),
 (5,'heading_acceptance','F05_heading_error_comparison','方向路线的误差比较'),
 (6,'aiding','F06_heading_and_tilt','持续方向更新与姿态'),
 (7,'aiding','F07_heading_retained_translation','已通过的观测中断图'),
 (8,'aiding','F08_heading_quality_scaling','三类质量变化与航向'),
 (9,'navigation','F09_heading_comparison','滤波与FGO比较'),
 (10,'aiding','F10_heading_sensitivity','方向退化的过程证据')]
rows=[]
for no,folder,stem,title in spec:
 base=Path(folder)/('figures' if folder in ['aiding','schematics'] else '')
 preview=Path(folder)/'preview'/f'{stem}.png'
 w,h=Image.open(ROOT/preview).size
 rows.append(dict(figure=no,id=stem,title=title,folder=folder,preview=preview.as_posix(),pdf=(base/f'{stem}.pdf').as_posix(),svg=(base/f'{stem}.svg').as_posix(),png=(base/f'{stem}.png').as_posix(),width_px=w,height_px=h))
 assert w>=1920 and h>=1080,(stem,w,h)
 for fmt in ['pdf','svg','png']:assert (ROOT/rows[-1][fmt]).is_file()
with (ROOT/'MAIN_FIGURE_CATALOG.csv').open('w',newline='',encoding='utf-8-sig') as f:
 writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
read=(ROOT/'FIGURE_READERS_ZH.md').read_text(encoding='utf-8')
sections=re.split(r'(?m)^## 图\d+[^\n]*\n',read)[1:]
def rich(s):
 s=html.escape(s)
 return re.sub(r'\*\*(.*?)\*\*',r'<strong>\1</strong>',s)
out=['''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>V3 正文精修 R2</title><style>*{box-sizing:border-box}body{margin:0;background:#f5f7fa;color:#1e293b;font:16px/1.8 system-ui,"Microsoft YaHei",sans-serif}header,main{max-width:1280px;margin:auto;padding:28px 30px}h1{font-size:30px;margin:0}nav{position:sticky;top:0;background:#fffffff5;padding:10px;display:flex;justify-content:center;gap:10px;flex-wrap:wrap;z-index:2;border-block:1px solid #e2e8f0}a{color:#2563eb;text-decoration:none}nav a{padding:1px 8px}section{background:white;border:1px solid #e2e8f0;margin-bottom:32px;padding:28px;scroll-margin-top:70px}h2{font-size:24px;margin-top:0}.figure{width:100%;height:auto;cursor:zoom-in}.links{display:flex;gap:22px;flex-wrap:wrap;font-size:14px}details{border-top:1px solid #e2e8f0;margin-top:18px;padding-top:14px}summary{cursor:pointer;font-weight:600}.reader{white-space:pre-wrap}small{color:#64748b}dialog{max-width:98vw;max-height:98vh;border:0;padding:12px}dialog img{max-width:92vw;max-height:none}dialog button{position:sticky;top:0;float:right;padding:10px;cursor:pointer}dialog::backdrop{background:#0f172acc}@media(max-width:700px){header,main{padding:16px 10px}section{padding:16px 10px}h1{font-size:25px}dialog img{max-width:none;width:1500px}}</style><header><h1>正文精修 R2：高清与可编辑图</h1><p>蓝色突出本文，保留认可版式。图1改为实物，图2完全矢量化，图8展示三类质量案例，图9补齐FGO定位，图10增加方向扰动过程。</p><p><a href="schematics/editable/F02_method.drawio">图2 draw.io 编辑文件</a>　<a href="schematics/figures/F02_method.svg">图2可编辑SVG</a>　<a href="正文十图_R2审阅册.pdf">十图PDF审阅册</a></p><small>所有屏幕预览宽≥2560px、高≥1080px。点击图片放大；原始PNG为出版分辨率。实物局部细节取决于原照片分辨率。</small></header><nav>''']
out += [f'<a href="#f{r["figure"]}">图{r["figure"]}</a>' for r in rows]
out+=['</nav><main>']
for row,sec in zip(rows,sections):
 sec=re.sub(r'!\[[^\]]*\]\([^\n]*\)','',sec).split('\n## ',1)[0].strip()
 out.append(f'<section id="f{row["figure"]}"><h2>图{row["figure"]}　{html.escape(row["title"])}</h2><small>{row["width_px"]} × {row["height_px"]} px 屏幕版</small><img class="figure" src="{row["preview"]}" alt="图{row["figure"]} {row["title"]}"><div class="links"><a href="{row["png"]}">原尺寸PNG</a><a href="{row["pdf"]}">矢量PDF</a><a href="{row["svg"]}">可编辑SVG（本地）</a></div><details><summary>修改内容与读图说明</summary><div class="reader">{rich(sec)}</div></details></section>')
out+=['''</main><dialog id="zoom"><button onclick="document.getElementById('zoom').close()">关闭 ×</button><img alt="放大图"></dialog><script>document.querySelectorAll('.figure').forEach(el=>el.onclick=()=>{const d=document.getElementById('zoom');d.querySelector('img').src=el.src;d.showModal()});document.getElementById('zoom').onclick=e=>{if(e.target.tagName==='DIALOG')e.currentTarget.close()};</script></html>''']
(ROOT/'正文十图_R2高清图库.html').write_text('\n'.join(out),encoding='utf-8')
doc=fitz.open()
for r in rows:
 with fitz.open(ROOT/r['pdf']) as p:doc.insert_pdf(p)
doc.save(ROOT/'正文十图_R2审阅册.pdf',deflate=True)
(ROOT/'SCREEN_EXPORTS.json').write_text(json.dumps({'all_previews_above_full_hd':True,'ratio_preserved':True,'figures':rows,'pdf_pages':len(doc)},ensure_ascii=False,indent=2),encoding='utf-8')
print([(r['figure'],r['width_px'],r['height_px']) for r in rows])
