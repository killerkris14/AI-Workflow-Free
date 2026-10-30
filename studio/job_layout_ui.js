/* STAGE_UNIFY_V1 (AI UI Unifi 0.015: one fixed 12-stage block, stage bar + task bar, updated in place) + JOB_AREA_LAYOUT_V1 + JOB_PROGRESS_BAR_V1 + CHECKPOINT_LAYOUT_V1 + GEOMETRY_CHECK_V1 (AI Modeling Studio 0.009): newest information first, color steps in the stage bar,
   live 5-line task log, finished-stage boxes collapsed. Other scripts' boxes are only re-ordered or hidden,
   never moved into new containers, so their own refresh logic keeps finding them. */
(()=>{'use strict';
const KEY='__ACCESS_TOKEN__';
const $=id=>document.getElementById(id);
const COLOR_STEPS=['Color: masks','Color: alignment','Color: texture preview','Color: review','Color: export'];
const PHASE_STEP={preparing:0,mask_review:0,mask_approved:1,aligning:1,previewing:2,preview_review:3,exporting:4,complete:5};
const style=document.createElement('style');
style.textContent='#job-live-console{margin:10px 0;border:1px solid #33506f;border-radius:8px;background:#0b1320;padding:6px 10px}'+
 '#job-live-console .head{font-size:12px;color:#9fb3c8;margin-bottom:4px}'+
 '#job-live-console pre{margin:0;padding:3px 0;background:none;border-radius:0;font:12px/17px Consolas,"Courier New",monospace;white-space:pre-wrap;word-break:break-all;color:#d7e3f4;user-select:text;height:85px;min-height:85px;max-height:85px;overflow:hidden}'+
 '.layout-hidden{display:none!important}#layout-earlier-toggle{margin:12px 0}'+
 '#studio-stage-block{margin:8px 0 10px;padding:10px 12px;border:1px solid #4d7158;border-radius:8px;background:#0f2219;contain:layout}'+
 '#studio-stage-block .ssb-title{font-size:14px;font-weight:700;color:#e8f3ec;height:20px;line-height:20px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}'+
 '#studio-stage-chips{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:4px;margin:8px 0}'+
 '#studio-stage-chips .chip{height:34px;box-sizing:border-box;padding:2px 5px;border:1px solid #3d5a4a;border-radius:5px;font-size:11px;line-height:14px;color:#8fa79a;background:#13261d;overflow:hidden}'+
 '#studio-stage-chips .chip.past{color:#cfe9d8;background:#1d4a31;border-color:#3f8a5c}'+
 '#studio-stage-chips .chip.current{color:#fff;background:#1f8f4a;border-color:#7be3a3;font-weight:700}'+
 '#studio-stage-chips .chip.current.waiting{background:#8a6a12;border-color:#ffd17c}#studio-stage-chips .chip.current.stopped{background:#8a2a35;border-color:#ff91a2}'+
 '#studio-stage-block .ssb-bar{margin:6px 0 0}#studio-stage-block .label{font-size:12px;color:#c9d6e5;height:17px;line-height:17px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}'+
 '#studio-stage-block .track{height:16px;border:1px solid #5b6b7d;border-radius:3px;background:#e6e6e6;overflow:hidden;position:relative}'+
 '#studio-stage-block .fill{height:100%;width:0;background:repeating-linear-gradient(90deg,#06b025 0 9px,#2fd14e 9px 11px);transition:width .6s}#studio-stage-block .ssb-task .fill{transition:width .4s linear}'+
 '#studio-stage-block .ssb-stage .fill{background:repeating-linear-gradient(90deg,#1c6fd1 0 9px,#3f8ff0 9px 11px)}'+
 '#studio-stage-block .ssb-bar.indeterminate .fill{width:28%!important;position:absolute;animation:job-marquee 1.6s linear infinite}'+
 '#studio-stage-block .ssb-bar.idle .fill{width:0!important}'+
 '#guided-current-stage{height:84px;box-sizing:border-box;overflow:hidden}#guided-current-stage p{display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}'+
 '#job-live-console pre{height:85px}'+
 '#job-progress{margin:6px 0 10px}#job-progress .label{font-size:12px;color:#c9d6e5;margin-bottom:3px}'+
 '#job-progress .track{height:18px;border:1px solid #5b6b7d;border-radius:3px;background:#e6e6e6;overflow:hidden;position:relative}'+
 '#job-progress .fill{height:100%;background:repeating-linear-gradient(90deg,#06b025 0 9px,#2fd14e 9px 11px);transition:width .6s}'+
 '#job-progress.indeterminate .fill{width:28%!important;position:absolute;animation:job-marquee 1.6s linear infinite}'+
 '@keyframes job-marquee{from{left:-28%}to{left:100%}}'+
 '.layout-approve{display:block;width:100%;margin:14px 0;padding:16px 20px;font-size:18px;font-weight:700;color:#fff;background:#1f8f4a;border:2px solid #49d17f;border-radius:10px;cursor:pointer}'+
 '.layout-approve:hover{background:#26a957}.layout-orig-hidden{display:none!important}'+
 '#hunyuan-checkpoint img{max-height:440px!important}'+
 '#layout-ckpt-refs{margin:10px 0}#layout-ckpt-refs .row{display:flex;gap:10px;flex-wrap:wrap;align-items:flex-start}#layout-ckpt-refs figure{margin:0;flex:1 1 160px;min-width:0}#layout-ckpt-refs img{width:100%;max-height:260px;object-fit:contain;background:#0b1320;border-radius:7px}#layout-ckpt-refs figcaption{font-size:12px;color:#9fb3c8}';
document.head.append(style);
let expanded=false,lastJob='',scheduled=false,fetching=false;
const direct=(root,sel)=>root.querySelector(':scope > '+sel);
function jobId(root){return direct(root,'p.mono')?.textContent.trim()||'';}
function consoleBox(){
 let box=$('job-live-console');
 if(!box){box=document.createElement('section');box.id='job-live-console';const head=document.createElement('div');head.className='head';head.textContent='Live task log (last 5 lines)';const pre=document.createElement('pre');pre.textContent='Waiting for log...';box.append(head,pre);}
 return box;
}
function progressBox(){
 let box=$('job-progress');
 if(!box){box=document.createElement('section');box.id='job-progress';const label=document.createElement('div');label.className='label';const track=document.createElement('div');track.className='track';const fill=document.createElement('div');fill.className='fill';track.append(fill);box.append(label,track);box.hidden=true;}
 return box;
}
function updateProgress(data){
 const box=$('job-progress');if(!box)return;
 const chips=Array.from(document.querySelectorAll('#detail div.steps > .step'));const at=chips.findIndex(c=>c.classList.contains('current'));
 const step=at>=0?'Step '+(at+1)+' of '+chips.length+' \u2014 '+chips[at].textContent.replace(/^\d+\.\s*/,''):'';
 if(!data.running){box.hidden=true;return;}
 box.hidden=false;const pct=data.progress?data.progress.percent:null;
 box.classList.toggle('indeterminate',pct===null);box.querySelector('.fill').style.width=(pct===null?28:Math.max(2,pct))+'%';
 box.querySelector('.label').textContent=(step||'Working')+(pct===null?' \u00b7 working (no measurable progress reported by this step)':' \u00b7 '+pct.toFixed(0)+'% of the current task');
}
function checkpointKind(cp){const h=cp&&cp.querySelector('h3');return h?h.textContent:'';}
function approveProxy(cp){
 const original=cp&&Array.from(cp.querySelectorAll('button')).find(b=>/^Save answer \/ continue$/.test(b.textContent.trim())||b.dataset.layoutOriginal==='1');
 let proxy=$('layout-approve');
 if(!original){if(proxy)proxy.remove();return null;}
 original.dataset.layoutOriginal='1';original.classList.add('layout-orig-hidden');
 if(!proxy){proxy=document.createElement('button');proxy.type='button';proxy.id='layout-approve';proxy.className='layout-approve';
  proxy.onclick=()=>{const o=$('detail')?.querySelector('#hunyuan-checkpoint button[data-layout-original="1"]');if(o)o.click();};}
 proxy.textContent=/^Checkpoint 2/.test(checkpointKind(cp))?'\u2714 Approve mesh & continue':'\u2714 Approve & continue';
 return proxy;
}
const geoCache={};
function geometryEvidence(cp,id){
 let box=$('layout-geometry-check');
 if(!/^Checkpoint 2/.test(checkpointKind(cp))){if(box)box.remove();return null;}
 if(!box){box=document.createElement('section');box.id='layout-geometry-check';box.style.cssText='margin:10px 0;padding:10px;border:1px solid #6a8aaa;border-radius:8px';}
 if(box.dataset.job===id&&box.dataset.loaded&&box._checkpoint===cp)return box;
 box.dataset.job=id;box._checkpoint=cp;delete box.dataset.loaded;
 fetch('/hunyuan-color/geometry/'+encodeURIComponent(id),{headers:{'X-Workflow-Key':KEY},cache:'no-store'}).then(r=>r.json()).then(g=>{
  if(box.dataset.job!==id)return;box.dataset.loaded='1';box.replaceChildren();
  const tries=g.tries||[];const h=document.createElement('h4');
  if(!tries.length){h.textContent='Geometry check: not run for this mesh';box.append(h);return;}
  const shown=tries.find(t=>t.candidate===g.shown_candidate)||tries[tries.length-1];
  h.textContent=shown.error?'\u26a0 Geometry check could not run \u2014 inspect the mesh yourself':shown.passed?'\u2714 Geometry check passed against every reference view (try '+(tries.indexOf(shown)+1)+' of '+tries.length+')':'\u26a0 No try passed the geometry check \u2014 showing the best of '+tries.length+'. Check the yellow areas.';
  h.style.color=shown.passed?'#81e3a5':'#ffcf6e';box.append(h);
  const table=document.createElement('table');table.style.cssText='width:100%;font-size:12px;border-collapse:collapse;margin:6px 0';
  table.innerHTML='<tr><th align=left>Try</th><th align=left>Result</th><th align=left>Score</th><th align=left>Problems found</th><th align=left>Fix used for the next try</th></tr>';
  tries.forEach((t,i)=>{const tr=document.createElement('tr');const cells=['Try '+(i+1)+(t.candidate===g.shown_candidate?' (shown)':''),t.error?'check failed':t.passed?'passed':'failed',t.score>=0?Number(t.score).toFixed(2):'\u2014',(t.reasons||[]).map(r=>(r.code==='misplaced_part'?'misplaced part (pictures disagree)':r.code.replace('_',' '))+(r.view?' in '+r.view:'')+' ('+r.value+(r.code==='poor_fit'?'':'%')+(r.code==='misplaced_part'&&r.missing!=null?' extra, '+r.missing+'% missing':'')+')').join('; ')||'\u2014',(t.fix_for_next_try||[]).join('; ')||'\u2014'];cells.forEach(c=>{const td=document.createElement('td');td.textContent=c;td.style.cssText='padding:3px 6px;border-top:1px solid #33506f;vertical-align:top';tr.append(td);});table.append(tr);});
  box.append(table);
  const legend=document.createElement('p');legend.className='small';legend.textContent='Mesh vs each reference: green = agree, blue = mesh only, red = reference only, YELLOW = far from the outline. Extra only = an extra part (e.g. a doubled tail); extra AND missing in one view = a part in a different place than drawn.';box.append(legend);
  const row=document.createElement('div');row.style.cssText='display:flex;gap:10px;flex-wrap:wrap';box.append(row);
  const views=(g.check&&g.check.views)||{};
  Object.entries(views).forEach(([v,m])=>{const fig=document.createElement('figure');fig.style.cssText='margin:0;flex:1 1 160px;min-width:0';const img=document.createElement('img');img.style.cssText='width:100%;max-height:240px;object-fit:contain;background:#0b1320;border-radius:6px';const cap=document.createElement('figcaption');cap.className='small';cap.textContent=v+': fit '+m.iou+', far extra '+m.far_extra_percent+'%, far missing '+m.far_missing_percent+'%';fig.append(img,cap);row.append(fig);
   fetch('/hunyuan-color/geometry/'+encodeURIComponent(id)+'/'+g.shown_candidate+'/fit_'+v+'.png',{headers:{'X-Workflow-Key':KEY}}).then(r=>r.ok?r.blob():null).then(b=>{if(b)img.src=URL.createObjectURL(b);});});
 }).catch(e=>{box.textContent='Geometry check evidence unavailable: '+e.message;});
 return box;
}
const refCache={};
function checkpointRefs(cp,id){
 let box=$('layout-ckpt-refs');
 if(!/^Checkpoint 2/.test(checkpointKind(cp))){if(box)box.remove();return null;}
 if(box&&box.dataset.job===id)return box;
 if(box)box.remove();
 box=document.createElement('section');box.id='layout-ckpt-refs';box.dataset.job=id;const h=document.createElement('h4');h.textContent='Color references used for this model (prepared views)';const row=document.createElement('div');row.className='row';box.append(h,row);
 for(const view of ['front','left','right','back','top','main']){
  const fig=document.createElement('figure');fig.hidden=true;const img=document.createElement('img');img.alt=view+' reference';const cap=document.createElement('figcaption');cap.textContent=view;fig.append(img,cap);row.append(fig);
  const key=id+'/'+view;const show=url=>{img.src=url;fig.hidden=false;};
  if(refCache[key]!==undefined){if(refCache[key])show(refCache[key]);continue;}
  fetch('/hunyuan-color/prepared/'+encodeURIComponent(id)+'/'+view+'.png',{headers:{'X-Workflow-Key':KEY}}).then(r=>r.ok?r.blob():null).then(b=>{refCache[key]=b?URL.createObjectURL(b):null;if(refCache[key]&&box.isConnected)show(refCache[key]);}).catch(()=>{refCache[key]=null;});
 }
 return box;
}
function colorSteps(stages,phase,active){
 const steps=stages?(stages.matches('div.steps')?stages:stages.querySelector('div.steps')):null;
 if(!steps)return;
 const sig=active?phase:'';
 if(steps.dataset.colorSig===sig&&(!active||steps.querySelector('.layout-color')))return;
 steps.dataset.colorSig=sig;
 steps.querySelectorAll('.layout-color').forEach(n=>n.remove());
 if(!active)return;
 const base=steps.querySelectorAll(':scope > .step').length;
 steps.querySelectorAll(':scope > .step').forEach(n=>{n.classList.remove('current');n.classList.add('past');});
 const at=PHASE_STEP[phase]??-1;
 COLOR_STEPS.forEach((title,i)=>{const chip=document.createElement('div');chip.className='step layout-color'+(i===at?' current':i<at?' past':'');chip.textContent=(base+i+1)+'. '+title;steps.append(chip);});
}
// ---- STAGE_UNIFY_V1 ----
function bar(cls,label){const b=document.createElement('div');b.className='ssb-bar '+cls;const l=document.createElement('div');l.className='label';l.textContent=label;const t=document.createElement('div');t.className='track';const f=document.createElement('div');f.className='fill';t.append(f);b.append(l,t);return b;}
function stageBlock(){
 let b=$('studio-stage-block');
 if(!b){b=document.createElement('section');b.id='studio-stage-block';b.setAttribute('aria-live','polite');const t=document.createElement('div');t.className='ssb-title';t.textContent='Loading stages...';const chips=document.createElement('div');chips.id='studio-stage-chips';b.append(t,chips,bar('ssb-stage idle','Overall progress'),bar('ssb-task idle','Current task'));}
 return b;
}
function setText(n,t){if(n&&n.textContent!==t)n.textContent=t;}
function setBar(b,label,pct,mode){setText(b.querySelector('.label'),label);b.classList.toggle('indeterminate',mode==='indeterminate');b.classList.toggle('idle',mode==='idle');const w=(pct==null?0:Math.max(0,Math.min(100,pct)))+'%';const f=b.querySelector('.fill');if(b.classList.contains('ssb-task')){b._mode=mode;if(mode==='value'){if(b._real==null||pct<b._real-0.5)b._shown=pct;b._real=pct;}else b._real=null;return;}if(mode==='value'&&f.style.width!==w)f.style.width=w;}
// SMOOTH_TASK_BAR_V1: the task bar glides toward the reported value and creeps slowly (at most 4 points) while a long step reports nothing new
setInterval(()=>{const b=document.querySelector('#studio-stage-block .ssb-task');if(!b||b._mode!=='value'||b._real==null)return;const r=b._real;let s=b._shown==null?r:b._shown;s=s<r?s+Math.max(0.3,(r-s)*0.3):Math.min(s+0.08,r+4,99.5);b._shown=s;const f=b.querySelector('.fill');if(f)f.style.width=s.toFixed(2)+'%';},400);
const KIND={running:'running',waiting:'waiting for you',queued:'waiting for the worker',stopped:'stopped',done:'done'};
function updateStage(d,id){
 const b=$('studio-stage-block');if(!b||d.engine!=='hunyuan')return;
 const chips=$('studio-stage-chips');
 if(chips.dataset.job!==id||chips.children.length!==d.count){chips.dataset.job=id;chips.replaceChildren(...d.stages.map((s,i)=>{const c=document.createElement('div');c.className='chip';c.textContent=(i+1)+'. '+s;return c;}));}
 Array.from(chips.children).forEach((c,i)=>{const cls='chip'+(i<d.index-1||(d.kind==='done'&&i===d.index-1)?' past':i===d.index-1?' current '+d.kind:'');if(c.className!==cls)c.className=cls;});
 const title='Stage '+d.index+' of '+d.count+' \u2014 '+d.title+' ('+KIND[d.kind]+')';setText(b.querySelector('.ssb-title'),title);b.dataset.title=d.title;b.dataset.kind=d.kind;
 setBar(b.querySelector('.ssb-stage'),'Overall: stage '+d.index+' of '+d.count+(d.kind==='done'?' finished':'')+' \u00b7 '+d.overall_percent.toFixed(0)+'% of the workflow',d.overall_percent,'value');
 const t=d.task||{},p=t.progress?t.progress.percent:null,tb=b.querySelector('.ssb-task');
 if(d.kind==='running'&&t.running)setBar(tb,'Current task'+(p==null?': working (this step reports no measurable progress)':': '+p.toFixed(0)+'%')+(t.progress?' \u00b7 '+t.progress.line.replace(/^\s*\d{1,3}%\|\s*/,'').slice(0,110):''),p,p==null?'indeterminate':'value');
 else setBar(tb,d.kind==='waiting'?'Current task: waiting for your answer below':d.kind==='queued'?'Current task: queued for the worker':d.kind==='stopped'?'Current task: stopped \u2014 see the error below':'Current task: none (finished)',0,'idle');
}
function arrange(){
 scheduled=false;
 const root=$('detail');if(!root)return;
 const id=jobId(root);if(!id)return;
 if(id!==lastJob){lastJob=id;expanded=false;}
 const kids=Array.from(root.children);
 const legacyStages=direct(root,'div.steps')||kids.find(k=>k.tagName==='DETAILS'&&k.querySelector(':scope > div.steps'));
 const selectedView=/^Selected job/.test(root.querySelector('h2')?.textContent||'');
 if(!legacyStages&&!selectedView)return;          // archive view: leave untouched
 const stages=legacyStages||stageBlock();          // STAGE_UNIFY_V1: Hunyuan jobs get the fixed 12-stage block
 if(legacyStages)$('studio-stage-block')?.remove();
 const note=kids.find(k=>k.tagName==='P'&&k.textContent.startsWith('Stages are not a percentage'));
 if(note)note.id='job-stage-note';
 const attempt=kids.find(k=>k.tagName==='P'&&k.textContent.startsWith('Attempt '));
 const cancel=direct(root,'#job-cancel-controls');
 let controls=direct(root,'[data-layout="controls"]');
 if(!controls){const mono=direct(root,'p.mono');for(let n=mono.nextElementSibling;n&&n!==stages;n=n.nextElementSibling){if(n.matches('div.row')&&!n.matches('.between')&&!n.id){n.dataset.layout='controls';controls=n;break;}}}
 const panel=root.querySelector('#photo-color-workflow');
 const phase=panel?.dataset.phase||'';
 const active=!!panel&&panel.parentElement===root&&!!phase&&phase!=='idle';
 const box=consoleBox();box.dataset.job=id;const prog=legacyStages?progressBox():null;if(!legacyStages)$('job-progress')?.remove();
 const cp=!active?direct(root,'#hunyuan-checkpoint'):null;const proxy=approveProxy(cp);const refs=cp?checkpointRefs(cp,id):null;const geo=cp?geometryEvidence(cp,id):null;
 if(!cp){$('layout-ckpt-refs')?.remove();$('layout-geometry-check')?.remove();if(!active)$('layout-approve')?.remove();}
 const ckpt1=cp&&/^Checkpoint 1/.test(checkpointKind(cp));
 let toggle=$('layout-earlier-toggle');
 if(active&&!toggle){toggle=document.createElement('button');toggle.type='button';toggle.id='layout-earlier-toggle';toggle.onclick=()=>{expanded=!expanded;schedule();};}
 if(!active&&toggle){toggle.remove();toggle=null;}
 if(toggle)toggle.textContent=expanded?'\u25be Hide earlier stages (geometry checkpoint, warnings, previews)':'\u25b8 Show earlier stages (geometry checkpoint, warnings, previews)';
 const head=kids[0]&&kids[0].matches('div.row.between')?kids[0]:null,later=[active?panel:null,toggle,cp,geo,refs,ckpt1?direct(root,'#hunyuan-autorouting'):null,proxy,cp?direct(root,'#solid-mesh-review'):null];
 const want=(legacyStages?[head,direct(root,'p.mono'),direct(root,'.job-info-area'),controls,cancel,attempt,stages,note,direct(root,'#guided-current-stage'),box,prog,...later]
  :[head,direct(root,'p.mono'),stages,direct(root,'#guided-current-stage'),...kids.filter(k=>k.matches('.notice.error')),box,cancel,controls,attempt,direct(root,'.job-info-area'),...later]).filter(Boolean);   // STAGE_UNIFY_V1: fixed-height items first, errors right under the current stage
 for(let i=0;i<want.length;i++){const cur=root.children[i];if(cur!==want[i])root.insertBefore(want[i],cur||null);}
 const keep=new Set(want);
 for(const k of Array.from(root.children)){if(keep.has(k))continue;k.classList.toggle('layout-hidden',active&&!expanded&&!k.matches('.notice.error'));}
 if(legacyStages)colorSteps(stages,phase,active);
 const exportButton=panel&&Array.from(panel.querySelectorAll('button')).find(b=>b.textContent.startsWith('\u2714 Approve & export'));if(exportButton)exportButton.classList.add('layout-approve');
}
function schedule(){if(!scheduled){scheduled=true;requestAnimationFrame(arrange);}}
async function poll(){
 const box=$('job-live-console');if(!box||!box.isConnected||fetching||document.hidden)return;
 const id=box.dataset.job;if(!id)return;fetching=true;
 try{
  let data;
  if($('studio-stage-block')){const r=await fetch('/hunyuan-color/stage/'+encodeURIComponent(id),{headers:{'X-Workflow-Key':KEY},cache:'no-store'});const d=await r.json();if(!r.ok)throw new Error(d.error||'Stage unavailable');if(box.dataset.job!==id)return;if(d.engine==='hunyuan'){updateStage(d,id);data=d.task;}}
  if(!data){const r=await fetch('/hunyuan-color/console/'+encodeURIComponent(id),{headers:{'X-Workflow-Key':KEY},cache:'no-store'});data=await r.json();if(!r.ok)throw new Error(data.error||'Log unavailable');}
  if(box.dataset.job!==id)return;
  const head=box.querySelector('.head'),pre=box.querySelector('pre');
  const title=data.file?'Live task log (last 5 lines) \u00b7 '+data.file+' \u00b7 updated '+data.modified:'Live task log \u00b7 no task log yet';
  const text=(data.lines||[]).join('\n')||' ';
  if(head.textContent!==title)head.textContent=title;
  if(pre.textContent!==text)pre.textContent=text;
  updateProgress(data);
 }catch(e){const head=box.querySelector('.head');if(head)head.textContent='Live task log unavailable: '+e.message;}
 finally{fetching=false;}
}
// STUDIO_VERSION_LABEL_V1: installed update version in front of the 'Connected' status (its text is rewritten every refresh).
async function showVersion(){
 const conn=$('connection');if(!conn){setTimeout(showVersion,1000);return;}
 let label=$('studio-version');
 if(!label){label=document.createElement('span');label.id='studio-version';label.style.cssText='margin-right:10px;padding:2px 8px;border:1px solid #4a6a8a;border-radius:10px;font-size:12px;color:#c9d6e5';conn.after(label);/* STUDIO_SHELL_V1: version to the right of Connected / server time */}
 try{const r=await fetch('/hunyuan-color/version',{headers:{'X-Workflow-Key':KEY},cache:'no-store'});const v=await r.json();label.textContent=v.version?'Version '+v.version+(v.build?' (build '+v.build+')':''):'Version unknown';label.title=v.installed?'Installed '+v.installed:'';}
 catch(e){label.textContent='Version unavailable';}
}
function start(){
 showVersion();
 const root=$('detail');if(!root){setTimeout(start,500);return;}
 let depth=0;new MutationObserver(()=>{if(depth>2){schedule();return;}depth++;try{arrange();}finally{Promise.resolve().then(()=>{depth=0;});}}).observe(root,{childList:true});   // STAGE_UNIFY_V1: re-order before the browser paints (no one-frame jump)
 schedule();setInterval(poll,2000);setInterval(schedule,3000);
}
start();
})();
