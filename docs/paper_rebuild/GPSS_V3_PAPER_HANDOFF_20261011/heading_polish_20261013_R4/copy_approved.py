from pathlib import Path
import shutil,json,hashlib
ROOT=Path(__file__).resolve().parent
OLD=ROOT.parent/'V3正文精修_20261012_R3'
spec=[('schematics','figures','F01_platform'),('observability','','F04_absolute_direction_relative_motion'),('heading_acceptance','','F05_heading_error_comparison'),('aiding','figures','F06_heading_and_tilt'),('aiding','figures','F07_heading_retained_translation'),('navigation_comparison','','F09_heading_comparison'),('aiding','figures','F10_heading_sensitivity')]
records=[]
for folder,sub,stem in spec:
    for ext in ['pdf','svg','png','tiff']:
        rel=Path(folder)/sub/(stem+'.'+ext)
        target=ROOT/rel;target.parent.mkdir(exist_ok=True,parents=True)
        shutil.copyfile(OLD/rel,target)
        records.append({'path':rel.as_posix(),'same_as_R3':target.read_bytes()==(OLD/rel).read_bytes(),'sha256':hashlib.sha256(target.read_bytes()).hexdigest()})
    rel=Path(folder)/'preview'/(stem+'.png')
    (ROOT/rel).parent.mkdir(exist_ok=True,parents=True);shutil.copyfile(OLD/rel,ROOT/rel)
(ROOT/'APPROVED_FIGURES_LOCK.json').write_text(json.dumps(records,indent=2),encoding='utf-8')
print({'files':len(records),'all_identical':all(r['same_as_R3'] for r in records)})
