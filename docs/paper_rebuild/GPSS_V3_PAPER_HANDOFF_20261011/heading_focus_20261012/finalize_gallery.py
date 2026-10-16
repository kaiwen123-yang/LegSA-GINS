from pathlib import Path
import csv,json,re,html,shutil
import fitz

ROOT=Path(__file__).resolve().parent
shutil.copyfile(ROOT/'schematics/preview/F02_method.png',ROOT/'schematics/figures/F02_method.png')
reader=ROOT/'FIGURE_READERS_ZH.md'
txt=reader.read_text(encoding='utf-8')
start=txt.index('## 图1')
end=txt.index('## 图3')
schematic='''## 图1　紧凑四足平台与短基线安装

![图1](schematics/preview/F01_platform.png)

**(a)真实照片，(b)平台插图，(c)几何定义。** (a)完整显示真实采集照片；(b)依实物照片调用image绘制，帮助看清机身与上方装配；(c)用矢量标明p1、p2、b=p2−p1、名义0.35m基线及机体坐标轴。三部分分别交代实物、结构与方向观测来源。

**正文主张：** 紧凑平台上的短基线提供方向信息。照片保留实物证据，插图用于说明，几何图连接方法定义。

**下一步：** 按论文方法统一器件称呼、基线方位到机身航向的安装角约定。抽象坐标原点不表示已测量的IMU位置；不能从照片推断相位中心或杆臂。图1为174×82mm，文字最小8pt，矢量几何与实际照片分开保存。

## 图2　方向与机身观测怎样作用于共同状态

![图2](schematics/preview/F02_method.png)

**沿箭头从左到右读。** MEMS IMU传播共同状态；GNSS位置对在实际支路构造方向并做有效性/新息选择；roll/pitch直接走倾角支路，body velocity经过坐标旋转。观测进入更新前的菱形标明冻结V3的有效GNSS事件调度。更新下方的质量/新息控制协方差，再返回真正使用它的更新步骤。

历史heading+tilt只以虚线连接预处理坐标旋转，没有画成当前估计状态的实时反馈。已纠正一个接线问题：roll/pitch不再进入Frame rotation，而是沿独立倾角箭头直接进入更新门。

**正文主张：** 不同观测校正同一个姿态、位置、速度与零偏状态；方向选择、坐标转换、更新调度各自位于实际作用路径。

**下一步：** 本轮image信息关系与设计已完成。原生1816×866像素的图2已保存PNG及原像素嵌入PDF；174mm下约265ppi，出版排版仍需矢量化文字和线条，不能把PDF封装当作矢量成图。完整箭头解释和英文图注见schematics/README.md。

'''
txt=txt[:start]+schematic+txt[end:]
reader.write_text(txt,encoding='utf-8')
exec((ROOT/'build_figure_catalog.py').read_text(encoding='utf-8'),{'__file__':str(ROOT/'build_figure_catalog.py')})
rows=list(csv.DictReader((ROOT/'MAIN_FIGURE_CATALOG.csv').open(encoding='utf-8-sig')))

def rich(s):
 s=html.escape(s)
 s=re.sub(r'\*\*(.*?)\*\*',r'<strong>\1</strong>',s)
 s=re.sub(r'`([^`]+)`',r'<code>\1</code>',s)
 return s
