"""Tk interfaces for the update launcher and local Release Tool."""
import ast,base64,hashlib,json,os,re,shutil,subprocess,sys,tempfile,threading,time,traceback,urllib.parse,webbrowser,zipfile
from pathlib import Path
import tkinter as tk
from tkinter import filedialog,messagebox,ttk
import studio_update_core as c

def launch(root,role='main'):
 root=Path(root);window=tk.Tk();window.title('AI Studio — update check');window.geometry('560x170')
 status=tk.StringVar(value='Checking the installed release...');tk.Label(window,textvariable=status,wraplength=520,justify='left').pack(padx=16,pady=20)
 outcomes=[];finished=threading.Event();gate=c.Gate(root)
 try:gate.__enter__()
 except Exception as error:messagebox.showinfo('Already launching',str(error),parent=window);window.destroy();return
 def worker():
  try:
   c.recover(root,role)
  except Exception as error:outcomes.append(('fatal',str(error)));finished.set();return
  try:
   if c.busy(root,role):outcomes.append(('ok','Existing services are running. Opening the existing launcher without applying an update.'))
   else:
    messages=[];c.check(root,role,messages.append);outcomes.append(('ok','\n'.join(messages)))
  except Exception as error:outcomes.append(('fallback',str(error)))
  finished.set()
 threading.Thread(target=worker,daemon=True).start();state={'waiting':True}
 def poll():
  if not finished.is_set():window.after(150,poll);return
  kind,text=outcomes[-1]
  if kind=='fatal':messagebox.showerror('Update recovery required',text,parent=window);gate.__exit__();window.destroy();return
  if kind=='fallback' and not messagebox.askyesno('Update check unavailable',text+'\n\nNo downloaded update was installed. Launch the existing local version instead?',parent=window):gate.__exit__();window.destroy();return
  status.set(text or 'Launching...')
  script=root/('worker_agent.pyw' if role=='worker' else 'studio_launcher.pyw')
  if not script.is_file():messagebox.showerror('Launcher missing','Run the setup wizard to repair '+str(script),parent=window);gate.__exit__();window.destroy();return
  try:process=subprocess.Popen([sys.executable,str(script)],cwd=str(root))
  except Exception as error:messagebox.showerror('Launch failed',str(error),parent=window);gate.__exit__();window.destroy();return
  window.withdraw();state['waiting']=False
  def wait():
   if process.poll() is None:window.after(500,wait)
   else:gate.__exit__();window.destroy()
  wait()
 def close():
  if state['waiting']:messagebox.showinfo('Checking update','Wait for the check to finish. No studio process has been launched yet.',parent=window)
 window.protocol('WM_DELETE_WINDOW',close);window.after(100,poll);window.mainloop()

