from pathlib import Path
import csv,json,re,html,shutil
from PIL import Image
import fitz
ROOT=Path(__file__).resolve().parent
OLD=ROOT.parent/'V3正文精修_20261012_R3'
for stem in ['S11_GINav_partial_trajectories','S11_native_relative_trajectories']:
    for ext in ['pdf','png']:
        shutil.copyfile(OLD/'navigation'/f'{stem}.{ext}',ROOT/'navigation'/f'{stem}.{ext}')
    shutil.copyfile(OLD/'navigation/preview'/f'{stem}.png',ROOT/'navigation/preview'/f'{stem}.png')
navread=ROOT/'navigation/README.md'
txt=navread.read_text(encoding='utf-8')
txt=txt.replace('../../V3正文精修_20261012_R3/navigation/preview/','preview/')
txt=txt.replace('原局部199.945–209.945s几乎没有运动。','原局部199.945–209.945s的参考轨迹近静止。')
if 'OBSTRUCTION_SDK_CORROBORATION.md' not in txt:
    txt+='\n补充核对：[SDK速度低速旁证](OBSTRUCTION_SDK_CORROBORATION.md)。参考轨迹近静止与原机载SDK低速读数一致；两者不升级为独立真值或严格停止的证明。\n'
navread.write_text(txt,encoding='utf-8')
spec=[(1,'schematics','figures','F01_platform','保留：平台与短基线'),(2,'schematics','figures','F02_method','原样式高清与矢量阅读'),(3,'navigation','','F03_integrated_routes_and_heading','完整路线、局部与航向合图'),(4,'observability','','F04_absolute_direction_relative_motion','保留：同一算法七个朝向设置'),(5,'heading_acceptance','','F05_heading_error_comparison','保留：方向比较'),(6,'aiding','figures','F06_heading_and_tilt','保留：自然场景姿态'),(7,'aiding','figures','F07_heading_retained_translation','保留：条件性辅助'),(8,'aiding','figures','F08_heading_quality_scaling','质量变化下的处理过程'),(9,'navigation_comparison','','F09_heading_comparison','保留：航向横向比较'),(10,'aiding','figures','F10_heading_sensitivity','保留：方向扰动输入与输出')]
rows=[]
for n,folder,sub,stem,title in spec:
    base=Path(folder)/sub
    p=Path(folder)/'preview'/f'{stem}.png'
    w,h=Image.open(ROOT/p).size
    assert w>=1920 and h>=1080
    r=dict(figure=n,id=stem,title=title,preview=p.as_posix(),pdf=(base/f'{stem}.pdf').as_posix(),svg=(base/f'{stem}.svg').as_posix(),png=(base/f'{stem}.png').as_posix(),width_px=w,height_px=h)
    for k in ['pdf','svg','png']:assert (ROOT/r[k]).is_file()
    rows.append(r)
with (ROOT/'MAIN_FIGURE_CATALOG.csv').open('w',newline='',encoding='utf-8-sig') as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
read=(ROOT/'FIGURE_READERS_ZH.md').read_text(encoding='utf-8')
sections=re.split(r'(?m)^## 图\d+[^\n]*\n',read)[1:]
def rich(s):
    s=html.escape(s)
    return re.sub(r'\*\*(.*?)\*\*',r'<strong>\1</strong>',s)
