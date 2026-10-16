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
REV = 'heading_polish_20261013_R5'
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
          or p.name in {'PR_BODY.txt', 'GITHUB_RECEIPT.json', '正文图_R5审阅册.pdf', '正文图_R5修改三图.pdf'}
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
for name in ['README.md', 'FIGURE_READERS_ZH.md', '正文图_R5高清图库.html']:
    target = DEST / name
    value = target.read_text(encoding='utf-8')
    for old, new in sorted(replacements.items(), key=lambda item: -len(item[0])):
        value = value.replace('"' + old + '"', '"' + new + '"').replace('(' + old + ')', '(' + new + ')')
    value = value.replace('href="正文图_R5审阅册.pdf">全部正文十图PDF', 'href="FIGURE_READERS_ZH.md">正文十图说明')
    value = value.replace('href="正文图_R5修改三图.pdf">本轮三图PDF', 'href="README.md">本轮修改说明')
    value = value.replace('[本轮修改三图 PDF](正文图_R5修改三图.pdf)', '[本轮修改说明](FIGURE_READERS_ZH.md)')
    value = value.replace('[全部十图 PDF](正文图_R5审阅册.pdf)', '[逐图 PDF 索引](MAIN_FIGURE_CATALOG.csv)')
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

state = json.loads((BASE / 'STATE.json').read_text(encoding='utf-8'))
state.update(date='2026-10-13', status='R5_TRAJECTORY_DETAIL_TWO_ROBOT_ROUTES_AND_DISTINCT_DEGRADATIONS',
             latest_revision=REV, latest_figure_revision=REV + '/README.md',
             latest_figure_review=REV + '/FIGURE_READERS_ZH.md',
             main_text_figure_selection=REV + '/MAIN_FIGURE_CATALOG.csv', main_text_figure_count=10,
             next_entry=REV + '/README.md', approved_figures_unchanged=[1,2,5,6,7,9,10],
             changed_figures=[3,4,8], figure4_user_confirmed_methods=['Contact-aided InEKF', 'Leg kinematic dead reckoning'],
             figure4_role='Two robot-motion routes and the lack of an absolute-direction anchor; initial-yaw equivariance has a separate role',
             figure4_origin='Panels a/b: saved H5 anchor and six H6 initial-yaw replays. Panels c/d: official InEKF and HX05 LEG-DR, with saved initial-10-second relative evaluation.',
             figure3_heading_comparison_destination='Figure 9',
             figure8_selected_conditions=['D15_seed_00', 'D38_seed_00', 'D53_seed_00'],
             figure8_claim='Compare distinct existing degradation mechanisms, retaining effects, costs and complete denominators',
             new_solver_runs=0, new_evaluator_runs=0, new_provider_runs=0,
             next_discussion='Review F3 spatial readability, F4 two-route interpretation, and F8 representative degradation cases')
(BASE / 'STATE.json').write_text(json.dumps(state, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
intro = f'''# 2026-10-13 正文精修R5：当前入口

**[当前十图与解释]({REV}/FIGURE_READERS_ZH.md)**；[本轮修改]({REV}/README.md)。

本轮修改图3、4、8，图1、2、5、6、7、9、10保持R4。图3把面积还给轨迹与分组局部；图4按作者明确确认，补入接触辅助InEKF与足端运动学航位推算；图8恢复多个物理机制不同的受控退化案例，统一解释输入、质量调整与航向响应。

冻结V3不变，全部取自已完成结果。本轮无新solver/provider/evaluator运行。旧版本保留为历史；继续工作从当前入口阅读。

---

'''
for name in ['README.md', 'CONTINUATION.md']:
    p = BASE / name
    value = p.read_text(encoding='utf-8')
    if not value.startswith('# 2026-10-13 正文精修R5'):
        p.write_text(intro + value, encoding='utf-8')
(REPO / 'PAPER_HANDOFF.md').write_text(f'''# V3 论文当前入口

当前作者轮次为2026-10-13正文精修R5。

- [本轮修改与文件入口](docs/paper_rebuild/GPSS_V3_PAPER_HANDOFF_20261011/{REV}/README.md)
- [正文十图与完整解释](docs/paper_rebuild/GPSS_V3_PAPER_HANDOFF_20261011/{REV}/FIGURE_READERS_ZH.md)

本轮只修改图3、4、8。图3解决完整路线与厘米局部混在狭小坐标中的可读性问题。图4补齐用户确认的两条机器人运动估计路线：接触辅助InEKF、足端运动学航位推算；七初值检查属于单一实现的性质说明，与跨方法相对表现分开。图8展示不同已完成退化案例的输入、来源协方差调整和航向响应，保留完整统计与位置代价。其余七图沿用R4。

主科学问题仍为短基线方向与机身运动观测的互补条件，主打航向精度。冻结V3为7d43b9af26120ed5dde21f53e515386361072ba6；本轮没有新求解、provider或冻结评价器执行。下一步先讨论修改图面和图注，再决定正文结论。
''', encoding='utf-8')
for p in [BASE / 'STATE.json', BASE / 'README.md', BASE / 'CONTINUATION.md', REPO / 'PAPER_HANDOFF.md']:
    p.chmod(0o644)
print(json.dumps({'files': sum(r['storage']=='GITHUB_AND_LOCAL' for r in records),
                  'MB': sum(r['bytes'] for r in records if r['storage']=='GITHUB_AND_LOCAL') / 1e6,
                  'destination': str(DEST)}, indent=2))
