# AI Modeling Studio launcher. Installed by AI-Modeling-Studio-Setup.bat.
# One window: Open studio / Power off / Force power off.
# Everything started from here (studio, ComfyUI, Qwen router, Blender) runs inside a
# Windows Job Object, so Force power off closes exactly those processes and nothing else.
import ctypes, json, os, re, socket, subprocess, sys, threading, time, urllib.request, webbrowser
import tkinter as tk
from pathlib import Path
from tkinter import messagebox

ROOT = Path(__file__).resolve().parent
SETTINGS = ROOT / 'studio_settings.json'
LOG = ROOT / 'logs' / 'studio-console.log'
URL = 'http://127.0.0.1:8765'
WIN = os.name == 'nt'


def load_settings():
    try:
        return json.loads(SETTINGS.read_text(encoding='utf-8'))
    except Exception:
        return {}


class Job:
    """Windows Job Object: every child (and grandchild) dies together."""
    def __init__(self):
        self.handle = None
        if not WIN:
            return
        k = ctypes.windll.kernel32
        k.CreateJobObjectW.restype = ctypes.c_void_p
        self.handle = k.CreateJobObjectW(None, None)

        class IO(ctypes.Structure):
            _fields_ = [(n, ctypes.c_ulonglong) for n in ('a', 'b', 'c', 'd', 'e', 'f')]

        class Basic(ctypes.Structure):
            _fields_ = [('PerProcessUserTimeLimit', ctypes.c_longlong), ('PerJobUserTimeLimit', ctypes.c_longlong),
                        ('LimitFlags', ctypes.c_uint32), ('MinimumWorkingSetSize', ctypes.c_size_t),
                        ('MaximumWorkingSetSize', ctypes.c_size_t), ('ActiveProcessLimit', ctypes.c_uint32),
                        ('Affinity', ctypes.c_size_t), ('PriorityClass', ctypes.c_uint32), ('SchedulingClass', ctypes.c_uint32)]

        class Ext(ctypes.Structure):
            _fields_ = [('Basic', Basic), ('Io', IO), ('ProcessMemoryLimit', ctypes.c_size_t), ('JobMemoryLimit', ctypes.c_size_t),
                        ('PeakProcessMemoryUsed', ctypes.c_size_t), ('PeakJobMemoryUsed', ctypes.c_size_t)]
        info = Ext()
        info.Basic.LimitFlags = 0x2000  # KILL_ON_JOB_CLOSE
        k.SetInformationJobObject(ctypes.c_void_p(self.handle), 9, ctypes.byref(info), ctypes.sizeof(info))

    def start(self, args, cwd, out):
        if not WIN:
            return subprocess.Popen(args, cwd=cwd, stdout=out, stderr=subprocess.STDOUT)
        # Start suspended, put it in the job, then resume: no child can escape the job.
        p = subprocess.Popen(args, cwd=cwd, stdout=out, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                             creationflags=0x00000004 | 0x08000000)  # CREATE_SUSPENDED | CREATE_NO_WINDOW
        ctypes.windll.kernel32.AssignProcessToJobObject(ctypes.c_void_p(self.handle), ctypes.c_void_p(int(p._handle)))
        ctypes.windll.ntdll.NtResumeProcess(ctypes.c_void_p(int(p._handle)))
        return p

    def kill(self):
        if self.handle:
            ctypes.windll.kernel32.TerminateJobObject(ctypes.c_void_p(self.handle), 1)


def port_open(port, host='127.0.0.1'):
    with socket.socket() as s:
        s.settimeout(0.5)
        return s.connect_ex((host, port)) == 0


def exe_path(pid):
    if not WIN:
        return ''
    k = ctypes.windll.kernel32
    k.OpenProcess.restype = ctypes.c_void_p
    h = k.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not h:
        return ''
    try:
        buf = ctypes.create_unicode_buffer(1024)
        size = ctypes.c_uint32(1024)
        if k.QueryFullProcessImageNameW(ctypes.c_void_p(h), 0, buf, ctypes.byref(size)):
            return buf.value
        return ''
    finally:
        k.CloseHandle(ctypes.c_void_p(h))


def listeners(ports):
    """{port: pid} for local TCP listeners (netstat, no extra modules)."""
    found = {}
    if not WIN:
        return found
    try:
        text = subprocess.run(['netstat', '-ano', '-p', 'TCP'], capture_output=True, text=True,
                              creationflags=0x08000000, timeout=20).stdout
    except Exception:
        return found
    for line in text.splitlines():
        m = re.match(r'\s*TCP\s+\S+:(\d+)\s+\S+\s+LISTENING\s+(\d+)', line)
        if m and int(m.group(1)) in ports:
            found[int(m.group(1))] = int(m.group(2))
    return found