def release(root):
 root=Path(root);window=tk.Tk();window.title('AI Studio Release Tool');window.geometry('790x670');window.minsize(680,580)
 profile=c.settings(root);cfg=c.read(root/'.studio_release'/'publisher.json');current=c.current_version(root).get('version','0.0.0')
 source=tk.StringVar(value=profile.get('manifest_url',''));version=tk.StringVar(value='1.0.1' if current=='0.0.0' else '.'.join(str(n) for n in (list(c.ver(current)[:2])+[c.ver(current)[2]+1])))
 destination=tk.StringVar(value=cfg.get('output',str(Path.home()/'Desktop'/'AI-Studio-Releases')))
 key=tk.StringVar(value=profile.get('public_key',''));state={'busy':False}
 tk.Label(window,text='Create a signed release, then upload its files to your update host.',font=('Segoe UI',12,'bold')).pack(anchor='w',padx=12,pady=(12,5))
 tk.Label(window,text='Application: '+str(root)+'   |   Installed: '+current,anchor='w').pack(fill='x',padx=12)
 form=tk.Frame(window);form.pack(fill='x',padx=12,pady=10);form.columnconfigure(1,weight=1)
 for row,(text,var) in enumerate([('Manifest HTTPS URL / local latest.json',source),('New release version',version),('Release output folder',destination)]):
  tk.Label(form,text=text).grid(row=row,column=0,sticky='w',pady=4);tk.Entry(form,textvariable=var).grid(row=row,column=1,sticky='ew',padx=8)
 tk.Button(form,text='Browse',command=lambda:destination.set(filedialog.askdirectory(parent=window) or destination.get())).grid(row=2,column=2)
 trust=tk.Frame(window);trust.pack(fill='x',padx=12);finger=tk.StringVar(value='No trusted signing key configured')
 def fingerprint():finger.set('Trusted key fingerprint: '+hashlib.sha256(key.get().encode()).hexdigest()[:24] if key.get() else 'No trusted signing key configured')
 fingerprint();tk.Label(trust,textvariable=finger,anchor='w').pack(fill='x')
 def load_key():
  path=filedialog.askopenfilename(title='Select the publisher public XML key',filetypes=[('Public XML key','*.xml')],parent=window)
  if path:key.set(Path(path).read_text(encoding='utf-8'));fingerprint()
 def create_key():
  if not messagebox.askyesno('Publisher signing identity','Create or reuse this Windows account’s publisher identity?\n\nIts private key is protected with Windows DPAPI and is NOT included in packages. Do not delete the signing identity after distributing installers. This account/profile is required to sign later releases.',parent=window):return
  try:key.set(c.identity());fingerprint();messagebox.showinfo('Publisher identity', 'Public key: '+str(c.PUBLIC)+'\nPrivate identity stays under '+str(c.PRIVATE.parent),parent=window)
  except Exception as error:messagebox.showerror('Signing identity',str(error),parent=window)
 tk.Button(trust,text='Publisher: create/reuse signing identity',command=create_key).pack(side='left',pady=7)
 tk.Button(trust,text='Import trusted public key',command=load_key).pack(side='left',padx=6)
 notes=tk.Text(window,height=4,wrap='word');notes.insert('1.0','Describe the changes in this release.');notes.pack(fill='x',padx=12,pady=6)
 tk.Label(window,text='Application files + custom node only. No model weights, jobs, tokens, or pairing settings.\nSource code is included as-is: review hardcoded secrets and test changes before signing.',justify='left',fg='#6a3700').pack(anchor='w',padx=12)
 log=tk.Text(window,height=12,wrap='word');log.pack(fill='both',expand=True,padx=12,pady=8)
 def say(text):log.insert('end',str(text)+'\n');log.see('end')
 def save_profile():
  location=c.validate_source(source.get());public=key.get().strip()
  if not public.startswith('<RSAKeyValue>') or '<D>' in public:raise ValueError('Import a public RSA XML key, not a private key.')
  previous=c.settings(root)
  if previous.get('public_key') and previous['public_key']!=public:
   if not messagebox.askyesno('Change trusted publisher','Replace the trusted signing key? Verify its fingerprint with the publisher first.',parent=window):return False
   previous['highest_sequence']=0
  previous.update(manifest_url=location,public_key=public,check_on_launch=True);c.set_settings(root,previous);say('Update source saved. Checks run before every desktop launch.');return True
 def save_click():
  try:save_profile()
  except Exception as error:messagebox.showerror('Update configuration',str(error),parent=window)
 def build():
  if state['busy']:return
  try:
   if not save_profile():return
   new=version.get().strip();c.ver(new);history=c.read(c.PRIVATE.parent/'release-history.json',{'version':'0.0.0','sequence':0})
   if c.ver(new)<=c.ver(history['version']):raise ValueError('Use a version newer than '+history['version']+'. Published versions must not be overwritten.')
   if c.busy(root):raise ValueError('Power off the studio and its managed services before making a release snapshot.')
   if not c.PRIVATE.exists() or not c.PUBLIC.exists() or c.PUBLIC.read_text(encoding='utf-8').strip()!=key.get().strip():raise ValueError('The configured public key does not match this Windows account’s publisher identity.')
   folder=Path(destination.get()).expanduser().resolve()/new
   if folder==root or root in folder.parents:raise ValueError('Choose a release output folder outside the application folder.')
   if folder.exists():raise ValueError('Release output already exists. Choose a new version or remove the unpublished failed build folder.')
   seed=root/'.studio_release'/'setup-seed.bat'
   if not seed.is_file():raise ValueError('Setup seed missing. Run the revised installer’s shortcut installation again.')
   location=c.validate_source(source.get());public=key.get().strip();text_notes=notes.get('1.0','end').strip();output_base=str(Path(destination.get()).expanduser().resolve());state['busy']=True
  except Exception as error:messagebox.showerror('Cannot build release',str(error),parent=window);return
  def work():
   try:
    with c.Gate(root):
     folder.mkdir(parents=True);seed_text=seed.read_text(encoding='utf-8-sig');payload='\n'.join(seed_text.splitlines()[1:]);tree=ast.parse(payload);worker_code=None
     for n in tree.body:
      if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='WORKER_B64' for t in n.targets):worker_code=base64.b64decode(ast.literal_eval(n.value))
     package=folder/('AI-Studio-Package-'+new+'.zip');count=c.bundle(root,package,new,worker_code)
     trust=base64.b64encode(json.dumps({'manifest_url':location,'public_key':public}).encode()).decode()
     setup_name='AI-Modeling-Studio-Setup-'+new+'.bat'
     seed_text,n=re.subn(r"(?m)^UPDATER_TRUST_B64 = '[^']*'$","UPDATER_TRUST_B64 = '"+trust+"'",seed_text)
     if n!=1:raise ValueError('Setup trust anchor missing or ambiguous.')
     seed_text,n=re.subn(r"(?m)^UPDATER_RELEASE_VERSION = '[^']*'$","UPDATER_RELEASE_VERSION = '"+new+"'",seed_text)
     if n!=1:raise ValueError('Setup release anchor missing.')
     ast.parse('\n'.join(seed_text.splitlines()[1:]));setup=folder/setup_name;setup.write_bytes(seed_text.replace('\r\n','\n').replace('\n','\r\n').encode('utf-8'))
     sequence=max(int(history.get('sequence',0)),int(c.settings(root).get('highest_sequence',0)))+1;now=time.time()
     body={'product':c.PRODUCT,'version':new,'sequence':sequence,'published':now,'expires':now+90*86400,'min_updater':'1.0.0','notes':text_notes,'package':{'name':package.name,'size':package.stat().st_size,'sha256':c.sha(package)},'setup':{'name':setup.name,'size':setup.stat().st_size,'sha256':c.sha(setup)},'file_count':count}
     envelope={'algorithm':'rsa-pkcs1v15-sha256','signed':body,'signature':c.ps('sign',data=c.canonical(body))}
     c.ps('verify',public,c.canonical(body),envelope['signature']);c.write(folder/'latest.json',envelope);(folder/'release-public.xml').write_text(public,encoding='utf-8')
     (folder/'UPLOAD-INSTRUCTIONS.txt').write_text('Upload '+package.name+' and '+setup.name+' to the same directory as your configured latest.json. Upload latest.json LAST, after both assets are available.\nNever upload release-key.dpapi or any private signing material.\nMetadata expires in 90 days; publish a newer release before expiry.\nThe installer handles third-party prerequisites separately.\n',encoding='utf-8')
     c.write(c.PRIVATE.parent/'release-history.json',{'version':new,'sequence':sequence});c.write(root/'.studio_release'/'publisher.json',{'output':output_base})
     if not location.startswith('https://'):
      target=Path(location);target.parent.mkdir(parents=True,exist_ok=True)
      for asset in (package,setup):
       if asset.resolve()!=(target.parent/asset.name).resolve():shutil.copy2(asset,target.parent/asset.name)
      temporary=target.with_name(target.name+'.tmp');shutil.copy2(folder/'latest.json',temporary);temporary.replace(target)
      result='Signed local test release published to '+str(target)
     else:result='Signed release CREATED (not uploaded). Upload the two assets, then latest.json LAST, to your configured host.'
    window.after(0,lambda:say(result+'\nOutput: '+str(folder)+'\nThe public installer contains only the public verification key, never the private signing identity.'))
   except Exception as error:
    text=str(error);window.after(0,lambda:say('BUILD FAILED: '+text+'\nNo remote upload was performed.'))
   finally:state['busy']=False
  threading.Thread(target=work,daemon=True).start()
 def restore():
  if not messagebox.askyesno('Restore previous application','Restore files from the last update backup? Jobs and settings are not replaced. Close all services first.',parent=window):return
  try:
   with c.Gate(root):folder=c.rollback(root)
   say('Restored previous version from '+str(folder))
  except Exception as error:messagebox.showerror('Rollback',str(error),parent=window)
 row=tk.Frame(window);row.pack(fill='x',padx=12,pady=(0,12));tk.Button(row,text='Save update source',command=save_click).pack(side='left');tk.Button(row,text='Build signed release',command=build).pack(side='left',padx=6);tk.Button(row,text='Restore previous version',command=restore).pack(side='left',padx=6)
 def close():
  if state['busy']:messagebox.showinfo('Release build active','Wait for packaging/signing to finish.',parent=window)
  else:window.destroy()
 window.protocol('WM_DELETE_WINDOW',close);window.mainloop()