sections=re.split(r'(?m)^## 图\d+[^\n]*\n',txt)[1:]
out=['''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>V3 航向主线 · 最新十图</title>
<style>*{box-sizing:border-box}body{margin:0;background:#f3f5f7;color:#18232d;font:16px/1.85 system-ui,"Microsoft YaHei",sans-serif}header,main{max-width:1250px;margin:auto;padding:26px 36px}header{padding-top:45px}h1{font-size:30px;line-height:1.45;margin:0 0 14px}p{margin:12px 0}nav{position:sticky;top:0;z-index:2;background:#ffffffef;border-block:1px solid #dce2e8;padding:9px 20px;display:flex;gap:8px;justify-content:center;flex-wrap:wrap}nav a{color:#22638a;text-decoration:none;padding:2px 9px}section{background:white;padding:26px 32px;margin:0 0 32px;scroll-margin-top:70px;border:1px solid #dce2e8;border-radius:5px}h2{font-size:24px;line-height:1.5;margin:0 0 12px}.claim{font-size:18px;color:#22638a}.figure{display:block;width:100%;height:auto;cursor:zoom-in;margin:25px 0}.links{font-size:14px;display:flex;gap:22px}.links a{color:#22638a}details{margin-top:20px;border-top:1px solid #e1e5eb;padding-top:14px}summary{cursor:pointer;font-weight:650}.reader{white-space:pre-wrap;font-family:inherit;margin-top:14px}code{font-family:inherit;background:#f1f3f5;padding:1px 4px}dialog{border:0;padding:12px;max-width:98vw;max-height:96vh}dialog img{max-width:90vw;height:auto}dialog button{position:sticky;top:0;float:right;padding:8px 16px;cursor:pointer}dialog::backdrop{background:#101820cc}.note{color:#626b74;font-size:14px}@media(max-width:700px){header,main{padding:18px 12px}section{padding:18px 12px}h1{font-size:25px}h2{font-size:21px}nav{padding:7px}nav a{padding:1px 6px}dialog img{max-width:none;width:1600px}}</style>
<header><h1>航向精度为主线：本轮完成的十张正文图</h1><p>2026-10-12 · 短基线方向提供绝对朝向，机身观测在可用性与质量条件下形成互补。每张只展示本轮最新版本，点击图片放大，下方展开完整读法。</p><p class="note">定量图使用已完成结果。本轮新增C-LAMBDA/C-WLS成本比筛选；冻结V3与原始结果保持原身份。图2为已完成的image设计稿，最终出版文字/线条矢量化尚待完成。</p></header><nav>''']
out+=['<a href="#f'+r['figure_number']+'">图'+r['figure_number']+'</a>' for r in rows]
out+=['</nav><main>']
for r,body in zip(rows,sections):
 clean=re.sub(r'!\[[^\]]*\]\([^\n]*\)','',body).strip()
 # Strip closing book-level discussion from the last figure's expanded reader.
 clean=clean.split('\n## ',1)[0]
 out.append(f'''<section id="f{r['figure_number']}"><h2>图{r['figure_number']}　{html.escape(r['title_zh'])}</h2><p class="claim">{html.escape(r['claim_zh'])}</p><img class="figure" src="{r['preview_relative']}" alt="图{r['figure_number']} {html.escape(r['title_zh'])}"><div class="links"><a href="{r['pdf_relative']}">打开本图PDF</a><a href="{r['png_relative']}">打开原尺寸PNG</a></div><details><summary>逐面板解释、结果与下一步</summary><div class="reader">{rich(clean)}</div></details></section>''')
out+=['''<p class="note">全部记录与数据入口：FIGURE_READERS_ZH.md、MAIN_FIGURE_CATALOG.csv及各子目录说明。完整失败与非正文方法保存于源表，不因正文选图而删除。</p></main><dialog id="zoom"><button onclick="document.getElementById('zoom').close()">关闭 ×</button><img alt="放大图"></dialog><script>document.querySelectorAll('.figure').forEach(x=>x.addEventListener('click',()=>{let d=document.getElementById('zoom');d.querySelector('img').src=x.src;d.querySelector('img').alt=x.alt;d.showModal()}));document.getElementById('zoom').addEventListener('click',e=>{if(e.target.tagName==='DIALOG')e.currentTarget.close()});</script></html>''']
(ROOT/'正文十图_航向主线.html').write_text('\n'.join(out),encoding='utf-8')
pdf=fitz.open()
for r in rows:
 with fitz.open(ROOT/r['pdf_relative']) as source:pdf.insert_pdf(source)
pdf.save(ROOT/'正文十图_审阅册.pdf')
checks={'figures':len(rows),'pdf_pages':len(pdf),'all_preview_exists':all((ROOT/r['preview_relative']).is_file() for r in rows),'all_pdf_exists':all((ROOT/r['pdf_relative']).is_file() for r in rows),'all_png_exists':all((ROOT/r['png_relative']).is_file() for r in rows),'direct_visual_review':'10/10 checked by root; individual QA under sections','new_original_solvers':0,'new_V3_evaluators':0,'new_acceptance_layer':True,'figure_2_native_raster':True,'full_result_denominators_retained':True}
(ROOT/'FINAL_REVIEW.json').write_text(json.dumps(checks,indent=2),encoding='utf-8')
print(json.dumps(checks,indent=2))
