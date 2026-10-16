from pathlib import Path
import csv
ROOT=Path(__file__).resolve().parent
spec=[
(1,'F01_platform','紧凑四足平台与短基线安装','schematics','F01_platform','照片与名义几何共同定义紧凑平台上的方向来源。','READY_FOR_AUTHOR_REVIEW'),
(2,'F02_method','方向与机身观测的共同状态融合','schematics','F02_method','方向质量选择与辅助门控作用于真实更新路径。','DESIGN_COMPLETE_RASTER_NATIVE'),
(3,'F03_event_routes_and_heading','沿真实事件看路线与航向误差','navigation','F03_event_routes_and_heading','把转弯和遮挡中的航向精度与空间过程联系起来。','READY_FOR_AUTHOR_REVIEW'),
(4,'F04_absolute_direction_relative_motion','不同绝对朝向与相同相对运动','observability','F04_absolute_direction_relative_motion','同一自身观测保留全局方向自由度，需要绝对方向约束。','READY_FOR_AUTHOR_REVIEW'),
(5,'F05_heading_error_comparison','短基线方向处理路线的误差比较','heading_acceptance','F05_heading_error_comparison','本文方向观测更集中于小误差；新增工程筛选后的原始处理路线仍有限制。','READY_FOR_AUTHOR_REVIEW'),
(6,'F06_heading_and_tilt','持续方向更新的航向收益','aiding','F06_heading_and_tilt','持续方向更新贡献自然场景中主要航向收益；倾角对其他姿态分量另有作用。','READY_FOR_AUTHOR_REVIEW'),
(7,'F07_heading_retained_translation','方向保持条件下的平移作用','aiding','F07_heading_retained_translation','方向与辅助更新持续时，机身速度显著限制位置漂移。','READY_FOR_AUTHOR_REVIEW'),
(8,'F08_heading_quality_scaling','质量变化下的航向保持与位置代价','aiding','F08_heading_quality_scaling','来源质量处理可保护航向，但并非所有状态同时改善。','READY_FOR_AUTHOR_REVIEW'),
(9,'F09_heading_comparison','滤波与因子图方法的航向比较','navigation','F09_heading_comparison','航向优势随输入和场景变化，保留标定双位置IEKF的反例。','READY_FOR_AUTHOR_REVIEW'),
(10,'F10_heading_sensitivity','航向质量条件与跨源冲突边界','aiding','F10_heading_sensitivity','已测方向扰动范围内收益保持，跨源冲突仍有两个重点精度边界。','READY_FOR_AUTHOR_REVIEW')]
rows=[]
def winpath(path):
 text=str(path).replace('\\','/')
 return 'G:/'+text[len('/mnt/g/'):] if text.startswith('/mnt/g/') else text
for no,fid,title,folder,stem,claim,status in spec:
 base=Path(folder)/('figures' if folder in ['aiding','schematics'] else '')/stem
 preview=Path(folder)/'preview'/(stem+'.png')
 rows.append({'figure_number':no,'figure_id':fid,'title_zh':title,'claim_zh':claim,'status':status,'preview_relative':preview.as_posix(),'preview_path':winpath(ROOT/preview),'png_relative':base.as_posix()+'.png','png_path':winpath(ROOT/base)+'.png','pdf_relative':base.as_posix()+'.pdf','pdf_path':winpath(ROOT/base)+'.pdf','svg_relative':base.as_posix()+'.svg' if no!=2 else '', 'tiff_relative':base.as_posix()+'.tiff' if no!=2 else '', 'reader':'FIGURE_READERS_ZH.md','folder':folder,'preview_exists_at_catalog_build':(ROOT/preview).exists()})
with (ROOT/'MAIN_FIGURE_CATALOG.csv').open('w',newline='',encoding='utf-8-sig') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
print('Catalog:',len(rows),'main figures;',sum(r['preview_exists_at_catalog_build'] for r in rows),'previews present')