out=['''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>V3 正文图 R4</title><style>*{box-sizing:border-box}body{margin:0;background:#f4f6f9;color:#17212b;font:16px/1.85 system-ui,"Microsoft YaHei",sans-serif}header,main{max-width:1280px;margin:auto;padding:28px}h1{font-size:28px;margin:0 0 12px}h2{font-size:23px;margin-top:0}a{color:#2563eb;text-decoration:none}nav{position:sticky;top:0;background:#fffffff5;z-index:2;padding:10px;display:flex;justify-content:center;gap:16px;flex-wrap:wrap;border-block:1px solid #e1e6ec}section{background:white;border:1px solid #e1e6ec;padding:26px;margin-bottom:28px;scroll-margin-top:72px}.figure{display:block;width:100%;height:auto;cursor:zoom-in;margin:20px 0}.links{display:flex;gap:20px;flex-wrap:wrap;font-size:14px}small{color:#596876}details{border-top:1px solid #e1e6ec;padding-top:14px;margin-top:18px}summary{font-weight:650;cursor:pointer}.reader{white-space:pre-wrap}dialog{border:0;padding:0;width:96vw;height:94vh;max-width:96vw;max-height:94vh}#controls{padding:8px;background:white;border-bottom:1px solid #d5dce4;display:flex;gap:8px;align-items:center}button{cursor:pointer;padding:6px 12px;border:1px solid #ccd6e1;background:#fff;border-radius:4px;font:inherit;color:#215db0}#zoomview{height:calc(100% - 52px);overflow:auto;padding:12px;background:#f1f3f6}#zoomimg{max-width:none;display:block;background:white}dialog::backdrop{background:#0f172acc}@media(max-width:700px){header,main{padding:14px 10px}section{padding:15px 10px}h1{font-size:24px}}</style><header><h1>正文图 R4 · 保留通过项，合并路线与质量证据</h1><p>图3已融合原图11。图4七条曲线的来源已核实。图8以一条真实处理过程解释条件性收益。</p><p><a href="schematics/F02_矢量放大查看.html">图2矢量放大查看</a>　<a href="schematics/figures/F02_method_8K.png">图2 7680px原图</a>　<a href="schematics/figures/F02_method_reading.pdf">图2放大阅读PDF</a>　<a href="正文图_R4审阅册.pdf">正文十图PDF</a></p><small>点击任何图后可继续放大或显示原始像素，放大窗口不再强制缩至屏宽。</small></header><nav>''']
out += [f'<a href="#f{r["figure"]}">图{r["figure"]}</a>' for r in rows]
out += ['</nav><main>']
for r,section in zip(rows,sections):
    section=re.sub(r'!\[[^\]]*\]\([^\n]*\)','',section).strip()
    out.append(f'<section id="f{r["figure"]}"><h2>图{r["figure"]}　{r["title"]}</h2><small>{r["width_px"]} × {r["height_px"]} px</small><img class="figure" loading="lazy" src="{r["preview"]}" data-full="{r["png"]}" alt="{r["title"]}"><div class="links"><a href="{r["png"]}">原尺寸PNG</a><a href="{r["pdf"]}">PDF</a><a href="{r["svg"]}">SVG（本地）</a></div><details><summary>本轮解释和决定</summary><div class="reader">{rich(section)}</div></details></section>')
out+=['''</main><dialog id="zoom"><div id="controls"><button id="close">关闭 ×</button><button id="fit">适合窗口</button><button id="plus">放大 ＋</button><button id="minus">缩小 −</button><button id="native">原始像素</button><span id="ratio"></span></div><div id="zoomview"><img id="zoomimg" alt="原图放大"></div></dialog><script>
const d=document.getElementById('zoom'),im=document.getElementById('zoomimg'),v=document.getElementById('zoomview');let scale=1;
function apply(){im.style.width=(im.naturalWidth*scale)+'px';im.style.height='auto';document.getElementById('ratio').textContent=Math.round(scale*100)+'%'}
function fit(){scale=Math.min(1,(v.clientWidth-24)/im.naturalWidth);apply();v.scrollLeft=v.scrollTop=0}
document.querySelectorAll('.figure').forEach(x=>x.onclick=()=>{im.onload=fit;im.src=x.dataset.full;d.showModal();if(im.complete&&im.naturalWidth)fit()});
document.getElementById('close').onclick=()=>d.close();document.getElementById('fit').onclick=fit;document.getElementById('native').onclick=()=>{scale=1;apply()};document.getElementById('plus').onclick=()=>{scale=Math.min(3,scale*1.4);apply()};document.getElementById('minus').onclick=()=>{scale=Math.max(.05,scale/1.4);apply()};d.onclick=e=>{if(e.target===d)d.close()};
</script></html>''']
(ROOT/'正文图_R4高清图库.html').write_text('\n'.join(out),encoding='utf-8')
doc=fitz.open()
for r in rows:
    with fitz.open(ROOT/r['pdf']) as src:doc.insert_pdf(src)
doc.save(ROOT/'正文图_R4审阅册.pdf',deflate=True)
(ROOT/'SCREEN_EXPORTS.json').write_text(json.dumps({'main_figures':10,'independent_F11_removed_from_main':True,'all_previews_full_hd_or_higher':True,'figures':rows},ensure_ascii=False,indent=2),encoding='utf-8')
print([(r['figure'],r['width_px'],r['height_px']) for r in rows])
