"""Prepare private import/reference copies. The user template is never modified."""
from pathlib import Path
import os, re, json, zipfile, hashlib
from xml.etree import ElementTree as ET
base=Path(os.environ.get('LEGSA_PPT_WORKDIR',r'C:\Users\ykw\.codex\tmp\legsa_paper_deck_20261004'))/'.build'
src=Path(os.environ.get('LEGSA_PPT_TEMPLATE',r'C:\Users\ykw\Desktop\泛源定位与组合导航\组会模版.pptx'))
expected='dd521f62d3ef710a0506a7f4677ed7e14564ecac2dc58785ae5b44088aadfb63'
assert hashlib.sha256(src.read_bytes()).hexdigest()==expected, 'Template identity differs; inspect explicitly before reusing layout.'
base.mkdir(parents=True,exist_ok=True)
changes=[]
with zipfile.ZipFile(src) as z, zipfile.ZipFile(base/'template_compatible.pptx','w',zipfile.ZIP_DEFLATED) as out:
 for i in z.infolist():
  data=z.read(i.filename)
  if i.filename.startswith('ppt/charts/') and i.filename.endswith('.xml'):
   def fix(m):
    old=int(m.group(2));new=old%(2**32);changes.append({'part':i.filename,'from':old,'to':new})
    return m.group(1)+str(new).encode()+m.group(3)
   data=re.sub(rb'(<c:(?:axId|crossAx)\b[^>]*\bval=")(-\d+)(")',fix,data)
  out.writestr(i,data)
with zipfile.ZipFile(src) as z, zipfile.ZipFile(base/'template_typography_reference.pptx','w',zipfile.ZIP_DEFLATED) as out:
 p=ET.fromstring(z.read('ppt/presentation.xml'))
 ids=p.find('{http://schemas.openxmlformats.org/presentationml/2006/main}sldIdLst')
 for n,item in enumerate(list(ids),1):
  if n not in (1,24):ids.remove(item)
 for i in z.infolist():out.writestr(i,ET.tostring(p,encoding='utf-8',xml_declaration=True) if i.filename=='ppt/presentation.xml' else z.read(i.filename))
with zipfile.ZipFile(src) as a,zipfile.ZipFile(base/'template_typography_reference.pptx') as b:
 assert all(a.read(n)==b.read(n) for n in a.namelist() if n!='ppt/presentation.xml')
manifest={'original_source':str(src),'original_sha256':expected,'chart_axis_compatibility_changes':changes,'reference_subset':str(base/'template_typography_reference.pptx'),'reference_sha256':hashlib.sha256((base/'template_typography_reference.pptx').read_bytes()).hexdigest(),'selected_original_slides':[1,24],'all_other_package_parts_byte_identical':True,'reason':'Use actual original cover/content typography; unused source slide 32 has unresolved East Asian inheritance. No source font substitution.'}
(base/'TYPOGRAPHY_REFERENCE.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(manifest,ensure_ascii=False))
