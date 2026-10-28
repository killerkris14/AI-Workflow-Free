const fs = require('fs');
const http = require('http');
const ROOT = 'C:\\AI-Workflow-Auto';
function call(method, route, data, key) {
  return new Promise((resolve, reject) => {
    const body = data ? JSON.stringify(data) : '';
    const req = http.request({hostname:'127.0.0.1', port:8765, path:route, method,
      headers:{'X-Workflow-Key':key, ...(data ? {'Content-Type':'application/json','Content-Length':Buffer.byteLength(body)} : {})}}, res => {
      let text=''; res.setEncoding('utf8'); res.on('data', x => text+=x);
      res.on('end', () => res.statusCode >= 400 ? reject(new Error(text)) : resolve(text));
    });
    req.setTimeout(15000, () => req.destroy(new Error('Controller timeout. Is Start-Workflow.bat running?')));
    req.on('error', reject); req.end(body);
  });
}
module.exports.runtime = {handler: async function({action, image_path, instructions, parent_job}) {
  try {
    const key=fs.readFileSync(ROOT+'\\access-token.txt','utf8').trim();
    if(action==='status') {
      const jobs=JSON.parse(await call('GET','/jobs',null,key));
      return JSON.stringify(jobs.slice(0,10).map(j => ({id:j.id,state:j.state,attempt:j.attempt,error:j.error,note:j.note})),null,2);
    }
    if(action!=='start' && action!=='revise') return 'ERROR: action must be start, revise, or status.';
    if(action==='revise' && !parent_job) return 'ERROR: revise needs the exact successful parent job ID.';
    const result=await call('POST','/start',{image_path:image_path||'', instructions:instructions||'', parent_job:action==='revise'?parent_job:''},key);
    return result+'\nQueued, not completed. Inspect the local dashboard at http://127.0.0.1:8765 . Do not repeatedly poll or claim the model passed until its status is SUCCEEDED.';
  } catch(error) {return 'ERROR: '+error.message;}
}};
