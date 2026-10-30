"""ARCHIVE_RETENTION_V1 (AI Modeling Studio 0.016): archived jobs are deleted a set time after they were archived.

Settings: archive_retention.json  {"enabled": true, "hours": 24, "keep": ["<job id>", ...]}  (missing file = these defaults)
- The archive time is recorded the first time the scan sees a job in Archived-Jobs (marker file .archived_at, scan every
  10 minutes). Jobs that were already archived when this update was installed therefore get the full time from install.
- Only folders named like a job id (YYYYMMDD-HHMMSS-xxxxxxxx) inside Archived-Jobs are ever deleted. Jobs, Input, models,
  settings and everything else are never touched. A restored job loses its marker, so archiving it again restarts the clock.
- Every action is written to logs/archive-retention.log. Errors are logged, never hidden, and never stop the studio."""
import json, re, shutil, threading, time, traceback
from pathlib import Path
ROOT = Path(__file__).resolve().parent
MARK = '.archived_at'
JOB_ID = re.compile(r'\d{8}-\d{6}-[0-9a-f]{8}')
DEFAULTS = {'enabled': True, 'hours': 24, 'keep': []}
SCAN_SECONDS = 600


def settings(root=ROOT):
    s = dict(DEFAULTS)
    p = Path(root) / 'archive_retention.json'
    if p.is_file():
        raw = json.loads(p.read_text(encoding='utf-8-sig'))
        if not isinstance(raw, dict): raise ValueError('archive_retention.json must be a JSON object')
        s.update({k: raw[k] for k in DEFAULTS if k in raw})
    if not isinstance(s['enabled'], bool): raise ValueError('archive_retention.json: enabled must be true/false')
    if isinstance(s['hours'], bool) or not isinstance(s['hours'], (int, float)) or not 1 <= s['hours'] <= 8760: raise ValueError('archive_retention.json: hours must be 1-8760')
    if not isinstance(s['keep'], list) or not all(isinstance(k, str) for k in s['keep']): raise ValueError('archive_retention.json: keep must be a list of job ids')
    return s


def log(text, root=ROOT):
    d = Path(root) / 'logs'; d.mkdir(exist_ok=True)
    with (d / 'archive-retention.log').open('a', encoding='utf-8') as f: f.write(time.strftime('%Y-%m-%d %H:%M:%S ') + text + '\n')


def scan(archive_root, jobs_root, lock=None, now=None, root=ROOT):
    """One pass. Returns the list of deleted job ids."""
    s = settings(root); now = time.time() if now is None else now; deleted = []
    archive_root, jobs_root = Path(archive_root), Path(jobs_root)
    for d in (jobs_root.iterdir() if jobs_root.is_dir() else []):      # restored jobs: the archive clock starts again next time
        m = d / MARK
        if d.is_dir() and not d.is_symlink() and m.is_file(): m.unlink(); log('restored job %s: archive time cleared' % d.name, root)
    if not s['enabled'] or not archive_root.is_dir(): return deleted
    for d in sorted(archive_root.iterdir()):
        if not d.is_dir() or d.is_symlink() or not JOB_ID.fullmatch(d.name) or d.name in s['keep']: continue
        m = d / MARK
        if not m.is_file():
            m.write_text('%.0f' % now, encoding='utf-8'); log('archived job %s: will be deleted after %g h' % (d.name, s['hours']), root); continue
        try: t = float(m.read_text(encoding='utf-8').strip())
        except ValueError: m.write_text('%.0f' % now, encoding='utf-8'); log('archived job %s: unreadable archive time reset' % d.name, root); continue
        if now - t < s['hours'] * 3600: continue
        ctx = lock if lock is not None else threading.Lock()
        with ctx:
            if d.is_dir() and not d.is_symlink() and d.parent.resolve() == archive_root.resolve():
                shutil.rmtree(d); deleted.append(d.name); log('DELETED archived job %s (archived %.1f h ago)' % (d.name, (now - t) / 3600), root)
    return deleted


def start(main, root=ROOT):
    """Background thread for the studio server (called once at startup)."""
    archive_root = Path(main.get('ARCHIVE_ROOT') or Path(root) / 'Archived-Jobs'); jobs_root = Path(main.get('JOBS') or Path(root) / 'Jobs')
    lock = main.get('ARCHIVE_LOCK')
    def run():
        time.sleep(30)
        while True:
            try: scan(archive_root, jobs_root, lock, root=root)
            except Exception: log('ERROR ' + traceback.format_exc().replace('\n', ' | '), root)
            time.sleep(SCAN_SECONDS)
    t = threading.Thread(target=run, daemon=True, name='archive-retention'); t.start(); return t
