from pathlib import Path
import traceback
try:
    from studio_update_ui import release
    release(Path(__file__).resolve().parent)
except Exception:
    import tkinter as tk
    from tkinter import messagebox
    window=tk.Tk();window.withdraw();messagebox.showerror('Release Tool error',traceback.format_exc());window.destroy()
