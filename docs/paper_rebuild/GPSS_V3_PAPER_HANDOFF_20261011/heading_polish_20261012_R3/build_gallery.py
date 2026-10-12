from pathlib import Path
import csv,json,re,html
from PIL import Image
import fitz
ROOT=Path(__file__).resolve().parent
spec=[(1,'schematics','figures','F01_platform','平台照片与恢复插图'),(2,'schematics','figures','F02_method','原构图可编辑描摹'),(3,'navigation','','F03_100s_routes_with_spatial_detail','100秒路线与空间放大'),(4,'observability','','F04_absolute_direction_relative_motion','已批准：方向与相对路径'),(5,'heading_acceptance','','F05_heading_error_comparison','方向比较与筛选分布'),(6,'aiding','figures','F06_heading_and_tilt','已批准：持续航向与倾角'),(7,'aiding','figures','F07_heading_retained_translation','已批准：中断与条件性辅助'),(8,'aiding','figures','F08_heading_quality_scaling','六面板质量案例暂定稿'),(9,'navigation_comparison','','F09_heading_comparison','航向比较与18种中断条件'),(10,'aiding','figures','F10_heading_sensitivity','方向扰动输入与融合输出'),(11,'navigation','','F11_full_trajectory_comparison','新增：完整评价窗轨迹')]
rows=[]
for n,folder,sub,stem,title in spec:
 base=Path(folder)/sub
 p=Path(folder)/'preview'/f'{stem}.png'
 w,h=Image.open(ROOT/p).size
 assert w>=1920 and h>=1080,(n,w,h)
 r=dict(figure=n,id=stem,title=title,preview=p.as_posix(),pdf=(base/f'{stem}.pdf').as_posix(),svg=(base/f'{stem}.svg').as_posix(),png=(base/f'{stem}.png').as_posix(),width_px=w,height_px=h)
 for fmt in ['pdf','svg','png']:assert (ROOT/r[fmt]).is_file()
 rows.append(r)
with (ROOT/'MAIN_FIGURE_CATALOG.csv').open('w',newline='',encoding='utf-8-sig') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
text=(ROOT/'FIGURE_READERS_ZH.md').read_text(encoding='utf-8')
sections=re.split(r'(?m)^## 图\d+[^\n]*\n',text)[1:]
def rich(x):
 x=html.escape(x)
 return re.sub(r'\*\*(.*?)\*\*',r'<strong>\1</strong>',x)
out=['''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>V3 正文图R3</title><style>*{box-sizing:border-box}body{margin:0;background:#f4f6f9;color:#17212b;font:16px/1.85 system-ui,"Microsoft YaHei",sans-serif}header,main{max-width:1280px;margin:auto;padding:30px}h1{font-size:30px;margin:0 0 14px}h2{font-size:23px;margin-top:0}a{color:#2563eb;text-decoration:none}nav{position:sticky;top:0;background:#fffffff5;z-index:2;padding:10px;display:flex;justify-content:center;gap:13px;flex-wrap:wrap;border-block:1px solid #e1e6ec}section{background:white;border:1px solid #e1e6ec;padding:28px;margin-bottom:30px;scroll-margin-top:75px}.figure{display:block;width:100%;cursor:zoom-in;margin:20px 0}.links{display:flex;gap:20px;flex-wrap:wrap;font-size:14px}small{color:#596876}details{border-top:1px solid #e1e6ec;padding-top:14px;margin-top:18px}summary{font-weight:650;cursor:pointer}.reader{white-space:pre-wrap}dialog{border:0;padding:12px;max-width:98vw;max-height:96vh}dialog img{max-width:92vw}dialog button{position:sticky;top:0;float:right;padding:10px;cursor:pointer}dialog::backdrop{background:#0f172acc}@media(max-width:700px){header,main{padding:15px 10px}section{padding:15px 10px}h1{font-size:24px}dialog img{max-width:none;width:1500px}}</style><header><h1>正文图 R3：完整轨迹与清楚的读法</h1><p>新增完整轨迹组，图2按作者原图描摹，图3采用100秒及真实空间放大。图4、6、7、10保留。点击图片放大，展开下方读法。</p><p><a href="schematics/editable/F02_method_traced.svg">图2主编辑SVG</a>　<a href="正文图_R3审阅册.pdf">全部正文图PDF</a>　<a href="aiding/READ_F04_F07_F10_R3.md">图4(b)、图7、图10详细解释</a></p></header><nav>''']
out += [f'<a href="#f{r["figure"]}">图{r["figure"]}</a>' for r in rows]
out += ['<a href="#more">完整轨迹补充</a></nav><main>']
for r,sec in zip(rows,sections):
 sec=re.sub(r'!\[[^\]]*\]\([^\n]*\)','',sec).strip()
 out.append(f'<section id="f{r["figure"]}"><h2>图{r["figure"]}　{r["title"]}</h2><small>{r["width_px"]} × {r["height_px"]} px</small><img class="figure" src="{r["preview"]}" alt="{r["title"]}"><div class="links"><a href="{r["png"]}">原尺寸PNG</a><a href="{r["pdf"]}">PDF</a><a href="{r["svg"]}">SVG（本地）</a></div><details><summary>含义、修改与读图说明</summary><div class="reader">{rich(sec)}</div></details></section>')
out.append('<section id="more"><h2>完整轨迹的其他已有输出</h2><p>原生局部坐标与部分输出分别展示，避免把它们当成与地理参考相同的完整轨迹。</p>')
for p in sorted((ROOT/'navigation/preview').glob('S11_*.png')):
 if '_gray' in p.name:continue
 out.append(f'<img class="figure" src="{p.relative_to(ROOT).as_posix()}" alt="已有轨迹补充"><p><a href="navigation/{p.stem}.pdf">打开该图PDF</a></p>')
out.append('''</section></main><dialog id="zoom"><button onclick="document.getElementById('zoom').close()">关闭 ×</button><img alt="放大图"></dialog><script>document.querySelectorAll('.figure').forEach(x=>x.onclick=()=>{let d=document.getElementById('zoom');d.querySelector('img').src=x.src;d.showModal()});document.getElementById('zoom').onclick=e=>{if(e.target.tagName==='DIALOG')e.currentTarget.close()};</script></html>''')
(ROOT/'正文图_R3高清图库.html').write_text('\n'.join(out),encoding='utf-8')
doc=fitz.open()
for r in rows:
 with fitz.open(ROOT/r['pdf']) as src:doc.insert_pdf(src)
doc.save(ROOT/'正文图_R3审阅册.pdf',deflate=True)
(ROOT/'SCREEN_EXPORTS.json').write_text(json.dumps({'main_figures':len(rows),'all_full_hd_or_higher':True,'ratio_preserved':True,'figures':rows},ensure_ascii=False,indent=2),encoding='utf-8')
print([(r['figure'],r['width_px'],r['height_px']) for r in rows])
