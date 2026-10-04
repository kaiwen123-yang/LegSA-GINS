import {c} from './deck_appendix.mjs';
import {pathToFileURL} from 'node:url';
import crypto from 'node:crypto';
const {fs,path,p,ROOT,REPO,order,metadata,tableOwners,chartOwners,assets,PresentationFile}=c;
p.slides.keep(order.map(x=>'sl/'+x.replace(/^sl\//,'')));p.slides.reorder(order.map(x=>'sl/'+x.replace(/^sl\//,'')));
const renderDir=path.join(ROOT,'.build/final_render');await fs.mkdir(renderDir,{recursive:true});
const sources=[];
for(const m of metadata)for(const s of m.sources||[]){if(s.startsWith('http')){sources.push({page:m.page,path:s,type:'web'});continue;}const resolved=path.join(REPO,s);await fs.access(resolved);const b=await fs.readFile(resolved);sources.push({page:m.page,path:s,sha256:crypto.createHash('sha256').update(b).digest('hex'),bytes:b.length});}
const st=path.join(ROOT,'.codex-finalizer');await fs.mkdir(st,{recursive:true});await fs.mkdir(path.join(ROOT,'output'),{recursive:true});
const candidate=path.join(st,'candidate.pptx');await(await PresentationFile.exportPptx(p)).save(candidate);
await fs.writeFile(path.join(st,'DECK_SOURCE_INDEX.json'),JSON.stringify({slide_count:metadata.length,slides:metadata,tableOwners,chartOwners,assets,sources},null,2));
// Render this exact candidate state for independent visual review before delivery.
for(let i=0;i<p.slides.items.length;i++){const b=await p.slides.items[i].export({format:'png',scale:1});await fs.writeFile(path.join(renderDir,`slide-${String(i+1).padStart(3,'0')}.png`),new Uint8Array(await b.arrayBuffer()));if((i+1)%10===0)console.log('rendered',i+1);}
const SKILL='C:/Users/ykw/.codex/plugins/cache/openai-primary-runtime/presentations/26.930.11008/skills/presentations';
const typography=JSON.parse(await fs.readFile(path.join(ROOT,'.build/TYPOGRAPHY_REFERENCE.json'),'utf8'));
const {finalizePresentation}=await import(pathToFileURL(path.join(SKILL,'container_tools/artifact_tool_utils.mjs')).href);
const final=path.join(ROOT,'output/LegSA_GINS_研究汇报_20261004.pptx');
const result=await finalizePresentation({workspaceDir:ROOT,candidatePath:candidate,finalPath:final,pythonExecutable:'C:/Users/ykw/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe',integrityValidatorPath:path.join(SKILL,'container_tools/inspect_presentation_package_integrity.py'),layoutValidatorPath:path.join(SKILL,'container_tools/inspect_presentation_layout_geometry.py'),layoutArgs:['--expected-slide-size-emu','12192000,6858000','--validate-bullet-geometry','--validate-heading-fit',...tableOwners.flatMap(n=>['--require-native-table-slide',String(n)])],requiredNativeTableOwnerSlides:tableOwners,requiredNativeChartOwnerSlides:chartOwners,materializeLiteralChartWorkbooks:true,fontPolicy:{basis:'reference',families:['微软雅黑','Calibri'],referencePath:path.join(ROOT,'.build/template_typography_reference.pptx'),referenceSha256:typography.reference_sha256},verifyArtifactToolImport:true,receiptPath:path.join(st,'FINAL_VALIDATION_RELEASE.json')});
console.log('FINAL',JSON.stringify({slides:metadata.length,final,sha256:result.finalSha256||null},null,2));
