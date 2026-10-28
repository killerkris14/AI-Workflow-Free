/* REMEMBERED LOCAL PROCESSING TOGGLE v1 */
/* ROUTING APPROVAL SHORTCUT v1 */
/* AUTOROUTING REVIEW CHECKPOINT GUARD v1 */
/* NATIVE COLOR CHECKPOINT GUARD v1 */
/* HEADER WORKFLOW SWITCH v1 */
(() => {
'use strict';
const KEY='__ACCESS_TOKEN__';
const $=id=>document.getElementById(id);
const make=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;};
async function api(route,payload){const options={headers:{'X-Workflow-Key':KEY},cache:'no-store'};if(payload!==undefined){options.method='POST';options.headers['Content-Type']='application/json';options.body=JSON.stringify(payload);}const response=await fetch(route,options);const data=await response.json();if(!response.ok)throw new Error(data.error||('HTTP '+response.status));return data;}
function select(options){const n=make('select');for(const [value,label]of options){const o=make('option',label);o.value=value;n.append(o);}return n;}
function field(parent,label,input){const l=make('label',label,'title');parent.append(l,input);return input;}
function textInput(value,type='text'){const n=make('input');n.type=type;n.value=value;return n;}
const existing=$('create-panel');if(!existing)return;
const panel=make('section',undefined,'panel');panel.id='hunyuan-create';existing.before(panel);
const tabs=make('div',undefined,'row');tabs.style.marginBottom='10px';const hy=make('button','Image to 3D'),legacy=make('button','Blender workflow');hy.type=legacy.type='button';tabs.append(hy,legacy);const statusNode=$('connection');
const headerTools=make('div',undefined,'portal-header-tools');
tabs.classList.add('portal-workflow-switch');tabs.style.marginBottom='0';
if(statusNode){statusNode.before(headerTools);headerTools.append(tabs,statusNode);}else{document.querySelector('header').append(headerTools);headerTools.append(tabs);}
function mode(useHunyuan){panel.hidden=!useHunyuan;existing.hidden=useHunyuan;hy.classList.toggle('primary',useHunyuan);legacy.classList.toggle('primary',!useHunyuan);}
hy.onclick=()=>mode(true);legacy.onclick=()=>mode(false);mode(true);
panel.append(make('h2','Image to 3D'),make('p','Background removal → image approval → Hunyuan → mesh approval → 3MF.','muted small'));
const connection=make('p','Checking ComfyUI...','muted small');panel.append(connection);
const form=make('form');panel.append(form);const image=make('input');image.type='file';image.accept='image/png,image/jpeg';image.required=true;field(form,'Reference image',image);
const length=textInput('120','number');length.min='1';length.max='1000';length.step='1';field(form,'Output length along X (mm)',length);
const quality=select([['standard','Standard · 20 steps / 256'],['high','High · 30 steps / 384'],['ultra','Ultra · 40 steps / 512']]);field(form,'Quality',quality);quality.title='Standard: your tested settings. High and Ultra use more GPU memory.';
form.append(make('p','High / Ultra use more GPU memory.','muted small'));
const notes=make('textarea');notes.maxLength=15000;notes.style.minHeight='90px';notes.placeholder='Optional goals and notes. Hunyuan shape generation is image-driven; this text is not a general text-editing command.';field(form,'Notes / requested changes',notes);
const label=make('label',undefined,'checkrow');
label.style.cssText='display:flex;align-items:flex-start;gap:10px;cursor:pointer;width:100%;box-sizing:border-box;margin:12px 0 4px;position:relative';
const auth=make('input');auth.type='checkbox';auth.required=true;auth.id='hunyuan-local-processing-authorized';
auth.style.cssText='appearance:auto!important;display:inline-block!important;position:relative!important;width:22px!important;min-width:22px!important;max-width:22px!important;height:22px!important;min-height:22px!important;flex:0 0 22px!important;margin:1px 0 0!important;padding:0!important;opacity:1!important;pointer-events:auto!important;cursor:pointer!important;accent-color:#86d7a9;z-index:1';
auth.disabled=false;label.htmlFor=auth.id;
const authorizeText=make('span','I authorize local image and mesh processing. Imported meshes and exports still require human/slicer inspection.','small');authorizeText.style.cssText='flex:1 1 auto;min-width:0;line-height:1.45;cursor:pointer';
const AUTH_PREF='ai-studio.local-image-mesh-authorized.v1';
try{auth.checked=localStorage.getItem(AUTH_PREF)==='true';}catch(error){auth.checked=false;}
const authHint=make('p','','muted small');authHint.style.cssText='margin:4px 0 10px 32px;line-height:1.4';authHint.setAttribute('role','status');authHint.setAttribute('aria-live','polite');
function showAuthorization(){authHint.textContent=auth.checked?'On — local image/mesh processing authorized. This choice is remembered in this browser.':'Off — turn on to submit image/mesh processing. You can turn it off anytime.';}
auth.addEventListener('change',()=>{try{localStorage.setItem(AUTH_PREF,String(auth.checked));}catch(error){}showAuthorization();});
label.append(auth,authorizeText);form.append(label,authHint);showAuthorization();
const submit=make('button','Prepare image','primary');submit.type='submit';const message=make('p','','muted small');message.setAttribute('role','status');form.append(submit,message);
form.onsubmit=async e=>{e.preventDefault();if(submit.disabled)return;submit.disabled=true;try{if(!auth.checked)throw new Error('Authorize processing.');const file=image.files[0];if(!file)throw new Error('Choose an image.');if(file.size>15*1024*1024)throw new Error('Image exceeds 15 MB.');const encoded=await new Promise((resolve,reject)=>{const r=new FileReader();r.onload=()=>resolve(String(r.result).split(',')[1]);r.onerror=()=>reject(new Error('Could not read image.'));r.readAsDataURL(file);});message.textContent='Submitting...';const result=await api('/hunyuan/start',{image_base64:encoded,instructions:notes.value,length_mm:Number(length.value),quality:quality.value,authorize_processing:true});message.textContent='Queued '+result.id;location.reload();}catch(e){message.textContent=e.message;submit.disabled=false;}};
async function check(){try{const c=await api('/hunyuan/config');connection.textContent=c.online?(c.problem||('ComfyUI ready: '+c.comfy_url)):'ComfyUI is on demand - it starts when a job needs it.';}catch(e){connection.textContent=e.message;}}check();
let busy=false,activeId='',signature='',urls=[];
function clearURLs(){for(const u of urls)URL.revokeObjectURL(u);urls=[];}
async function addImage(container,id,asset,label){const item=make('div');item.style.cssText='flex:1 1 210px;min-width:0';item.append(make('div',label,'muted small'));const image=make('img');image.alt=label;image.style.cssText='width:100%;max-height:300px;object-fit:contain;background:repeating-conic-gradient(#243043 0% 25%,#182234 0% 50%) 50%/18px 18px;border-radius:8px';item.append(image);container.append(item);try{const response=await fetch('/hunyuan/asset/'+encodeURIComponent(id)+'/'+asset,{headers:{'X-Workflow-Key':KEY},cache:'no-store'});if(!response.ok)throw new Error('Not available');const blob=await response.blob();if(!item.isConnected)return;const u=URL.createObjectURL(blob);urls.push(u);image.src=u;}catch(e){item.append(make('p',e.message,'muted small'));}}
async function update(){
 const detail=$('detail'),id=detail?.querySelector('p.mono')?.textContent.trim();
 if(!id||busy||(detail.querySelector('h2')?.textContent||'').includes('Archived'))return;
 busy=true;
 try{
  const data=await api('/hunyuan/detail/'+encodeURIComponent(id));if(data.engine&&data.engine!=='hunyuan')return;
  if(!$('detail')?.querySelector('p.mono')||$('detail').querySelector('p.mono').textContent.trim()!==id)return;
  const sig=JSON.stringify([id,data.progress,data.status.state,data.status.note]);
  if(signature===sig&&$('hunyuan-checkpoint'))return;
  signature=sig;activeId=id;clearURLs();$('hunyuan-checkpoint')?.remove();
  const box=make('section',undefined,'notice');box.id='hunyuan-checkpoint';const toolbar=detail.querySelector('p.mono');toolbar.after(box);
  const state=data.status.state,p=data.progress,req=data.request;
  if(p.stage==='route_review'){
   box.append(make('h3','Checkpoint — approve image selection'),make('p','Your image selection is waiting for approval. Open the routing section, select the panels, assign MV directions, then click Apply these settings & proceed.','muted small'));
   const openApproval=make('button','Open image selection approval','primary');openApproval.type='button';box.append(openApproval);
   openApproval.onclick=()=>{const target=document.getElementById('autoroute-approval-actions')||document.getElementById('hunyuan-autorouting');if(target)target.scrollIntoView({behavior:'smooth',block:'center'});else{const note=make('p','The routing controls are still loading. Wait a moment, then try again. If they do not appear, press Ctrl+F5.','muted small');box.append(note);}};
   return;
  }
  if(String(p.stage||'').startsWith('color_')){box.append(make('h3','Color workflow'),make('p','Use the color review controls below. Original solid export is retained.','muted small'));return;}
  box.append(make('h3',state==='WAITING_IMAGE_APPROVAL'?'Checkpoint 1 — prepared image':state==='WAITING_MODEL_APPROVAL'?'Checkpoint 2 — approve the mesh':'Hunyuan image-to-3D'));
  if(state==='SUCCEEDED'){
   for(const button of detail.querySelectorAll('button')){
    if(button.textContent==='Revise this result'||button.textContent==='Revise'){button.textContent='Revisit mesh approval';button.onclick=async()=>{try{await api('/hunyuan/answer',{id,choice:'reopen'});signature='';$('refresh')?.click();update();}catch(e){alert(e.message);}};}
   }
  }
  if(state==='SUCCEEDED'){
   const downloads=make('div',undefined,'row');
   for(const [name,label] of [['source.glb','Original generated GLB'],['model.glb','Processed GLB']]){
    const button=make('button',label);button.type='button';button.onclick=async()=>{button.disabled=true;try{const response=await fetch('/hunyuan/asset/'+encodeURIComponent(id)+'/'+name,{headers:{'X-Workflow-Key':KEY}});if(!response.ok)throw new Error('File unavailable');const blob=await response.blob(),url=URL.createObjectURL(blob),link=make('a');link.href=url;link.download=id+'-'+name;document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),30000);}catch(e){alert(e.message);}finally{button.disabled=false;}};downloads.append(button);
   }box.append(downloads);
  }
  if(data.status.note)box.append(make('p',data.status.note,'small'));
  const images=make('div',undefined,'row');images.style.alignItems='start';box.append(images);
  if(state==='WAITING_IMAGE_APPROVAL'){
   addImage(images,id,'original','Original');addImage(images,id,'prepared','Prepared subject');
   const choice=select([['continue','A. Subject looks correct — continue'],['invert','B. Foreground/background reversed — invert mask'],['original','C. Use original image without background removal'],['other','D. Other — record notes and remain paused']]);field(box,'Is the subject isolated correctly?',choice);
   const goal=select([['likeness','A. Prioritize likeness'],['print','B. Print-oriented preparation (no automatic strength redesign)'],['other','C. Other — describe below']]);field(box,'Goal',goal);
   const result=select([['solid','A. Solid model — proceed to 3MF'],['articulated','B. Articulation requested — pause for joint design before export'],['other','C. Other — describe below; no automatic joint generation']]);field(box,'Result type',result);
   const more=make('textarea');more.style.minHeight='65px';more.value=p.notes||'';field(box,'Other / clarification',more);
   const button=make('button','Save answer / continue');button.type='button';box.append(button);
   button.onclick=()=>send(button,{choice:choice.value,goal:goal.value,result_type:result.value,notes:more.value});
  }else if(state==='WAITING_MODEL_APPROVAL'){
   addImage(images,id,'original','Reference');addImage(images,id,'preview.png','Generated mesh');
   const extra=make('details');extra.append(make('summary','Side and top views'));const views=make('div',undefined,'row');extra.append(views);box.append(extra);addImage(views,id,'preview_side.png','Side');addImage(views,id,'preview_top.png','Top');
   const choice=select([['export','A. Accept — export 3MF (or pause for requested joint design)'],['regenerate','B. Generate another candidate with a new seed'],['higher_detail','C. Generate again at the next detail level (more memory)'],['adjust','D. Apply size / orientation / cleanup controls below'],['other','E. Other — record notes and remain paused']]);field(box,'What should happen next?',choice);
   const controls=make('details');controls.append(make('summary','Size, orientation and optional cleanup'));box.append(controls);
   const len=textInput(p.transform?.length_mm||req.length_mm,'number');len.min='1';len.max='1000';field(controls,'Length in mm',len);
   const axes={};for(const axis of ['x','y','z']){axes[axis]=select([['0','0°'],['90','90°'],['-90','−90°'],['180','180°']]);axes[axis].value=String(p.transform?.['rotate_'+axis]||0);field(controls,'Rotate '+axis.toUpperCase(),axes[axis]);}
   const flat=make('input');flat.type='checkbox';flat.checked=!!p.transform?.flatten;const l1=make('label',undefined,'checkrow');l1.append(flat,make('span','Cut a shallow flat underside (changes geometry)'));controls.append(l1);
   const tiny=make('input');tiny.type='checkbox';tiny.checked=!!p.transform?.remove_tiny;const l2=make('label',undefined,'checkrow');l2.append(tiny,make('span','Remove tiny disconnected fragments — may also remove legitimate small details'));controls.append(l2);
   const accept=make('input');accept.type='checkbox';const l3=make('label',undefined,'checkrow');l3.append(accept,make('span','Allow export despite mesh topology warnings; not certified printable'));box.append(l3);
   const more=make('textarea');more.style.minHeight='65px';more.value=p.notes||'';field(box,'Other / requested refinement notes (saved; not free-text mesh editing)',more);
   const button=make('button','Save answer / continue');button.type='button';box.append(button);
   button.onclick=()=>send(button,{choice:choice.value,length_mm:Number(len.value),rotate_x:Number(axes.x.value),rotate_y:Number(axes.y.value),rotate_z:Number(axes.z.value),flatten:flat.checked,remove_tiny:tiny.checked,allow_mesh_warnings:accept.checked,notes:more.value});
  }else if(state==='WAITING_JOINT_DESIGN'){
   box.append(make('p','No mechanical joints have been inserted. This patch preserves the mesh and waits rather than claiming articulation works.','small'));
   const button=make('button','Continue as a solid model');button.type='button';box.append(button);button.onclick=()=>send(button,{choice:'export_solid'});
  }else if(state==='FAILED'){
   box.append(make('p','Use the existing Failure report and Retry buttons. Do not blindly resubmit a timed-out ComfyUI prompt that may still be running.','small'));
  }
  function send(button,payload){button.disabled=true;const msg=make('p','Saving...','small');box.append(msg);api('/hunyuan/answer',{id,...payload}).then(result=>{msg.textContent=result.waiting?'Saved; still waiting for your choice.':'Answer saved.';signature='';$('refresh')?.click();update();}).catch(e=>{msg.textContent=e.message;}).finally(()=>{button.disabled=false;});}
 }catch(e){/* Non-Hunyuan jobs retain their original details. */}finally{busy=false;}
}
new MutationObserver(()=>{if(!$('hunyuan-checkpoint')){signature='';update();}}).observe($('detail'),{childList:true});
setInterval(update,3000);update();window.addEventListener('beforeunload',clearURLs);
})();


