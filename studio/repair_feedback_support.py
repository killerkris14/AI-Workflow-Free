"""Local diagnostic reports. May contain user prompts and generated code; review before sharing."""
import datetime
import json
import traceback
from pathlib import Path

LIMITS={'request.json':18000,'description.txt':12000,'quality_plan.json':24000,
        'generation_error.txt':16000,'repair_feedback.json':24000,'checks.json':36000,
        'visual_review.json':16000,'blender.log':28000,'model.py':60000,'raw_response.txt':60000}

def _read(path,limit):
    try:
        if not path.is_file():return '[not available]'
        text=path.read_text(encoding='utf-8-sig',errors='replace')
        if len(text)>limit:
            if path.name in {'blender.log','generation_error.txt'}:
                return '[truncated: last %s characters]\n'%limit+text[-limit:]
            return text[:limit]+'\n[truncated: first %s characters]'%limit
        return text
    except Exception as error:return '[could not read: '+str(error)+']'

def _section(title,text):
    return '\n'+'='*78+'\n'+title+'\n'+'='*78+'\n'+str(text)+'\n'

def _atomic(path,text):
    temp=path.with_name(path.name+'.tmp')
    temp.write_text(text,encoding='utf-8');temp.replace(path)

def write_attempt_failure(job,attempt,stage,latest_error,root_failure=''):
    job,attempt=Path(job),Path(attempt)
    try:
        stamp=datetime.datetime.now().astimezone().isoformat(timespec='seconds')
        text='AI WORKFLOW - ATTEMPT FAILURE REPORT\n'
        text+='Created: '+stamp+'\nJob: '+job.name+'\nAttempt: '+attempt.name+'\nStage: '+str(stage)+'\n'
        text+='Contains local paths, prompts and generated code. Review before sharing.\n'
        text+=_section('LATEST FAILURE',latest_error)
        text+=_section('PRESERVED UNDERLYING FAILURE',root_failure or '[No earlier underlying failure recorded]')
        for name in ('request.json','description.txt','quality_plan.json'):
            text+=_section('JOB FILE: '+name,_read(job/name,LIMITS[name]))
        for name in ('generation_error.txt','repair_feedback.json','checks.json','visual_review.json','blender.log','model.py'):
            text+=_section('ATTEMPT FILE: '+name,_read(attempt/name,LIMITS[name]))
        # Raw response can explain extraction failures; avoid duplicating an identical script.
        raw=_read(attempt/'raw_response.txt',LIMITS['raw_response.txt'])
        code=_read(attempt/'model.py',LIMITS['model.py'])
        if raw!='[not available]' and raw.strip()!=code.strip():text+=_section('ATTEMPT FILE: raw_response.txt',raw)
        _atomic(attempt/'FAIL_REASON.txt',text)
        write_job_failure(job,'Most recent failed attempt: '+attempt.name+' ('+str(stage)+')')
    except Exception:
        print('WARNING: Could not write failure report:\n'+traceback.format_exc())

def write_job_failure(job,job_error):
    job=Path(job)
    try:
        text='AI WORKFLOW - COMBINED JOB FAILURE REPORT\nJob: '+job.name+'\n'
        text+='Send this one file for diagnosis. File sections can be truncated as labeled.\n'
        text+='Contains local paths, prompts and generated code. Review before sharing.\n'
        text+=_section('JOB FAILURE / CURRENT SUMMARY',job_error)
        attempts=sorted(p for p in job.glob('attempt_*') if p.is_dir())
        found=False
        for attempt in attempts:
            report=attempt/'FAIL_REASON.txt'
            if report.is_file():
                found=True
                text+=_section('FULL ATTEMPT REPORT: '+attempt.name,report.read_text(encoding='utf-8',errors='replace'))
        if not found:
            for name in ('request.json','description.txt','quality_plan.json'):
                text+=_section('JOB FILE: '+name,_read(job/name,LIMITS[name]))
        _atomic(job/'FAIL_REASON.txt',text)
    except Exception:
        print('WARNING: Could not write job summary:\n'+traceback.format_exc())
