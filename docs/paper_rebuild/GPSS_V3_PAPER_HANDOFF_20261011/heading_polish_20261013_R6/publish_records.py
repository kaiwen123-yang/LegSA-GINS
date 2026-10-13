"""Copy the reviewed revision into the existing documentation worktree."""
from pathlib import Path
import argparse
import csv
import json
import shutil

parser = argparse.ArgumentParser()
parser.add_argument('--repo', type=Path, required=True)
args = parser.parse_args()
ROOT = Path(__file__).resolve().parent
REPO = args.repo.resolve()
BASE = REPO / 'docs/paper_rebuild/GPSS_V3_PAPER_HANDOFF_20261011'
REV = 'heading_polish_20261013_R6'
PREV = 'heading_polish_20261013_R4'
DEST = BASE / REV
assert (REPO / '.git').exists()
DEST.mkdir(parents=True, exist_ok=True)
retained = {r['path'].replace('\\', '/') for r in json.loads((ROOT / 'RETAINED_FIGURES.json').read_text(encoding='utf-8'))}
retained.update(['schematics/F02_矢量放大查看.html', 'schematics/figures/F02_method_8K.png',
                 'schematics/figures/F02_method_4K.png', 'schematics/figures/F02_method_reading.pdf',
                 'schematics/editable/F02_method_traced.svg'])
records = []
replacements = {}
for rel in retained:
    if (BASE / PREV / rel).is_file():
        replacements[rel] = '../' + PREV + '/' + rel
for p in sorted(ROOT.rglob('*')):
    if not p.is_file():
        continue
    rel = p.relative_to(ROOT).as_posix()
    if rel in replacements:
        storage = 'REUSE_R4'
    elif (p.suffix.lower() in {'.tiff', '.tif', '.nav', '.gnss', '.pos', '.svg'}
          or '__pycache__' in p.parts
          or p.name in {'PR_BODY.txt', 'GITHUB_RECEIPT.json', '正文图_R6审阅册.pdf', '正文图_R6修改三图.pdf'}
          or p.name.endswith('.pdf.txt')):
        storage = 'LOCAL_ONLY'
    else:
        storage = 'GITHUB_AND_LOCAL'
    records.append({'path': rel, 'storage': storage, 'bytes': p.stat().st_size})
    if storage != 'GITHUB_AND_LOCAL':
        continue
    dst = DEST / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(p, dst)
    dst.chmod(0o644)

# References in the top-level reader/gallery point to already archived approved assets.
for name in ['README.md', 'FIGURE_READERS_ZH.md', '正文图_R6高清图库.html']:
    target = DEST / name
    value = target.read_text(encoding='utf-8')
    for old, new in sorted(replacements.items(), key=lambda item: -len(item[0])):
        value = value.replace('"' + old + '"', '"' + new + '"').replace('(' + old + ')', '(' + new + ')')
    value = value.replace('href="正文图_R6审阅册.pdf">全部正文十图PDF', 'href="FIGURE_READERS_ZH.md">正文十图说明')
    value = value.replace('href="正文图_R6修改三图.pdf">本轮三图PDF', 'href="README.md">本轮修改说明')
    value = value.replace('[本轮三图 PDF](正文图_R6修改三图.pdf)', '[本轮修改说明](FIGURE_READERS_ZH.md)')
    value = value.replace('[全部十图 PDF](正文图_R6审阅册.pdf)', '[逐图 PDF 索引](MAIN_FIGURE_CATALOG.csv)')
    if name.endswith('.html'):
        for row in csv.DictReader((ROOT / 'MAIN_FIGURE_CATALOG.csv').open(encoding='utf-8-sig')):
            svg = replacements.get(row['svg'], row['svg'])
            pdf = replacements.get(row['pdf'], row['pdf'])
            value = value.replace('href="' + svg + '">可编辑SVG', 'href="' + pdf + '">矢量PDF')
    target.write_text(value, encoding='utf-8')
catalog_rows = list(csv.DictReader((ROOT / 'MAIN_FIGURE_CATALOG.csv').open(encoding='utf-8-sig')))
for row in catalog_rows:
    for key in ['preview', 'pdf', 'svg', 'png']:
        row[key] = replacements.get(row[key], row[key])
with (DEST / 'MAIN_FIGURE_CATALOG.csv').open('w', newline='', encoding='utf-8-sig') as f:
    writer = csv.DictWriter(f, fieldnames=list(catalog_rows[0]))
    writer.writeheader()
    writer.writerows(catalog_rows)