/* SOLID MESH REVIEW PANEL v1 */
(() => {
'use strict';const KEY='__ACCESS_TOKEN__';let busy=false,urls=[];const skip=new Set();
const node=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;};
const currentId=root=>{const n=root&&root.querySelector(':scope > p.mono');return n?n.textContent.trim():'';};
async function api(path,body){const options={headers:{'X-Workflow-Key':KEY},cache:'no-store'};if(body){options.method='POST';options.headers['Content-Type']='application/json';options.body=JSON.stringify(body);}const r=await fetch(path,options),data=await r.json();if(!r.ok)throw Error(data.error||'Request failed');return data;}
async function scan(){
 const root=document.getElementById('detail'),id=currentId(root);
 if(busy||!root||!/^\d{8}-\d{6}-[a-zA-Z0-9]+$/.test(id)||skip.has(id)||root.querySelector('#solid-mesh-review'))return;
 busy=true;
 try{
  const data=await api('/hunyuan/detail/'+encodeURIComponent(id));
  if(!data.request||data.request.engine!=='hunyuan'){skip.add(id);return;}
  if(currentId(root)!==id)return;
  const state=data.status.state,p=data.progress||{},checks=data.mesh_checks||{},repair=checks.repair||{};
  if(String(p.stage||'').startsWith('color_'))return;
  if(!['FAILED','INTERRUPTED','WAITING_MODEL_APPROVAL','WAITING_JOINT_DESIGN'].includes(state))return;
  urls.forEach(u=>URL.revokeObjectURL(u));urls=[];
  const panel=node('section',undefined,'notice');panel.id='solid-mesh-review';panel.style.cssText='border-color:#6dba91;background:#13382b66;margin-top:14px;padding:14px';
  panel.append(node('h3','Solid mesh repair & review'));
  panel.append(node('p','Reuse this candidate’s source mesh—no Hunyuan regeneration. Repair does not create mechanical joints. Small gaps/thin features or surface colors may change.','muted small'));
  const objects=checks.objects||[];if(objects.length){const count=objects.reduce((sum,o)=>sum+(Number(o.non_manifold_edges)||0),0);panel.append(node('p','Latest check: '+count.toLocaleString()+' non-manifold edges.'))}
  if(repair.applied)panel.append(node('p','Voxel repair: '+repair.voxel_mm+' mm. Limited topology gate: '+(repair.passed_topology_checks?'passed — inspect all views before export.':'NOT PASSED — export remains blocked.')));
  const row=node('div',undefined,'row'),label=node('label','Repair voxel size (mm)'),voxel=node('input');voxel.type='number';voxel.min='.05';voxel.max='2';voxel.step='.05';voxel.value=String(p.transform&&p.transform.repair_voxel_mm||.35);voxel.style.cssText='width:95px;max-width:100%;padding:7px;color:#edf4ff;background:#10251f;border:1px solid #678d7d;border-radius:6px';label.append(voxel);row.append(label);
  const repairButton=node('button','Repair as solid & preview'),original=node('button','Preview original mesh'),exportButton=node('button','Export repaired solid');repairButton.type=original.type=exportButton.type='button';repairButton.className='primary';row.append(repairButton,original);
  const canExport=state==='WAITING_MODEL_APPROVAL'&&checks.ok&&repair.applied&&repair.passed_topology_checks;exportButton.disabled=!canExport;if(repair.applied)row.append(exportButton);
  const message=node('p',undefined,'muted small');panel.append(row,message);
  async function submit(payload){row.querySelectorAll('button,input').forEach(n=>n.disabled=true);try{await api('/hunyuan/answer',{id,...payload});message.textContent='Queued. The worker will update this job; ComfyUI is not needed for mesh repair.';}catch(e){message.textContent=e.message;row.querySelectorAll('button,input').forEach(n=>n.disabled=false);exportButton.disabled=!canExport;}}
  repairButton.onclick=()=>{const size=Number(voxel.value);if(!Number.isFinite(size)||size<.05||size>2){message.textContent='Choose a voxel size between 0.05 and 2 mm.';return;}if(!confirm('Create a repaired SOLID preview using the retained source mesh? This changes topology, may close small gaps/remove thin details, and adds NO joints. Existing previews are archived. Nothing is exported until you approve the new preview.'))return;submit({choice:'repair_solid',voxel_mm:size,confirm_solid_repair:true});};
  original.onclick=()=>{if(confirm('Restore a preview from the unmodified source mesh? Existing repair previews will be archived.'))submit({choice:'preview_original'});};
  exportButton.onclick=()=>{if(confirm('Have you inspected the repaired preview? Export this approved repaired mesh as a non-articulated solid?'))submit({choice:'export_repaired'});};
  root.append(panel);
  if(state==='WAITING_MODEL_APPROVAL'&&repair.applied){
   const views=node('div',undefined,'row');views.style.cssText='align-items:flex-start;margin-top:12px';panel.append(views);
   for(const [title,file] of [['Three-quarter','preview.png'],['Side','preview_side.png'],['Top','preview_top.png']]){
    const wrap=node('div'),image=node('img');image.alt=title+' repaired model preview';image.style.cssText='width:180px;max-width:100%;height:auto;border-radius:7px;display:block';wrap.style.cssText='flex:1 1 150px;min-width:0';wrap.append(node('p',title,'muted small'),image);views.append(wrap);
    try{const response=await fetch('/hunyuan/asset/'+encodeURIComponent(id)+'/'+file,{headers:{'X-Workflow-Key':KEY},cache:'no-store'});if(!response.ok)throw Error('Preview unavailable');const blob=await response.blob();if(!panel.isConnected)break;const url=URL.createObjectURL(blob);urls.push(url);image.src=url;}catch(e){wrap.append(node('p',e.message,'muted small'));}
   }
  }
 }catch(e){console.warn('Solid mesh review:',e.message);}finally{busy=false;}
}
setInterval(scan,1500);scan();
})();