def leftover_project_processes(cfg):
    """Only processes that listen on studio ports AND live in the studio's own folders."""
    comfy = str(cfg.get('comfy_dir', r'C:\ComfyUI_windows_portable')).lower()
    llama = str(cfg.get('llama_dir', r'C:\llama')).lower()
    result = []
    for port, pid in listeners({8765, 8188, 8080}).items():
        path = exe_path(pid).lower()
        name = os.path.basename(path)
        ok = (port == 8765 and name.startswith('python')) or \
             (port == 8188 and path.startswith(comfy)) or \
             (port == 8080 and path.startswith(llama))
        if ok and pid != os.getpid():
            result.append((pid, path, port))
    return result


def worker_call(cfg, action):
    if not cfg.get('two_pc') or not cfg.get('worker_key'):
        return 'worker remote control not configured'
    url = 'http://%s:%s/%s' % (cfg.get('worker_ip'), cfg.get('worker_control_port', 50053), action)
    req = urllib.request.Request(url, data=b'{}', method='POST',
                                 headers={'X-Worker-Key': cfg['worker_key'], 'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=6) as r:
            return r.read().decode('utf-8', 'replace')[:200]
    except Exception as e:
        return 'worker not reachable (%s)' % e


class App:
    def __init__(self):
        self.cfg = load_settings()
        self.job = Job()
        self.proc = None
        self.closing = False
        self.root = tk.Tk()
        self.root.title('AI Modeling Studio')
        self.root.geometry('640x420')
        self.root.protocol('WM_DELETE_WINDOW', self.on_close)
        top = tk.Frame(self.root)
        top.pack(fill='x', padx=10, pady=8)
        self.status = tk.StringVar(value='Starting...')
        tk.Label(top, textvariable=self.status, font=('Segoe UI', 12, 'bold'), anchor='w').pack(fill='x')
        row = tk.Frame(self.root)
        row.pack(fill='x', padx=10)
        tk.Button(row, text='Open studio', width=14, command=lambda: webbrowser.open(URL)).pack(side='left', padx=3)
        tk.Button(row, text='Power off', width=14, command=self.power_off).pack(side='left', padx=3)
        tk.Button(row, text='FORCE POWER OFF', width=18, bg='#b00020', fg='white', command=self.force_off).pack(side='left', padx=3)
        tk.Label(self.root, text='Power off = clean stop (refuses while a job is running).  '
                 'Force power off = close everything this studio started, right now.',
                 fg='#555', wraplength=610, justify='left').pack(fill='x', padx=10, pady=4)
        box = tk.Frame(self.root)
        box.pack(fill='both', expand=True, padx=10)
        self.text = tk.Text(box, height=12, wrap='word', font=('Consolas', 9))
        sb = tk.Scrollbar(box, command=self.text.yview)
        self.text.configure(yscrollcommand=sb.set)
        sb.pack(side='right', fill='y')
        self.text.pack(fill='both', expand=True)
        row2 = tk.Frame(self.root)
        row2.pack(fill='x', padx=10, pady=6)
        tk.Button(row2, text='Select all', command=self.select_all).pack(side='left', padx=3)
        tk.Button(row2, text='Copy all', command=self.copy_all).pack(side='left', padx=3)
        self.log_pos = 0
        self.root.after(200, self.start)

    def say(self, msg):
        self.text.insert('end', msg.rstrip() + '\n')
        self.text.see('end')

    def select_all(self):
        self.text.tag_add('sel', '1.0', 'end')
        self.text.focus_set()

    def copy_all(self):
        self.root.clipboard_clear()
        self.root.clipboard_append(self.text.get('1.0', 'end'))

    def start(self):
        if port_open(8765):
            self.status.set('Studio is already running (started elsewhere)')
            self.say('Port 8765 is already in use. Opening the existing studio. Force power off can still close it.')
            webbrowser.open(URL)
            return
        script = ROOT / 'start_ai_studio.py'
        if not script.exists():
            script = ROOT / 'app.py'
        if not script.exists():
            self.status.set('Studio files are missing')
            self.say('Could not find start_ai_studio.py or app.py in ' + str(ROOT) + '. Run the setup again (Repair).')
            return
        exe = Path(sys.executable)
        if exe.name.lower() == 'pythonw.exe' and (exe.parent / 'python.exe').exists():
            exe = exe.parent / 'python.exe'
        LOG.parent.mkdir(exist_ok=True)
        out = open(LOG, 'w', encoding='utf-8', errors='replace')
        env_note = worker_call(self.cfg, 'start') if self.cfg.get('two_pc') else ''
        if env_note:
            self.say('Second PC: ' + env_note)
        self.proc = self.job.start([str(exe), '-u', str(script)], str(ROOT), out)
        self.status.set('Running  -  ' + URL)
        self.say('Started ' + script.name + ' (pid %d). The studio opens in your browser.' % self.proc.pid)
        self.root.after(1000, self.tick)

    def tick(self):
        try:
            with open(LOG, 'r', encoding='utf-8', errors='replace') as f:
                f.seek(self.log_pos)
                chunk = f.read()
                self.log_pos = f.tell()
            if chunk:
                self.text.insert('end', chunk)
                self.text.see('end')
                lines = int(self.text.index('end').split('.')[0])
                if lines > 1500:
                    self.text.delete('1.0', '%d.0' % (lines - 1000))
        except Exception:
            pass
        if self.proc and self.proc.poll() is not None:
            code = self.proc.returncode
            self.job.kill()  # make sure ComfyUI / router / Blender started by the studio are gone too
            self.proc = None
            if code == 0 or self.closing:
                self.status.set('Studio stopped. Closing...')
                self.root.after(2500, self.root.destroy)
            else:
                self.status.set('Studio stopped with an error (code %s). Copy the text below if you need help.' % code)
            return
        self.root.after(1000, self.tick)

    def power_off(self):
        token_file = ROOT / 'access-token.txt'
        if not port_open(8765):
            self.job.kill()
            self.status.set('Studio is not running.')
            return
        try:
            key = token_file.read_text(encoding='utf-8').strip()
            req = urllib.request.Request(URL + '/services/power-off', data=b'{"confirm":true}', method='POST',
                                         headers={'X-Workflow-Key': key, 'Content-Type': 'application/json'})
            with urllib.request.urlopen(req, timeout=60) as r:
                r.read()
            self.closing = True
            self.status.set('Powering off cleanly...')
            self.say('Power off accepted. Waiting for the studio to finish closing.')
            if not self.proc:
                self.root.after(3000, self.root.destroy)
        except urllib.error.HTTPError as e:
            try:
                msg = json.loads(e.read()).get('error', str(e))
            except Exception:
                msg = str(e)
            if messagebox.askyesno('Power off refused', msg + '\n\nUse FORCE POWER OFF instead?'):
                self.force_off(confirm=False)
        except Exception as e:
            if messagebox.askyesno('Power off failed', 'Clean power off failed: %s\n\nUse FORCE POWER OFF instead?' % e):
                self.force_off(confirm=False)

    def force_off(self, confirm=True):
        if confirm and not messagebox.askyesno('Force power off',
                'Close the studio, ComfyUI, the Qwen model router and Blender right now?\n\n'
                'A running job will be interrupted. Windows and your other programs are not touched.'):
            return
        self.closing = True
        self.job.kill()
        if self.proc and self.proc.poll() is None:
            self.proc.kill()
        killed = []
        for pid, path, port in leftover_project_processes(self.cfg):
            subprocess.run(['taskkill', '/PID', str(pid), '/T', '/F'], capture_output=True, creationflags=0x08000000)
            killed.append('%s (port %d)' % (os.path.basename(path), port))
        if killed:
            self.say('Also closed: ' + ', '.join(killed))
        if self.cfg.get('two_pc'):
            self.say('Second PC: ' + worker_call(self.cfg, 'force-stop'))
        self.status.set('Force power off done.')
        self.say('Everything started by the studio has been closed.')
        self.root.after(2500, self.root.destroy)

    def on_close(self):
        if not self.proc and not port_open(8765):
            self.root.destroy()
            return
        if messagebox.askyesno('Close AI Modeling Studio', 'Closing this window powers off the studio. Continue?'):
            self.power_off()


def main():
    guard = socket.socket()
    try:
        guard.bind(('127.0.0.1', 8764))  # single instance
    except OSError:
        webbrowser.open(URL)
        return
    app = App()
    app.root.mainloop()
    app.job.kill()


if __name__ == '__main__':
    main()
