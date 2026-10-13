"""Assemble the approved figures and this revision's three data figures."""
from pathlib import Path
import csv
import html
import json
import re

import fitz
from PIL import Image

ROOT = Path(__file__).resolve().parent
OLD = ROOT.parent / 'V3正文精修_20261013_R4'
CHANGED = {3: 'navigation', 4: 'observability', 8: 'aiding'}
TITLES = {3: '完整轨迹与分组空间细节', 4: '两种机器人运动估计与绝对方向',
          8: '不同退化条件下的质量调整与航向响应'}
rows = list(csv.DictReader((OLD / 'MAIN_FIGURE_CATALOG.csv').open(encoding='utf-8-sig')))
for row in rows:
    num = int(row['figure'])
    if num in CHANGED:
        folder = ROOT / CHANGED[num]
        candidates = sorted(p for p in (folder / 'preview').glob(f'F{num:02d}*.png')
                            if not p.stem.endswith(('_gray', '_grayscale')))
        assert len(candidates) == 1, (num, candidates)
        preview = candidates[0]
        stem = preview.stem
        pdfs = [p for p in folder.rglob(stem + '.pdf') if 'qa' not in p.parts]
        assert len(pdfs) == 1, (stem, pdfs)
        base = pdfs[0].with_suffix('')
        row.update(id=stem, title=TITLES[num], preview=preview.relative_to(ROOT).as_posix())
        for ext in ['pdf', 'svg', 'png']:
            row[ext] = base.with_suffix('.' + ext).relative_to(ROOT).as_posix()
    for key in ['preview', 'pdf', 'svg', 'png']:
        assert (ROOT / row[key]).is_file(), row[key]
    width, height = Image.open(ROOT / row['preview']).size
    row.update(width_px=width, height_px=height)
    assert width >= 1920 and height >= 1080
with (ROOT / 'MAIN_FIGURE_CATALOG.csv').open('w', newline='', encoding='utf-8-sig') as f:
    writer = csv.DictWriter(f, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)

reader_path = ROOT / 'FIGURE_READERS_ZH.md'
source = reader_path.read_text(encoding='utf-8')
for row in rows:
    if int(row['figure']) not in CHANGED:
        continue
    pattern = rf'(?ms)(^## 图{row["figure"]}[^\n]*\n)(.*?)(?=^## 图|\Z)'
    def add_figure(match):
        body = re.sub(r'!\[[^\]]*\]\([^\n]*\)\n*', '', match.group(2)).lstrip()
        return match.group(1) + f'\n![图{row["figure"]}]({row["preview"]})\n\n' + body
    source = re.sub(pattern, add_figure, source)