/* FULL WIDTH JOBS LAYOUT v1 */
(() => {
'use strict';
const css=`
body.studio-wide-layout{overflow-x:hidden}
body.studio-wide-layout main{max-width:none!important;box-sizing:border-box}
body.studio-wide-layout .workspace.studio-wide-workspace{display:grid!important;grid-template-columns:minmax(280px,320px) minmax(260px,.85fr) minmax(420px,1.6fr)!important;gap:14px!important;align-items:stretch!important;width:100%;max-width:none!important;box-sizing:border-box}
.studio-left-rail{display:flex;flex-direction:column;gap:14px;min-width:0;align-self:start;grid-column:1;grid-row:1}
.studio-left-rail>[hidden]{display:none!important}
.studio-left-rail>.panel,.studio-left-rail>.studio-state-guide{margin:0!important;max-width:100%;min-width:0;box-sizing:border-box}
.studio-jobs-expanded{grid-column:2;grid-row:1;min-width:0;max-width:none!important;display:flex;flex-direction:column;min-height:calc(100vh - 225px);box-sizing:border-box;align-self:stretch}
.studio-detail-expanded{grid-column:3;grid-row:1;min-width:0;max-width:none!important;min-height:calc(100vh - 225px);box-sizing:border-box;align-self:stretch}
.studio-jobs-expanded :is(#jobs,#job-list,#jobs-list,.job-list,.jobs-list){flex:1 1 auto;min-height:300px;max-height:calc(100vh - 350px);overflow:auto;overscroll-behavior:contain}
.studio-detail-expanded pre{max-width:100%;box-sizing:border-box;overflow:auto}
.studio-detail-expanded img,.studio-detail-expanded canvas{max-width:100%;height:auto}
.studio-state-guide h2,.studio-state-guide h3{font-size:16px;margin-top:0}
.studio-state-guide{font-size:12px;overflow-wrap:anywhere}
@media(max-width:1199px) and (min-width:801px){body.studio-wide-layout .workspace.studio-wide-workspace{grid-template-columns:minmax(260px,300px) minmax(0,1fr)!important;align-items:start!important}.studio-left-rail{grid-row:1 / span 2}.studio-jobs-expanded{grid-column:2;grid-row:1;min-height:240px}.studio-jobs-expanded :is(#jobs,#job-list,#jobs-list,.job-list,.jobs-list){min-height:160px;max-height:320px}.studio-detail-expanded{grid-column:2;grid-row:2;min-height:500px}}
@media(max-width:800px){body.studio-wide-layout .workspace.studio-wide-workspace{grid-template-columns:minmax(0,1fr)!important;align-items:start!important}.studio-left-rail,.studio-jobs-expanded,.studio-detail-expanded{grid-column:1;grid-row:auto;min-height:0}.studio-jobs-expanded :is(#jobs,#job-list,#jobs-list,.job-list,.jobs-list){min-height:180px;max-height:340px}}
`;
if(!document.getElementById('studio-wide-layout-css')){const style=document.createElement('style');style.id='studio-wide-layout-css';style.textContent=css;document.head.append(style);}
function headingPanel(text){const heading=Array.from(document.querySelectorAll('h2,h3,summary')).find(n=>text.test(n.textContent.trim()));return heading?(heading.closest('.panel')||heading.closest('section,aside,article')):null;}
let attempts=0;
function arrange(){
 const workspace=document.querySelector('.workspace'),hy=document.getElementById('hunyuan-create'),legacy=document.getElementById('create-panel'),detail=document.getElementById('detail');
 if(!workspace||!hy||!detail)return false;
 if(workspace.dataset.studioWideLayout==='1')return true;
 const selected=detail.closest('.panel')||detail;
 const list=document.getElementById('job-list')||document.getElementById('jobs-list')||document.getElementById('jobs');
 let jobs=(list?.closest('.panel'))||document.getElementById('jobs-panel')||headingPanel(/^jobs(?:\s|$|\b)/i);
 if(!jobs||jobs===selected||jobs===hy||jobs===legacy||selected.contains(jobs)){console.warn('Wide layout: could not identify separate Jobs and Selected job panels. Existing layout retained.');return false;}
 let guide=document.getElementById('state-guide')||document.getElementById('state-guide-panel')||headingPanel(/^state guide\b/i);
 if(guide){const container=guide.closest('.panel');if(container&&![jobs,selected,hy,legacy].includes(container))guide=container;}
 if(guide===jobs||guide===selected||guide===hy||guide===legacy||guide===workspace)guide=null;
 const rail=document.createElement('aside');rail.id='studio-left-rail';rail.className='studio-left-rail';rail.setAttribute('aria-label','Create model and state guide');
 // Move the live elements, preserving event listeners, file inputs, selected job and form contents.
 workspace.append(rail);rail.append(hy);if(legacy)rail.append(legacy);
 if(guide){guide.classList.add('studio-state-guide');rail.append(guide);}else console.warn('State guide panel was not found; it was not removed.');
 jobs.classList.add('studio-jobs-expanded');selected.classList.add('studio-detail-expanded');workspace.append(jobs,selected);
 for(const child of Array.from(workspace.children)){if(child===rail||child===jobs||child===selected||['SCRIPT','STYLE'].includes(child.tagName))continue;if(!child.children.length&&!child.textContent.trim())child.hidden=true;}
 for(let parent=workspace.parentElement;parent&&parent!==document.body;parent=parent.parentElement){parent.style.maxWidth='none';parent.style.width='auto';}
 workspace.classList.add('studio-wide-workspace');workspace.dataset.studioWideLayout='1';document.body.classList.add('studio-wide-layout');return true;
}
if(!arrange()){const retry=setInterval(()=>{attempts++;if(arrange()||attempts>=30)clearInterval(retry);},150);}
})();
/* END FULL WIDTH JOBS LAYOUT v1 */

