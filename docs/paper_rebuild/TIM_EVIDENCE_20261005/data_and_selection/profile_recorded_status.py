"""Selected acquisition status and header audit; never infer firmware from schema."""
import ast,collections,csv,io,json,hashlib,zipfile
from pathlib import Path
from profile_candidates import OUT,ZIP,zcsv,save
prior={x['member']:x for x in json.loads((OUT/'ZIP_METADATA_PROFILE.json').read_text())}
raw={x['member']:x for x in json.loads((OUT/'ZIP_USERIO_METADATA_PROFILE.json').read_text())}
res=[]
with zipfile.ZipFile(ZIP)as z:
 for folder in [i.filename for i in z.infolist()if i.is_dir()]:
  name=folder+'user_io-out-odom_status.csv';h,f,rows=zcsv(z,name);counts=collections.defaultdict(collections.Counter);n=0
  for r in rows:
   n+=1
   for k in r:
    if k not in ['Time','header.seq','header.stamp.secs','header.stamp.nsecs']:counts[k][r[k]]+=1
  f.close();assert h.h.hexdigest()==prior[name]['sha256'];version=None;version_header_prefix=None
  name_raw=folder+'userio-raw.csv'
  with io.TextIOWrapper(z.open(name_raw),encoding='utf-8',newline='')as f:
   for r in csv.DictReader(f):
    if r['name']=='FP_A-ODOMETRY':
     b=ast.literal_eval(r['data']);parts=b.decode('ascii').split(',');assert parts[:2]==['$FP','ODOMETRY'];version=parts[2];version_header_prefix=','.join(parts[:5]);break
  res.append(dict(folder=folder,odom_status_rows=n,status_field_counts={k:dict(v)for k,v in counts.items()},odom_status_source_sha256=prior[name]['sha256'],actual_ODOMETRY_message_version=version,actual_ODOMETRY_header_prefix=version_header_prefix,userio_source_sha256=raw[name_raw]['sha256'],firmware_version='NOT_ESTABLISHED_BY_AVAILABLE_VERSION_MESSAGES',receiver_MON_VER_messages=0,FP_A_TEXT_messages=0,interpretation='ODOMETRY/TF schema version2 is not installed Fixposition firmware version; fusion enums retained literally'))
save('RECORDED_OUTPUT_STATUS_AND_VERSION.json',res)
print(json.dumps([{k:x[k]for k in ['folder','odom_status_rows','status_field_counts','actual_ODOMETRY_message_version']}for x in res],ensure_ascii=False,indent=2))
