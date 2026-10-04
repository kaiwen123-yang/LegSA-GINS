import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import {FileBlob,PresentationFile} from '@oai/artifact-tool';
const ROOT=process.env.LEGSA_PPT_WORKDIR||'C:/Users/ykw/.codex/tmp/legsa_paper_deck_20261004';
const final=process.env.LEGSA_FINAL_PPTX||path.join(ROOT,'output/LegSA_GINS_研究汇报_20261004.pptx');
const p=await PresentationFile.importPptx(await FileBlob.load(final));
const out=path.join(ROOT,'.build/final_exported');await fs.mkdir(out,{recursive:true});const rows=[];
for(let i=0;i<p.slides.items.length;i++){const name=`slide-${String(i+1).padStart(3,'0')}.png`;const b=Buffer.from(await(await p.slides.items[i].export({format:'png',scale:1})).arrayBuffer());await fs.writeFile(path.join(out,name),b);const candidate=await fs.readFile(path.join(ROOT,'.build/final_render',name));rows.push({page:i+1,file:name,sha256:crypto.createHash('sha256').update(b).digest('hex'),same_as_authoring_png:b.equals(candidate)});if((i+1)%10===0)console.log('final render',i+1);}
await fs.writeFile(path.join(out,'FINAL_RENDER_IDENTITY.json'),JSON.stringify({file:final,sha256:crypto.createHash('sha256').update(await fs.readFile(final)).digest('hex'),pages:rows},null,2));console.log('RENDERED',rows.length,'same authoring bytes',rows.filter(x=>x.same_as_authoring_png).length);