/* STACKED WIDE JOB PANELS v1 */
(() => {
'use strict';
const id='studio-stacked-job-panels-css';let style=document.getElementById(id);if(!style){style=document.createElement('style');style.id=id;document.head.append(style);}
style.textContent=`
@media(min-width:801px){
body.studio-wide-layout .workspace.studio-wide-workspace{grid-template-columns:minmax(270px,310px) minmax(0,1fr)!important;grid-template-rows:auto 1fr!important;gap:14px!important;align-items:start!important}
body.studio-wide-layout .studio-left-rail{grid-column:1!important;grid-row:1 / span 2!important;align-self:start!important;min-width:0}
body.studio-wide-layout .studio-jobs-expanded{grid-column:2!important;grid-row:1!important;width:100%!important;max-width:none!important;min-width:0!important;min-height:190px!important;align-self:stretch!important;box-sizing:border-box}
body.studio-wide-layout .studio-detail-expanded{grid-column:2!important;grid-row:2!important;width:100%!important;max-width:none!important;min-width:0!important;min-height:560px!important;align-self:stretch!important;box-sizing:border-box}
body.studio-wide-layout .studio-jobs-expanded :is(#jobs,#job-list,#jobs-list,.job-list,.jobs-list){min-height:100px!important;max-height:290px!important;overflow:auto!important;grid-template-columns:minmax(0,1fr)!important;box-sizing:border-box}
body.studio-wide-layout .studio-jobs-expanded :is(.job,.job-card,.job-row){width:100%;max-width:none;box-sizing:border-box}
}
@media(min-width:1600px){body.studio-wide-layout .workspace.studio-wide-workspace{grid-template-columns:minmax(290px,330px) minmax(0,1fr)!important}}
@media(max-width:800px){
body.studio-wide-layout .workspace.studio-wide-workspace{grid-template-columns:minmax(0,1fr)!important;grid-template-rows:auto auto auto!important}
body.studio-wide-layout .studio-left-rail{grid-column:1!important;grid-row:1!important}
body.studio-wide-layout .studio-jobs-expanded{grid-column:1!important;grid-row:2!important;min-height:160px!important;width:100%!important;box-sizing:border-box}
body.studio-wide-layout .studio-detail-expanded{grid-column:1!important;grid-row:3!important;min-height:350px!important;width:100%!important;box-sizing:border-box}
body.studio-wide-layout .studio-jobs-expanded :is(#jobs,#job-list,#jobs-list,.job-list,.jobs-list){min-height:100px!important;max-height:260px!important;grid-template-columns:minmax(0,1fr)!important}
}
`;
})();
/* END STACKED WIDE JOB PANELS v1 */

