import fs from 'node:fs/promises';
import path from 'node:path';
import {FileBlob,PresentationFile} from '@oai/artifact-tool';
const ROOT=process.env.LEGSA_PPT_WORKDIR||'C:/Users/ykw/.codex/tmp/legsa_paper_deck_20261004';
const p=await PresentationFile.importPptx(await FileBlob.load(path.join(ROOT,'.build/template_compatible.pptx')));
const original=p.slides.items;
const templates={cover:original[0],section:original[2],content:original[23],photo:original[6],two:original[19]};
const order=[];const metadata=[];const BLUE='#024282',GREY='#374151',MUTED='#64748B',FONT='微软雅黑';
function text(s,t,x,y,w,h,size=26,color=GREY,bold=false,align='left',name='text'){
 const q=s.shapes.add({geometry:'textbox',name,position:{left:x,top:y,width:w,height:h},fill:'none',line:{fill:'none',width:0}});
 q.text=t;q.text.style={typeface:FONT,fontSize:size,color,bold,alignment:align,verticalAlignment:'middle',wrap:'square',autoFit:'none',insets:{left:0,right:0,top:0,bottom:0}};return q;
}
async function layout(s){return JSON.parse(await (await s.export({format:'layout'})).text());}
async function base(title,sub='',kind='content'){
 const s=templates[kind].duplicate();order.push(s.id);const l=await layout(s);
 const remove=[];
 for(const e of l.elements){
  if(e.position.top>=95 && e.position.top<670 || (e.text&&e.text.includes('JUNE')))remove.push(e.id);
  else if(e.text&&e.text.includes('请输入你的标题')){const q=p.resolve(e.id);q.text=title;q.position={left:118,top:18,width:810,height:61};q.text.style={fontSize:38,typeface:FONT,bold:true,color:BLUE};}
 }
 if(remove.length)p.delete(remove);
 if(sub)text(s,sub,52,101,1176,40,23,MUTED,false);
 text(s,String(order.length).padStart(2,'0'),1142,680,82,26,18,MUTED,false,'right','page');
 metadata.push({page:order.length,title,kind});return s;
}
function note(s,value){s.speakerNotes.textFrame.setText(value);}
async function photo(s){
 const src=path.join(REPO,'docs/paper_rebuild/JOURNAL_REFRAME_20261004/presentation/platform/Original_installation.jpg');const b=await fs.readFile(src);
 s.images.add({blob:b,contentType:'image/jpeg',alt:'用户提供的真实机器人安装照片；只裁剪显示区域，原始像素未生成修改',fit:'contain',crop:{left:.355,top:.28,right:.14,bottom:.12},position:{left:65,top:155,width:562,height:500}});
 s.images.add({blob:b,contentType:'image/jpeg',alt:'同一原图的设备局部放大',fit:'contain',crop:{left:.51,top:.28,right:.28,bottom:.53},position:{left:710,top:160,width:500,height:339.15}});
 text(s,'顶部搭载装置',710,512,500,38,28,BLUE,true);
 text(s,'双天线 / GNSS 与融合装置\n安装几何需结合标定记录说明',710,560,500,74,23);

 note(s,'Source: user photograph C:/Users/ykw/Desktop/3ea6720b5e477e28ce8bec9d475423f5.jpg; SHA256 a5aac11a5cde1e99bd31d0342b5e3351d428e92ae5f74ef5547f9a35508cb64b. Native PPT crop only, same original JPEG embedded. Magnified inset intentionally reuses same photograph to show equipment details. Nominal physical dimensions require independent measurement.');
}
const REPO=process.env.LEGSA_REPO||'//wsl.localhost/Ubuntu-22.04/home/kaiwen/research/LegSA-GINS-WORKTREES/audit-code-xbpg-20261001';
const REF='docs/paper_rebuild/JOURNAL_REFRAME_20261004/';
const STORY='docs/paper_rebuild/V3_STORY_20261004/';
const assets=[];const tableOwners=[],chartOwners=[];
async function cover(){
 const s=templates.cover.duplicate();order.push(s.id);const l=await layout(s);
 for(const e of l.elements){if(e.kind==='textbox'&&e.text!=='BEIHANG UNIVERSITY')p.delete(e.id);}
 text(s,'短基线双天线 GNSS/INS\n四足机器人导航研究',90,267,1100,171,58,'#FFFFFF',true,'center');
 text(s,'航向可用条件 · 速度辅助 · 失效边界与测量不确定度',120,477,1040,44,25,'#FFFFFF',false,'center');
 text(s,'2026年10月04日',502,545,276,38,24,BLUE,false,'center');
 text(s,'完整研究与实验报告',328,630,269,34,22,'#FFFFFF',false,'center');
 text(s,'GPS Solutions / TIM',684,630,270,34,21,'#FFFFFF',false,'center');
 note(s,'Project scientific report. Method display label Proposed maps to archived original V3 full configuration. Academic descriptive name remains for author discussion. Uses the supplied institutional template; speaker and adviser names not provided.');metadata.push({page:order.length,title:'短基线双天线 GNSS/INS 四足机器人导航研究',kind:'cover'});return s;
}
function box(s,t,x,y,w,h,{size=25,color=BLUE,fill='#FFFFFF'}={}){const q=s.shapes.add({geometry:'rect',position:{left:x,top:y,width:w,height:h},fill,line:{fill:color,width:1.5}});q.text=t;q.text.style={typeface:FONT,fontSize:size,color,alignment:'center',verticalAlignment:'middle',wrap:'square',insets:{left:9,right:9,top:6,bottom:6}};return q;}
function connect(s,a,b,{from='right',to='left',color=BLUE,dashed=false}={}){return s.shapes.connect(a,b,{kind:'elbow',fromSide:from,toSide:to,line:{fill:color,width:2,style:dashed?'dashed':'solid'},tail:{type:'arrow',width:'med',length:'med'}});}
function line(s,x,y,w,h,color=BLUE,width=2){return s.shapes.add({geometry:'line',position:{left:x,top:y,width:w,height:h},fill:'none',line:{fill:color,width}});}
function caption(s,value){text(s,value,56,622,1168,42,23,BLUE,true);}
function source(s,paths,extra=''){note(s,[extra,...paths.map(x=>'Source: '+x)].join('\n'));if(metadata.length)metadata[metadata.length-1].sources=paths;}
async function equation(s,name,x,y,w,h){
 const b=await fs.readFile(path.join(ROOT,'.build/equations',name+'.png'));
 const iw=b.readUInt32BE(16),ih=b.readUInt32BE(20),z=Math.min(w/iw,h/ih);
 return s.images.add({blob:b,contentType:'image/png',alt:'Scientific equation: '+name,fit:'contain',position:{left:x,top:y+(h-ih*z)/2,width:iw*z,height:ih*z}});
}
function table(s,values,{x=54,y=162,w=1172,h=420,widths,font=23,headerFont=22}={}){
 const t=s.tables.add({rows:values.length,columns:values[0].length,left:x,top:y,width:w,height:h,columnWidths:widths,values});
 t.cells.block({row:0,column:0,rowCount:values.length,columnCount:values[0].length}).assign({textStyle:{fontSize:font,typeface:FONT,color:GREY},fill:'#FFFFFF',margins:{left:10,right:8,top:6,bottom:6}});
 t.cells.block({row:0,column:0,rowCount:1,columnCount:values[0].length}).assign({fill:BLUE,textStyle:{fontSize:headerFont,typeface:FONT,color:'#FFFFFF',bold:true}});
 t.borders.assign({fill:'#CBD5E1',width:.6,style:'solid'});tableOwners.push(order.length);return t;
}
async function figure(title,relative,{sub='',finding='',sourceText=''}={}){
 const s=await base(title,sub);const file=relative.startsWith('C:')||relative.startsWith('G:')?relative:path.join(REPO,relative);
 const b=await fs.readFile(file); // PNG dimensions; no image resampling or data modification.
 if(b.readUInt32BE(0)!==0x89504e47)throw new Error('PNG required '+relative);
 const iw=b.readUInt32BE(16),ih=b.readUInt32BE(20);let mxW=1180,mxH=finding?474:516;let y=sub?147:108;if(sub&&!finding)mxH=516;
 const z=Math.min(mxW/iw,mxH/ih),w=iw*z,h=ih*z;
 s.images.add({blob:b,contentType:'image/png',alt:title,fit:'contain',position:{left:(1280-w)/2,top:y+(mxH-h)/2,width:w,height:h}});
 if(finding)caption(s,finding);source(s,[relative],sourceText);assets.push(relative);metadata[metadata.length-1].asset=relative;return s;
}
async function figureCrop(title,relative,crop,{sub='',sourceText=''}={}){
 crop={left:0,top:0,right:0,bottom:0,...crop};
 const s=await base(title,sub);const b=await fs.readFile(path.join(REPO,relative));
 const iw=b.readUInt32BE(16)*(1-(crop.left||0)-(crop.right||0));
 const ih=b.readUInt32BE(20)*(1-(crop.top||0)-(crop.bottom||0));
 const z=Math.min(1180/iw,510/ih);const w=iw*z,h=ih*z;
 s.images.add({blob:b,contentType:'image/png',alt:title+'；原图原生裁剪放大，数据像素未改',fit:'contain',crop,position:{left:(1280-w)/2,top:151+(510-h)/2,width:w,height:h}});
 source(s,[relative],sourceText+' Native PowerPoint display crop; original PNG is embedded unchanged. The preceding overview retains the full plot.');
 assets.push(relative);metadata[metadata.length-1].asset=relative;metadata[metadata.length-1].displayCrop=crop;return s;
}
function chart(s,title,categories,series,{x=70,y=175,w=1140,h=410,yTitle='',max,stacked=false,bar=false}={}){
 const c=s.charts.add('bar',{position:{left:x,top:y,width:w,height:h},title,titleTextStyle:{typeface:FONT,fontSize:25,bold:true},categories,series,hasLegend:series.length>1,legend:{position:'bottom',textStyle:{typeface:FONT,fontSize:21}},barOptions:{direction:bar?'bar':'column',grouping:stacked?'stacked':'clustered',gapWidth:80},chartFill:'#FFFFFF',plotAreaFill:'#FFFFFF',xAxis:{textStyle:{typeface:FONT,fontSize:21},majorGridlines:null},yAxis:{title:{text:yTitle,textStyle:{typeface:FONT,fontSize:22}},textStyle:{typeface:FONT,fontSize:20},min:0,...(max===undefined?{}:{max}),majorGridlines:{fill:'#E2E8F0',width:1}},dataLabels:{showValue:true,position:stacked?'center':'outEnd',textStyle:{typeface:FONT,fontSize:21,fill:GREY}}});chartOwners.push(order.length);return c;
}
async function prose(title,items,{sub='',end='',paths=[]}={}){
 const s=await base(title,sub);const heights=items.map(()=>Math.min(135,440/items.length));let y=170;
 items.forEach((item,i)=>{text(s,String(i+1).padStart(2,'0'),66,y,70,55,38,BLUE,true);text(s,item,171,y,1024,heights[i]-14,28);y+=heights[i];});if(end)caption(s,end);source(s,paths);return s;
}
export {fs,path,FileBlob,PresentationFile,p,ROOT,REPO,REF,STORY,order,metadata,assets,tableOwners,chartOwners,BLUE,GREY,MUTED,FONT,text,base,photo,cover,box,connect,line,caption,table,figure,figureCrop,chart,prose,note,source,layout,equation};
