import json
import shutil
from pathlib import Path


def is_dragon_test(job):
    request=json.loads((job/'request.json').read_text(encoding='utf-8'))
    return request.get('instructions','').lstrip().startswith('[DRAGON_TEST]')


def run_dragon_test(cfg,job,blender_run,status,root,chat):
    if cfg.get('allow_generated_code_execution') is not True:raise RuntimeError('Generated-code execution is disabled in config.json.')
    request=json.loads((job/'request.json').read_text(encoding='utf-8'))
    if request.get('parent_job'):raise RuntimeError('[DRAGON_TEST] is a fixed baseline NEW job, not an arbitrary revision. Use a normal AI revision for changes.')
    if not Path(cfg['blender_exe']).is_file():raise RuntimeError('Blender executable not found.')
    settings_path=root/'mega_dragon_settings.json'
    settings=json.loads(settings_path.read_text(encoding='utf-8'))
    length=float(settings.get('length_mm',120))
    if not 80<=length<=180:raise RuntimeError('Baseline length must be 80..180mm.')
    mode='Fixed local dragon baseline; image and prose do not control geometry in [DRAGON_TEST] mode.'
    status(job,'PLANNING_MODEL',generation_mode='MEGA_DRAGON_BASELINE_v1',note=mode)
    description='Known stylized horizontal dragon baseline: orange body/head/snout/four legs/tapered tail, purple thick scalloped wings and blunt horns, green attached eyes. X length, Y width, Z height; separate closed intersecting parts.'
    (job/'description.txt').write_text(description,encoding='utf-8')
    (job/'requirements_history.txt').write_text('BASELINE TEST REQUEST:\n'+request['instructions']+'\nMODE: '+mode,encoding='utf-8')
    required=['Head','Body','Tail','Wing_Left','Wing_Right','Snout','Eye_Left','Eye_Right','Horn_Left','Horn_Right','Leg_Front_Left','Leg_Front_Right','Leg_Rear_Left','Leg_Rear_Right']
    plan={'target_length_mm':length,'max_height_mm':35*length/120,'require_horizontal':True,
          'separate_color_objects':True,'required_parts':required,'length_tolerance_fraction':.001,
          'bed_tolerance_mm':.01,'require_closed_parts':True,'request':request['instructions'],
          'assumptions':[mode,'No articulation; three colors; length comes from mega_dragon_settings.json.'],
          'parts':[{'name':name,'shape':'fixed closed baseline part'} for name in required]}
    (job/'quality_plan.json').write_text(json.dumps(plan,indent=2),encoding='utf-8')
    attempt=job/'attempt_01';attempt.mkdir()
    code='mega_build_report = build_stylized_dragon(length_mm='+repr(length)+')\n'
    (attempt/'model.py').write_text(code,encoding='utf-8')
    (attempt/'raw_response.txt').write_text('Trusted local recipe, not an LLM response.\n'+code,encoding='utf-8')
    status(job,'RUNNING_BLENDER',attempt=1,generation_mode='MEGA_DRAGON_BASELINE_v1',note=mode)
    exit_code=blender_run(cfg,attempt)
    report_path=attempt/'checks.json'
    report=json.loads(report_path.read_text(encoding='utf-8')) if report_path.exists() else {}
    if exit_code!=0 or not report.get('ok'):
        log=(attempt/'blender.log').read_text(encoding='utf-8',errors='replace')
        raise RuntimeError('Fixed baseline test failed; not repeatedly rebuilding the same recipe.\n'+json.dumps(report,indent=2)+'\n'+log[-14000:])
    (attempt/'quality_plan.json').write_text(json.dumps(plan,indent=2),encoding='utf-8')
    if settings.get('review_with_ai',True):
        from quality_support import quality_visual_review
        status(job,'REVIEWING_PREVIEW',attempt=1,generation_mode='MEGA_DRAGON_BASELINE_v1')
        review=quality_visual_review(cfg,attempt,plan, chat)
        report['visual_review']=review
        if not review['pass']:
            report['ok']=False;report['phase']='quality_review'
            report_path.write_text(json.dumps(report,indent=2),encoding='utf-8')
            raise RuntimeError('Baseline built and exported, but AI visual review rejected it. Files remain in attempt_01.\n'+json.dumps(review,indent=2))
    else:
        review={'pass':None,'issues':[],'observations':'AI review explicitly disabled in mega_dragon_settings.json for isolated builder testing.','performed':False}
        (attempt/'visual_review.json').write_text(json.dumps(review,indent=2),encoding='utf-8')
        report['visual_review_skipped']=review
        report.setdefault('warnings',[]).append('AI review was explicitly disabled for this baseline test; visual quality was not approved.')
    report['generation_mode']='MEGA_DRAGON_BASELINE_v1'
    report_path.write_text(json.dumps(report,indent=2),encoding='utf-8')
    final=job/'final';final.mkdir()
    for filename in ('model.py','model.blend','model.3mf','preview.png','preview_side.png','preview_top.png','quality_plan.json','visual_review.json','checks.json','blender.log'):
        path=attempt/filename
        if not path.is_file():raise RuntimeError('Missing baseline deliverable: '+filename)
        shutil.copy2(path,final/filename)
    status(job,'SUCCEEDED',attempt=1,checks=report,generation_mode='MEGA_DRAGON_BASELINE_v1',note=mode+' Inspect previews and sliced layers before printing.')