/* STANDALONE GUIDED JOB UI v2 */
(() => {
'use strict';const KEY='__ACCESS_TOKEN__';let busy=false,ctx=null,lastId='';const expanded=new Map(),disabled=new WeakMap();
const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;};
const selected=()=>document.getElementById('detail')?.querySelector(':scope > p.mono')?.textContent.trim()||'';
const style=el('style');style.textContent=`#guided-current-stage{position:sticky;top:8px;z-index:30;margin:8px 0 12px;padding:12px;background:#143b29;border:1px solid #94cca4;border-radius:8px;box-shadow:0 3px 12px #0005;min-width:0}#guided-current-stage p{margin:5px 0 0;font-size:12px}.guided-header-actions{display:inline-flex;gap:4px;flex-wrap:wrap;margin-left:8px}.guided-header-actions button{font-size:11px;padding:4px 7px}.guided-done{margin:8px 0!important;border:1px solid #4d7158;border-radius:7px;min-width:0}.guided-done>summary{padding:8px 10px;font-size:12px;cursor:pointer}.guided-done>section{margin:0!important}#guided-sidebar-dock[hidden]{display:none!important}#guided-sidebar-dock{min-width:0;margin-top:12px;padding:10px;border:1px solid #81b58e;border-radius:8px;background:#122d23}#guided-sidebar-dock pre{max-height:55vh;overflow:auto;white-space:pre-wrap;overflow-wrap:anywhere;font-size:11px;line-height:1.45;background:#0b1d17;padding:8px;user-select:text}.guided-doc-head{display:flex;justify-content:space-between;align-items:center;gap:8px}.guided-doc-head h3{font-size:13px;margin:0}#guided-sidebar-dock button{font-size:11px;padding:4px 7px}.guided-color-stages{display:flex;flex-wrap:wrap;gap:5px;margin-top:8px}.guided-color-stages span{font-size:11px;padding:4px 6px;border:1px solid #507359;border-radius:6px}.guided-color-stages .current{background:#356e49;border-color:#b4e1bb}`;document.head.append(style);
async function get(path){const response=await fetch(path,{headers:{'X-Workflow-Key':KEY},cache:'no-store'});if(!response.ok)throw Error('HTTP '+response.status);return response.json();}
function dock(){let target=document.getElementById('guided-sidebar-dock');if(!target){target=el('section');target.id='guided-sidebar-dock';target.hidden=true;}const h=Array.from(document.querySelectorAll('h2,h3,summary')).find(n=>/^state guide\b/i.test(n.textContent.trim()));const guide=document.querySelector('.studio-state-guide')||document.getElementById('state-guide')||h?.closest('.panel')||h?.closest('section,aside');if(guide&&target.previousElementSibling!==guide)guide.after(target);else if(!target.isConnected){const rail=document.getElementById('studio-left-rail');if(rail)rail.append(target);else document.getElementById('hunyuan-create')?.after(target);}return target;}
async function copy(text,status){try{try{await navigator.clipboard.writeText(text);}catch(e){const node=el('textarea');node.value=text;node.style.cssText='position:fixed;left:-10000px';document.body.append(node);node.select();const ok=document.execCommand('copy');node.remove();if(!ok)throw Error('Clipboard unavailable');}status.textContent='Copied. Paste the text into chat.';}catch(e){status.textContent=e.message;}}
function show(title,text){const target=dock();target.replaceChildren();target.hidden=false;const header=el('div',undefined,'guided-doc-head'),close=el('button','Close ×');close.type='button';header.append(el('h3',title),close);const body=el('pre',text);body.tabIndex=0;const row=el('div',undefined,'row'),cp=el('button','Copy'),select=el('button','Select all'),status=el('p','','muted small');cp.type=select.type='button';row.append(cp,select);target.append(header,el('p','Job: '+selected(),'muted small'),row,body,status);close.onclick=()=>{target.replaceChildren();target.hidden=true;};cp.onclick=()=>copy(body.textContent,status);select.onclick=()=>{const range=document.createRange();range.selectNodeContents(body);const selection=window.getSelection();selection.removeAllRanges();selection.addRange(range);body.focus();};target.scrollIntoView({behavior:'smooth',block:'start'});return body;}
async function log(title,path){const id=selected(),body=show(title,'Loading…');try{const r=await fetch(path,{headers:{'X-Workflow-Key':KEY},cache:'no-store'});if(!r.ok)throw Error('Report unavailable: HTTP '+r.status);let text=await r.text();try{const parsed=JSON.parse(text);text=typeof parsed==='string'?parsed:JSON.stringify(parsed,null,2);}catch(e){}if(body.isConnected&&selected()===id)body.textContent=text;}catch(e){if(body.isConnected)body.textContent=e.message;}}
function stage(job,p){const state=job.state||'',phase=String(p.stage||''),report=job.checks?.color_workflow||job.checks?.reference_textures||{},color=/color|texture/.test(phase)||/color|texture/i.test(job.note||'');let title=state,note=job.note||'',index=-1;
 if(state==='FAILED'){title='Stopped — needs attention';note='Open the failure report. Partial files are retained but are not a completed export.';}
 else if(state==='INTERRUPTED'){title=job.cancelled?'Canceled':'Interrupted';}
 else if(state==='QUEUED')title='Queued';
 else if(color){if(phase==='color_prepare'){title='Color — prepare references';index=0;}else if(phase==='color_mask_approval'){title='Color — review foreground masks';index=0;}else if(phase==='color_mask_approved'){title='Color — align references';index=1;}else if(phase==='color_preview'){title='Color — build texture preview';index=2;}else if(phase==='color_cancelling'){title='Color — cancelling';index=-1;}else if(/approv|preview_ready/.test(phase+' '+String(report.phase||''))){title='Color — review';index=3;}else if(/export/.test(phase)){title='Color — export';index=4;}else if(/align/.test(phase+' '+note)){title='Color — alignment';index=1;}else if(/combine|blend/.test(phase+' '+note)){title='Color — combining views';index=2;}else if(/transfer|bake/.test(phase+' '+note)){title='Color — texture transfer';index=1;}else title=state==='SUCCEEDED'?'Color output completed':'Color — processing';}
 else if(state==='WAITING_IMAGE_APPROVAL'){title=phase==='route_review'?'Image selection — approval needed':'Prepared images — approval needed';}
 else if(phase==='prepare'||phase==='route_analyze')title='Image analysis / preparation';
 else if(phase==='generate')title='Model generation';
 else if(phase==='reprocess')title='Model repair / preview';
 else if(state==='WAITING_MODEL_APPROVAL')title='Model review — approval needed';
 else if(state==='WAITING_JOINT_DESIGN')title='Joint design — waiting';
 else if(phase==='export')title='Model export';
 else if(state==='SUCCEEDED')title='Model completed';
 return{title,note,index,color,legacy:report.method==='photo_projection_to_filament_palette',phase,state};}
function lockPanel(panel,lock){for(const n of panel.querySelectorAll('input,select,textarea,button')){if(n.tagName==='BUTTON'&&/copy|download|preview|three-quarter|^side$|^top$|original generated glb|processed glb|revisit mesh approval/i.test(n.textContent.trim()))continue;if(lock){if(!disabled.has(n))disabled.set(n,n.disabled);n.disabled=true;}else if(disabled.has(n)){n.disabled=disabled.get(n);disabled.delete(n);}}}
function collapse(root,node,key,title,done){if(!node||node===root)return;let wrapper=node.closest('details.guided-done');if(done){if(!wrapper){wrapper=el('details',undefined,'guided-done');node.before(wrapper);wrapper.append(el('summary',title+' — completed · expand'),node);const memory=ctx.job.id+':'+key;wrapper.open=expanded.get(memory)||false;wrapper.addEventListener('toggle',()=>expanded.set(memory,wrapper.open));}lockPanel(node,true);}else if(wrapper){lockPanel(node,false);wrapper.before(node);wrapper.remove();}}
function decorate(){if(!ctx)return;const root=document.getElementById('detail');if(!root||selected()!==ctx.job.id)return;const title=root.querySelector('h2'),header=title?.parentElement;if(!root.querySelector('#guided-header-actions')){const actions=el('div',undefined,'guided-header-actions');actions.id='guided-header-actions';for(const [text,kind]of [['Your request','request'],['Full job status','status']]){const b=el('button',text);b.type='button';b.onclick=()=>{if(kind==='request')show('Your request',ctx.details.request?JSON.stringify(ctx.details.request,null,2):(ctx.job.instructions||'(No text request supplied.)'));else show('Full job status',JSON.stringify({job:ctx.job,progress:ctx.p},null,2));};actions.append(b);}if(header&&header!==root){const last=header.lastElementChild;if(last&&last!==title)header.insertBefore(actions,last);else header.append(actions);}else title?.after(actions);}
 for(const b of root.querySelectorAll('.job-info-tabs button'))if(/^(your request|full job status)$/i.test(b.textContent.trim()))b.hidden=true;
 for(const item of root.querySelectorAll('details')){const text=item.querySelector(':scope > summary')?.textContent.trim()||'';if(/^(your request|full job status)$/i.test(text)){item.hidden=true;const panel=item.closest('.job-info-panel');if(panel)panel.hidden=true;}}
 let card=root.querySelector('#guided-current-stage');if(!card){card=el('section');card.id='guided-current-stage';card.setAttribute('aria-live','polite');}const anchor=root.querySelector(':scope > #job-stage-note')||root.querySelector('#job-cancel-controls')||root.querySelector(':scope > p.mono');/* JOB_AREA_LAYOUT_V1: sit under the stage bar when the layout script provides it */if(anchor&&card.previousElementSibling!==anchor)anchor.after(card);const info=stage(ctx.job,ctx.p),signature=JSON.stringify(info);if(card.dataset.signature!==signature){card.dataset.signature=signature;card.replaceChildren(el('strong','Current stage: '+info.title),el('p',info.note),el('p','Reported state: '+info.state+(info.phase?' · '+info.phase:''),'muted small'));if(info.color){const steps=el('div',undefined,'guided-color-stages');['Review references','Align references','Build texture preview','Review match','Texture-master export'].forEach((s,i)=>{const chip=el('span',s);if(i===info.index)chip.className='current';steps.append(chip);});card.append(steps);if(info.legacy)card.append(el('p','This result uses the legacy palette projector. This UI update does not install the replacement reference-texture engine.','small'));}}
 const early=['prepare','route_analyze','route_review','image_approval'].includes(ctx.p.stage);collapse(root,root.querySelector('#hunyuan-autorouting'),'images','Image selection & routing',!!ctx.p.stage&&!early);collapse(root,root.querySelector('#hunyuan-checkpoint'),'mesh','Model preview & approval',info.color||ctx.job.state==='SUCCEEDED');collapse(root,root.querySelector('#solid-mesh-review'),'repair','Mesh repair & checks',info.color||ctx.job.state==='SUCCEEDED');dock();}
const routes={'failure report':id=>'/report/'+id,'blender log':id=>'/text/'+id+'/blender.log','last blender log':id=>'/text/'+id+'/blender.log','checks':id=>'/text/'+id+'/checks.json','last checks':id=>'/text/'+id+'/checks.json','script':id=>'/text/'+id+'/model.py','last script':id=>'/text/'+id+'/model.py','construction plan':id=>'/text/'+id+'/quality_plan.json'};
document.addEventListener('click',event=>{const b=event.target.closest('button');if(!b||!document.getElementById('detail')?.contains(b)||!selected())return;const label=b.textContent.trim().toLowerCase();if(routes[label]){event.preventDefault();event.stopImmediatePropagation();log(b.textContent.trim(),routes[label](encodeURIComponent(selected())));}else if(/^(open |view )?(error log|full error|error report)$/.test(label)){event.preventDefault();event.stopImmediatePropagation();log('Failure report','/report/'+encodeURIComponent(selected()));}else if(label==='diagnostics files'){event.preventDefault();event.stopImmediatePropagation();show('Diagnostics files','Choose a report below.');const row=el('div',undefined,'row');for(const name of ['Failure report','Blender log','Checks']){const button=el('button',name);button.type='button';button.onclick=()=>log(name,routes[name.toLowerCase()](encodeURIComponent(selected())));row.append(button);}dock().append(row);}},true);
function closeLogModals(){for(const modal of document.querySelectorAll('dialog[open]')){const title=modal.querySelector('h1,h2,h3,[id$="title"]')?.textContent||'',node=modal.querySelector('pre,textarea'),text=node?.value||node?.textContent||'';if(/error|failure|blender log|diagnostic/i.test(title)&&text.trim()&&!/^loading[.…]/i.test(text.trim())){show(title,text);modal.close();}}}
let queued=false;new MutationObserver(records=>{if(!records.some(r=>r.target.closest?.('dialog')||Array.from(r.addedNodes||[]).some(n=>n.nodeType===1&&n.matches?.('dialog'))))return;if(!queued){queued=true;setTimeout(()=>{queued=false;closeLogModals();},0);}}).observe(document.body,{subtree:true,childList:true,attributes:true,attributeFilter:['open']});
async function tick(){if(busy)return;const id=selected();if(!id)return;busy=true;try{const jobs=await get('/jobs'),job=Array.isArray(jobs)?jobs.find(j=>j.id===id):null;if(!job||selected()!==id)return;let details={};try{details=await get('/hunyuan/detail/'+encodeURIComponent(id));}catch(e){}if(selected()!==id)return;if(lastId&&lastId!==id){const n=document.getElementById('guided-sidebar-dock');if(n){n.hidden=true;n.replaceChildren();}}lastId=id;ctx={job,details,p:details.progress||{}};decorate();closeLogModals();}catch(e){console.warn('Guided job UI:',e.message);}finally{busy=false;}}
setInterval(tick,1500);tick();
})();
/* END STANDALONE GUIDED JOB UI v2 */