(DEST / 'SCREEN_EXPORTS.json').write_text(json.dumps(catalog_rows, ensure_ascii=False, indent=2), encoding='utf-8')
with (DEST / 'ARTIFACT_STORAGE.csv').open('w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=['path', 'storage', 'bytes'])
    writer.writeheader()
    writer.writerows(records)
(DEST / '.gitattributes').write_text('*.csv -text -whitespace\n*.gz binary\n*.png binary\n*.pdf binary\n', encoding='utf-8')

state = json.loads((BASE/'STATE.json').read_text(encoding='utf-8'))
state.update(date='2026-10-13', status='R6_LAYOUT_REVISION_AND_FIGURE4_RESTORED',
             latest_revision=REV, latest_figure_revision=REV+'/README.md',
             latest_figure_review=REV+'/FIGURE_READERS_ZH.md',
             main_text_figure_selection=REV+'/MAIN_FIGURE_CATALOG.csv', main_text_figure_count=10,
             next_entry=REV+'/README.md', approved_figures_unchanged=[1,2,5,6,7,9,10],
             changed_figures=[3,4,8], figure4_restored_from='R4 identical publication files',
             figure4_role='One estimator and recording, seven initial global orientations; two main trajectory panels plus a numerical residual strip',
             figure4_origin='H5 zero-yaw primary output plus six existing H6 initial-orientation replays',
             figure4_two_route_comparison_destination='R5 archived supplementary material; removed from current main Figure 4 at author request',
             figure3_layout='Three scenes by three columns: full route, single explicit spatial zoom, 100-s heading',
             figure3_heading_comparison_destination='Local heading context in Fig3; systematic comparison in Fig9',
             figure8_layout_only_revision=True,
             figure8_selected_conditions=['D15_seed_00','D38_seed_00','D53_seed_00'],
             new_solver_runs=0,new_evaluator_runs=0,new_provider_runs=0,
             next_discussion='Review the cleaner F3 layout, the restored F4 seven-initial-orientation explanation, and F8 palette and proportions')
state.pop('figure4_user_confirmed_methods', None)
(BASE/'STATE.json').write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
intro=f'''# 2026-10-13 正文精修R6：当前入口

**[当前正文十图与解释]({REV}/FIGURE_READERS_ZH.md)**；[本轮修改]({REV}/README.md)。

作者否定R5图3的细带分组及图4新增的复杂比较。当前图3恢复完整路线、单个空间放大、100s航向的整齐三列；图4恢复R4原文件，只解释同一方法与数据的七种初始全局朝向；图8保留三种退化，调整冷暖配色、三列比例与留白。图1、2、5、6、7、9、10保持上一版。

R5两条机器人路线比较仍保留在历史/补充，不再塞回当前正文图4。冻结V3与原结果不变，无新科学执行。本轮为作者审阅版本，以下为历史记录。

---

'''
for name in ['README.md','CONTINUATION.md']:
    path=BASE/name
    value=path.read_text(encoding='utf-8')
    if not value.startswith('# 2026-10-13 正文精修R6'):
        path.write_text(intro+value,encoding='utf-8')
(REPO/'PAPER_HANDOFF.md').write_text(f'''# V3 论文当前入口

最新作者轮次：2026-10-13正文精修R6。

- [当前修改与文件入口](docs/paper_rebuild/GPSS_V3_PAPER_HANDOFF_20261011/{REV}/README.md)
- [正文十图与解释](docs/paper_rebuild/GPSS_V3_PAPER_HANDOFF_20261011/{REV}/FIGURE_READERS_ZH.md)

图3采用三场景×三列整齐布局，取消R5九条分组细带。图4恢复R4的原出版文件，七次运行是同一接触辅助InEKF、同一段IMU/足位/接触输入、七种初始全局朝向；0°复用主运行，六个非零设置为既有回放。右图去掉已知旋转后重合，下方为数值一致性残差。R5新加的两机器人路线比较按作者意见从正文图4撤下，结果仍保留。

图8保持三种退化与R5全部数值，调整深蓝/暖朱红配色和列宽比例。其它七图保持上一版。当前任务是审阅图面与图注，不重启数值主线。

科学问题仍围绕紧凑四足平台中短基线方向与机身运动观测的互补条件，主打航向精度。冻结V3：7d43b9af26120ed5dde21f53e515386361072ba6；本轮无solver/provider/evaluator执行。
''',encoding='utf-8')
for p in [BASE/'STATE.json',BASE/'README.md',BASE/'CONTINUATION.md',REPO/'PAPER_HANDOFF.md']:
    p.chmod(0o644)
print(json.dumps({'files':sum(r['storage']=='GITHUB_AND_LOCAL' for r in records),
                  'MB':sum(r['bytes'] for r in records if r['storage']=='GITHUB_AND_LOCAL')/1e6,
                  'destination':str(DEST)},indent=2))
