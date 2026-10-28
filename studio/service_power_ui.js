(() => {
'use strict';const KEY='__ACCESS_TOKEN__';
const create=(tag,text)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;return n;};
const container=document.querySelector('.portal-header-tools')||document.querySelector('header');if(!container||document.getElementById('studio-power-menu'))return;
const menu=create('details');menu.id='studio-power-menu';menu.style.cssText='position:relative;margin:0';const summary=create('summary','Power');summary.style.cssText='cursor:pointer;padding:6px 10px;border:1px solid #6aa98c;border-radius:7px;background:#174c37;color:#edf4ff;font-size:12px';menu.append(summary);
const body=create('div');body.style.cssText='position:absolute;right:0;top:100%;z-index:100;min-width:235px;padding:12px;background:#152b29;border:1px solid #6aa98c;border-radius:8px;box-shadow:0 8px 25px #0008';
const status=create('p','Checking services...');status.style.cssText='font-size:12px;margin:0 0 10px';const stop=create('button','Stop idle engines now'),off=create('button','Power off studio');stop.type=off.type='button';stop.style.cssText=off.style.cssText='display:block;width:100%;margin:7px 0';body.append(status,stop,off);menu.append(body);container.append(menu);
async function api(route,body){const options={headers:{'X-Workflow-Key':KEY},cache:'no-store'};if(body){options.method='POST';options.headers['Content-Type']='application/json';options.body=JSON.stringify(body);}const response=await fetch(route,options),data=await response.json();if(!response.ok)throw new Error(data.error||'Service request failed');return data;}
async function refresh(){try{const data=await api('/services/state');status.textContent=Object.entries(data.services).map(([name,s])=>name+': '+(s.active_jobs?'working':s.running?(s.owned?'managed / idle':'externally started'):'off')).join(' · ')+'\nIdle timeout: '+data.idle_seconds+'s';status.style.whiteSpace='pre-wrap';}catch(e){status.textContent=e.message;}}
stop.onclick=async()=>{stop.disabled=true;try{const data=await api('/services/stop',{confirm:true});status.textContent=data.note;}catch(e){status.textContent=e.message;}finally{stop.disabled=false;}};
off.onclick=async()=>{if(!confirm('Power off the studio and its managed engines? Waiting approvals are saved. Queued or processing jobs prevent shutdown.'))return;off.disabled=true;try{await api('/services/power-off',{confirm:true});status.textContent='Studio is off. Use your AI Modeling Studio desktop button to start it again.';stop.disabled=true;}catch(e){status.textContent=e.message;off.disabled=false;}};
menu.addEventListener('toggle',()=>{if(menu.open)refresh();});
function heartbeat(){api('/services/heartbeat').catch(()=>{});}heartbeat();setInterval(heartbeat,20000);
})();