/* JOB ACTION ROW REFINEMENT v1 */
(() => {
'use strict';
const normalized=n=>(n?.textContent||n?.value||'').replace(/\s+/g,' ').trim().toLowerCase();
const controls=root=>Array.from(root.querySelectorAll('button,a,input[type="button"],input[type="submit"]'));
const named=(root,pattern)=>controls(root).find(n=>pattern.test(normalized(n)));
const create=(tag,cls)=>{const n=document.createElement(tag);if(cls)n.className=cls;return n;};
const style=create('style');style.textContent=`
#guided-header-actions,.job-top-information-actions{display:inline-flex;align-items:center;gap:4px;flex-wrap:wrap;margin-left:8px}
#guided-header-actions button,#guided-header-actions a,.job-top-information-actions button,.job-top-information-actions a{font-size:11px;padding:4px 7px}
.job-retry-archive-row{display:flex!important;align-items:center;flex-wrap:wrap;gap:8px;width:100%;box-sizing:border-box;margin:8px 0}
.job-retry-archive-row>.job-archive-direct{margin-left:auto!important;display:inline-flex!important;width:auto!important;flex:0 0 auto!important;align-items:center;visibility:visible!important;position:static!important;opacity:1!important}
.job-retry-archive-row>.job-archive-direct[hidden]{display:none!important}
`;document.head.append(style);
let scheduled=false,stopped=false;const autoOpened=new WeakSet();
function infoButtons(root){const diagnostics=named(root,/^diagnostics files$/);if(!diagnostics)return;let group=root.querySelector('#guided-header-actions,.job-top-information-actions');if(!group){const title=Array.from(root.querySelectorAll('h2,h3')).find(n=>/^selected job\b/i.test(n.textContent.trim()))||root.querySelector('h2');if(!title)return;group=create('div','job-top-information-actions');const header=title.parentElement;if(header&&header!==root){const last=header.lastElementChild;if(last&&last!==title)header.insertBefore(group,last);else header.append(group);}else title.after(group);for(const pattern of [/^your request$/,/^full job status$/]){const button=named(root,pattern);if(button){button.hidden=false;group.append(button);}}}
 if(diagnostics.parentElement!==group)group.append(diagnostics);diagnostics.hidden=false;
}
const finished=new Set(['SUCCEEDED','FAILED','INTERRUPTED','CANCELED','CANCELLED','COMPLETED']);let jobStates=new Map();
function archiveButton(root){const more=named(root,/^more(?: actions)?(?:\s*[▾▼⋮…])?$/);const lookup=()=>{let button=controls(root).find(n=>!n.classList.contains('job-archive-direct')&&/^archive(?: (?:this )?job)?$/.test(normalized(n)));if(!button&&more){const menu=document.getElementById(more.getAttribute('aria-controls')||'');if(menu)button=controls(menu).find(n=>/^archive(?: (?:this )?job)?$/.test(normalized(n)));}return button;};let button=lookup();if(button)return button;
 if(more&&!autoOpened.has(more)&&(more.getAttribute('aria-haspopup')==='menu'||more.hasAttribute('aria-expanded'))){autoOpened.add(more);const wasOpen=more.getAttribute('aria-expanded')==='true';if(!wasOpen){more.click();button=lookup();if(more.getAttribute('aria-expanded')==='true')more.click();}else button=lookup();}
 return button;
}
function makeActionRow(root){const jobId=root.querySelector(':scope > p.mono')?.textContent.trim()||'';const state=jobStates.get(jobId);if(!state||!finished.has(state)){const existing=root.querySelector('.job-archive-direct');if(existing)existing.hidden=true;return;}
 const retry=named(root,/^retry same test$/),archive=archiveButton(root);if(!retry||!archive)return;
 let row=retry.closest('.job-retry-archive-row');if(!row){const parent=retry.parentElement;const isRow=parent&&parent!==root&&parent.tagName!=='DETAILS'&&parent.getAttribute('role')!=='menu'&&!parent.closest('details')&&(parent.classList.contains('row')||parent.classList.contains('actions')||parent.classList.contains('job-actions'));
  if(isRow){row=parent;row.classList.add('job-retry-archive-row');}else{row=create('div','job-retry-archive-row');const menu=retry.closest('details');if(menu)menu.before(row);else retry.before(row);row.append(retry);}
 }
 let direct=row.querySelector('.job-archive-direct');if(!direct){direct=create('button','job-archive-direct');direct.type='button';direct.textContent='Archive job';row.append(direct);}direct.hidden=false;direct.disabled=archive.disabled||false;direct.setAttribute('title','Archive this job');
 // Forward to the original native control, retaining its confirmation and any delegated menu handler.
 direct.onclick=()=>{if(!archive.disabled&&archive.isConnected)archive.click();};archive.hidden=true;
 for(const details of root.querySelectorAll('details')){const summary=details.querySelector(':scope > summary');if(summary&&/^more(?: actions)?\b/i.test(summary.textContent.trim())){const remaining=controls(details).filter(n=>!n.hidden&&getComputedStyle(n).display!=='none');if(!remaining.length)details.hidden=true;}}
}
function apply(){const root=document.getElementById('detail');if(!root)return;infoButtons(root);makeActionRow(root);}
function schedule(){if(scheduled||stopped)return;scheduled=true;requestAnimationFrame(()=>{scheduled=false;observer.disconnect();try{apply();}catch(e){console.warn('Job action layout:',e);}finally{observer.observe(document.body,{childList:true,subtree:true});}});}
const observer=new MutationObserver(schedule);observer.observe(document.body,{childList:true,subtree:true});let polling=false;async function poll(){if(polling)return;polling=true;try{const r=await fetch('/jobs',{headers:{'X-Workflow-Key':'__ACCESS_TOKEN__'},cache:'no-store'});if(r.ok){const jobs=await r.json();if(Array.isArray(jobs)){jobStates=new Map(jobs.map(j=>[j.id,j.state]));schedule();}}}catch(e){}finally{polling=false;}}
setInterval(poll,1500);setInterval(schedule,1200);poll();schedule();
})();
/* END JOB ACTION ROW REFINEMENT v1 */