reader_path.write_text(source, encoding='utf-8')
sections = re.split(r'(?m)^## 图\d+[^\n]*\n', source)[1:]
assert len(sections) == 10
out = ['''<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>V3 正文图 R5</title><style>
*{box-sizing:border-box}body{margin:0;background:#f4f6f9;color:#17212b;font:16px/1.8 system-ui,"Microsoft YaHei",sans-serif}
header,main{max-width:1450px;margin:auto;padding:28px}h1{font-size:28px}h2{font-size:23px;margin-top:0}a{color:#174eaa}
nav{position:sticky;top:0;background:#fffffff5;z-index:2;padding:10px;display:flex;justify-content:center;gap:20px;flex-wrap:wrap;border-block:1px solid #dde2e8}
section{background:white;border:1px solid #dde2e8;padding:26px;margin-bottom:28px;scroll-margin-top:76px}
.figure{display:block;width:100%;height:auto;cursor:zoom-in;margin:20px 0}.links{display:flex;gap:20px;flex-wrap:wrap}small{color:#536274}
details{border-top:1px solid #dde2e8;padding-top:14px;margin-top:18px}summary{font-weight:650;cursor:pointer}.reader{white-space:pre-wrap}
dialog{border:0;padding:0;width:96vw;height:94vh;max-width:96vw;max-height:94vh}
#controls{padding:8px;background:white;border-bottom:1px solid #d5dce4;display:flex;gap:8px;align-items:center;flex-wrap:wrap}
button{cursor:pointer;padding:6px 12px;border:1px solid #ccd6e1;background:#fff;border-radius:4px;font:inherit;color:#174eaa}
#zoomview{height:calc(100% - 56px);overflow:auto;padding:12px;background:#f1f3f6}#zoomimg{max-width:none;display:block;background:white}
dialog::backdrop{background:#0f172acc}@media(max-width:700px){header,main{padding:14px 10px}section{padding:15px 10px}h1{font-size:24px}}
</style><header><h1>正文图 R5 · 轨迹细节、两种运动估计与多种退化</h1>
<p>本轮修改图3、4、8。其余正文图保持上一轮版本。点击图可按原始像素继续放大。</p>
<p><a href="正文图_R5修改三图.pdf">本轮三图PDF</a>　<a href="正文图_R5审阅册.pdf">全部正文十图PDF</a>　<a href="FIGURE_READERS_ZH.md">逐图解释</a>　<a href="schematics/F02_矢量放大查看.html">图2矢量阅读</a></p></header><nav>''']
out.extend(f'<a href="#f{row["figure"]}">图{row["figure"]}</a>' for row in rows)
out.append('</nav><main>')
for row, section in zip(rows, sections):
    section = re.sub(r'!\[[^\]]*\]\([^\n]*\)', '', section).strip()
    section = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', html.escape(section))
    out.append(f'<section id="f{row["figure"]}"><h2>图{row["figure"]}　{row["title"]}</h2><small>{row["width_px"]} × {row["height_px"]} px</small><img class="figure" loading="lazy" src="{row["preview"]}" data-full="{row["png"]}" alt="{row["title"]}"><div class="links"><a href="{row["png"]}">原尺寸PNG</a><a href="{row["pdf"]}">矢量PDF</a><a href="{row["svg"]}">可编辑SVG</a></div><details><summary>解释与修改理由</summary><div class="reader">{section}</div></details></section>')
out.append('''</main><dialog id="zoom"><div id="controls"><button id="close">关闭 ×</button><button id="fit">适合窗口</button><button id="plus">放大 ＋</button><button id="minus">缩小 −</button><button id="native">原始像素</button><span id="ratio"></span></div><div id="zoomview"><img id="zoomimg" alt="原图放大"></div></dialog><script>
const d=document.getElementById('zoom'),im=document.getElementById('zoomimg'),v=document.getElementById('zoomview');let scale=1;
function apply(){im.style.width=(im.naturalWidth*scale)+'px';im.style.height='auto';document.getElementById('ratio').textContent=Math.round(scale*100)+'%'}
function fit(){scale=Math.min(1,(v.clientWidth-24)/im.naturalWidth);apply();v.scrollLeft=v.scrollTop=0}
document.querySelectorAll('.figure').forEach(x=>x.onclick=()=>{im.onload=fit;im.src=x.dataset.full;d.showModal();if(im.complete&&im.naturalWidth)fit()});
document.getElementById('close').onclick=()=>d.close();document.getElementById('fit').onclick=fit;document.getElementById('native').onclick=()=>{scale=1;apply()};
document.getElementById('plus').onclick=()=>{scale=Math.min(3,scale*1.4);apply()};document.getElementById('minus').onclick=()=>{scale=Math.max(.05,scale/1.4);apply()};d.onclick=e=>{if(e.target===d)d.close()};
</script></html>''')
(ROOT / '正文图_R5高清图库.html').write_text('\n'.join(out), encoding='utf-8')
for filename, selected in [('正文图_R5审阅册.pdf', rows),
                           ('正文图_R5修改三图.pdf', [r for r in rows if int(r['figure']) in CHANGED])]:
    doc = fitz.open()
    for row in selected:
        with fitz.open(ROOT / row['pdf']) as source_doc:
            doc.insert_pdf(source_doc)
    doc.save(ROOT / filename, deflate=True)
(ROOT / 'SCREEN_EXPORTS.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf-8')
captions = ['# R5 修改三图的论文图注\n']
for num, folder in CHANGED.items():
    path = ROOT / folder / 'CAPTIONS_ZH_EN.md'
    assert path.is_file(), path
    captions.append(f'\n## 图{num}\n\n' + path.read_text(encoding='utf-8'))
(ROOT / 'CAPTIONS_REVISED_ZH_EN.md').write_text('\n'.join(captions), encoding='utf-8')
print({'figures': len(rows), 'changed': list(CHANGED)})
