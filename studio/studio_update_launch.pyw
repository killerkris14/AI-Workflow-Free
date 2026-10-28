from pathlib import Path
import traceback
try:
    from studio_update_ui import launch
    root=Path(__file__).resolve().parent
    launch(root,'worker' if (root/'worker_settings.json').is_file() and not (root/'app.py').is_file() else 'main')
except Exception:
    import tkinter as tk
    from tkinter import messagebox
    window=tk.Tk();window.withdraw();messagebox.showerror('AI Studio launch error',traceback.format_exc());window.destroy()
