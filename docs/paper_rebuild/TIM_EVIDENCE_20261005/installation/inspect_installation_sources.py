"""Inspect user-provided installation sources without changing or extracting originals."""
import argparse, hashlib, json, re, zipfile
from pathlib import Path
import xml.etree.ElementTree as ET


def sha(data):
    return hashlib.sha256(data).hexdigest()


def inspect(cad, urdf_zip, manual):
    selected = ['a1-底座a.SLDPRT', 'a1-底座b.SLDPRT', 'b1-亚克力板.SLDPRT',
                'print/a1-底座a.STEP', 'print/a1-底座b.STEP', 'print/b3-亚克力板.STL',
                'z1-总装.SLDASM', 'z1-总装.STEP']
    files = []
    for label, path in [(x, cad / x) for x in selected] + [('Go2_URDF.zip', urdf_zip), ('快速开启保姆级教程.pdf', manual)]:
        data = path.read_bytes()
        entry = {'source_label': label, 'bytes': len(data), 'sha256': sha(data)}
        if path.suffix.lower() == '.step':
            text = data.decode('latin1')
            entry['si_unit_declarations'] = re.findall(r'SI_UNIT\s*\([^;]+;', text)
            entry['product_declarations'] = re.findall(r'(?<![A-Z_])PRODUCT\s*\([^;]+;', text)
            entry['cartesian_point_entities'] = len(re.findall(r'=\s*CARTESIAN_POINT\s*\(', text))
            entry['interpretation'] = 'Neutral-file structure inspected; not a solid-model survey or measured antenna phase center.'
        files.append(entry)
    with zipfile.ZipFile(urdf_zip) as archive:
        names = archive.namelist()
        member = next(n for n in names if n.endswith('/urdf/go2_description.urdf') and '.history/' not in n)
        raw = archive.read(member)
        robot = ET.fromstring(raw)
        joints = []
        for node in robot.findall('joint'):
            origin = node.find('origin')
            joints.append({'name': node.get('name'), 'type': node.get('type'),
                           'parent': node.find('parent').get('link'), 'child': node.find('child').get('link'),
                           'xyz': origin.get('xyz', '0 0 0') if origin is not None else '0 0 0',
                           'rpy': origin.get('rpy', '0 0 0') if origin is not None else '0 0 0'})
        urdf = {'member': member, 'sha256': sha(raw), 'link_count':len(robot.findall('link')), 'joints':joints,
                'zip_members':len(names), 'history_members':sum('.history/' in n for n in names)}
        xmember = next(n for n in names if n.endswith('/xacro/robot.xacro') and '.history/' not in n)
        xraw = archive.read(xmember)
        xroot = ET.fromstring(xraw)
        imu_joints = []
        for node in xroot.findall('joint'):
            if 'imu' in str(node.attrib).lower() or any('imu' in str(c.attrib).lower() for c in node):
                imu_joints.append(ET.tostring(node, encoding='unicode'))
        urdf['xacro'] = {'member': xmember, 'sha256':sha(xraw), 'imu_joint_declarations':imu_joints}
    import fitz
    pdf = fitz.open(manual)
    pages = []
    for i, page in enumerate(pdf):
        text = page.get_text()
        pages.append({'page_1based':i+1, 'text_chars':len(text),
                      'topic_snippets':[line.strip() for line in text.splitlines() if any(term in line for term in ['外参','相机','坐标','输出','3 cm','3cm','精度','129','114','0.175','0.020'])]})
    return {'schema':'installation-source-inspection-v1', 'source_files':files, 'urdf':urdf,
            'manual':{'pages':len(pdf), 'page_topics':pages},
            'limits':['CAD files represent the installation according to the author; numeric base-to-sensor calibration is not thereby established.',
                      'URDF transforms are nominal model declarations; SDK state frame and actual sensitive-center equivalence require independent evidence.',
                      'No scientific configuration or original source file was edited.']}


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--cad-dir', type=Path, required=True)
    p.add_argument('--urdf-zip', type=Path, required=True)
    p.add_argument('--manual', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    args = p.parse_args()
    args.out.write_text(json.dumps(inspect(args.cad_dir, args.urdf_zip, args.manual), ensure_ascii=False, indent=2)+'\n', encoding='utf-8')