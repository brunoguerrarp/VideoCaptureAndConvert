import ctypes
import ctypes.wintypes
import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path

from tkinterdnd2 import DND_FILES, TkinterDnD

from video_screen_capture import process_video
from screen_capture import LiveCaptureSession, list_monitors, list_windows, open_region_selector


# ---------------------------------------------------------------------------
# Shared settings widget
# ---------------------------------------------------------------------------

class SettingsFrame(tk.LabelFrame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, text="Configuracoes de deteccao", padx=10, pady=8, **kwargs)
        self.threshold = tk.DoubleVar(value=5.0)
        self.interval = tk.DoubleVar(value=0.5)
        self.fmt = tk.StringVar(value="png")
        self._build()

    def _build(self):
        tk.Label(self, text="Sensibilidade (threshold):").grid(row=0, column=0, sticky="w", pady=3)
        tk.Spinbox(self, from_=1.0, to=50.0, increment=0.5, textvariable=self.threshold,
                   width=7, format="%.1f").grid(row=0, column=1, sticky="w", padx=8)
        tk.Label(self, text="(menor = mais sensivel)", fg="#666").grid(row=0, column=2, sticky="w")

        tk.Label(self, text="Intervalo minimo (seg):").grid(row=1, column=0, sticky="w", pady=3)
        tk.Spinbox(self, from_=0.1, to=10.0, increment=0.1, textvariable=self.interval,
                   width=7, format="%.1f").grid(row=1, column=1, sticky="w", padx=8)
        tk.Label(self, text="(entre capturas)", fg="#666").grid(row=1, column=2, sticky="w")

        tk.Label(self, text="Formato das imagens:").grid(row=2, column=0, sticky="w", pady=3)
        frm = tk.Frame(self)
        frm.grid(row=2, column=1, columnspan=2, sticky="w", padx=8)
        tk.Radiobutton(frm, text="PNG", variable=self.fmt, value="png").pack(side="left")
        tk.Radiobutton(frm, text="JPG", variable=self.fmt, value="jpg").pack(side="left", padx=8)


# ---------------------------------------------------------------------------
# Log + progress widget
# ---------------------------------------------------------------------------

class LogFrame(tk.Frame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.progress = ttk.Progressbar(self, mode="indeterminate", length=430)
        self.progress.pack(fill="x", pady=(0, 4))
        text_frame = tk.Frame(self)
        text_frame.pack(fill="both", expand=True)
        self._text = tk.Text(text_frame, height=9, state="disabled", bg="#f8f9fa",
                             fg="#333", font=("Consolas", 9), relief="flat", bd=1)
        scroll = tk.Scrollbar(text_frame, command=self._text.yview)
        self._text.configure(yscrollcommand=scroll.set)
        self._text.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

    def append(self, msg: str):
        self._text.config(state="normal")
        self._text.insert("end", msg + "\n")
        self._text.see("end")
        self._text.config(state="disabled")

    def clear(self):
        self._text.config(state="normal")
        self._text.delete("1.0", "end")
        self._text.config(state="disabled")

    def start(self):
        self.progress.start(10)

    def stop(self):
        self.progress.stop()


# ---------------------------------------------------------------------------
# Output path widget
# ---------------------------------------------------------------------------

class OutputFrame(tk.LabelFrame):
    def __init__(self, parent, default_name="screens", **kwargs):
        super().__init__(parent, text="Arquivo de saida", padx=10, pady=6, **kwargs)
        self.out_dir = tk.StringVar(value=str(Path.home() / "Desktop"))
        self.out_name = tk.StringVar(value=default_name)
        self._build()

    def _build(self):
        tk.Label(self, text="Pasta:").grid(row=0, column=0, sticky="w", pady=2)
        tk.Entry(self, textvariable=self.out_dir, width=34).grid(row=0, column=1, sticky="ew", padx=4)
        tk.Button(self, text="...", width=3,
                  command=self._choose).grid(row=0, column=2)

        tk.Label(self, text="Nome:").grid(row=1, column=0, sticky="w", pady=2)
        name_frm = tk.Frame(self)
        name_frm.grid(row=1, column=1, sticky="w", padx=4)
        tk.Entry(name_frm, textvariable=self.out_name, width=26).pack(side="left")
        tk.Label(name_frm, text=".zip", fg="#666").pack(side="left")

        self.columnconfigure(1, weight=1)

    def _choose(self):
        d = filedialog.askdirectory(title="Escolher pasta de saida")
        if d:
            self.out_dir.set(d)

    @property
    def path(self) -> str:
        name = self.out_name.get().strip() or "screens"
        if not name.endswith(".zip"):
            name += ".zip"
        return str(Path(self.out_dir.get()) / name)


# ---------------------------------------------------------------------------
# Tab 1 — Video file
# ---------------------------------------------------------------------------

class VideoTab(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, padx=10, pady=8)
        self._video_path = tk.StringVar()
        self._build()

    def _build(self):
        # Drop zone
        drop_lf = tk.LabelFrame(self, text="Video (.mp4)", padx=6, pady=6)
        drop_lf.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        self._drop = tk.Label(drop_lf, text="Arraste o arquivo .mp4 aqui\nou clique para selecionar",
                              bg="#e8f0fe", fg="#3c4043", width=54, height=4,
                              relief="groove", bd=3, cursor="hand2")
        self._drop.pack(fill="both", expand=True)
        self._drop.drop_target_register(DND_FILES)
        self._drop.dnd_bind("<<Drop>>", self._on_drop)
        self._drop.bind("<Button-1>", self._on_click)

        self._file_lbl = tk.Label(self, text="", fg="#1a73e8", wraplength=430, justify="left")
        self._file_lbl.grid(row=1, column=0, sticky="w")

        self._settings = SettingsFrame(self)
        self._settings.grid(row=2, column=0, sticky="ew", pady=6)

        self._output = OutputFrame(self, default_name="screens")
        self._output.grid(row=3, column=0, sticky="ew", pady=(0, 6))

        self._log = LogFrame(self)
        self._log.grid(row=4, column=0, sticky="ew")

        self._btn = tk.Button(self, text="Processar Video", command=self._run,
                              bg="#1a73e8", fg="white", font=("Segoe UI", 10, "bold"),
                              relief="flat", padx=16, pady=7, cursor="hand2")
        self._btn.grid(row=5, column=0, pady=(8, 0))
        self.columnconfigure(0, weight=1)

    def _on_drop(self, event):
        self._set_video(event.data.strip().strip("{}"))

    def _on_click(self, _=None):
        path = filedialog.askopenfilename(
            title="Selecionar video",
            filetypes=[("Videos MP4", "*.mp4"), ("Todos os arquivos", "*.*")],
        )
        if path:
            self._set_video(path)

    def _set_video(self, path: str):
        self._video_path.set(path)
        self._drop.config(text=f"Video: {Path(path).name}", bg="#d2e3fc")
        self._file_lbl.config(text=path)
        self._output.out_name.set(Path(path).stem + "_screens")
        self._output.out_dir.set(str(Path(path).parent))

    def _run(self):
        video = self._video_path.get()
        if not video or not os.path.isfile(video):
            messagebox.showwarning("Atencao", "Selecione um arquivo .mp4 valido.")
            return

        output_path = self._output.path
        self._btn.config(state="disabled", text="Processando...")
        self._log.clear()
        self._log.start()

        def worker():
            try:
                self._log.append(f"Iniciando: {Path(video).name}")
                total = process_video(
                    video, output_path,
                    threshold=self._settings.threshold.get(),
                    min_interval_sec=self._settings.interval.get(),
                    image_format=self._settings.fmt.get(),
                    log_fn=self._log.append,
                )
                self._log.append(f"\nConcluido: {total} telas capturadas.")
                self.after(0, lambda: messagebox.showinfo(
                    "Pronto!", f"{total} telas capturadas.\n\nSalvo em:\n{output_path}"))
            except Exception as e:
                self._log.append(f"\nERRO: {e}")
                self.after(0, lambda: messagebox.showerror("Erro", str(e)))
            finally:
                self.after(0, self._done)

        threading.Thread(target=worker, daemon=True).start()

    def _done(self):
        self._log.stop()
        self._btn.config(state="normal", text="Processar Video")


# ---------------------------------------------------------------------------
# Tab 2 — Live capture
# ---------------------------------------------------------------------------

class LiveTab(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, padx=10, pady=8)
        self._session: LiveCaptureSession | None = None
        self._monitors: list[dict] = []
        self._windows: list[dict] = []
        self._build()

    def _build(self):
        # Source type
        src_lf = tk.LabelFrame(self, text="Fonte de captura", padx=8, pady=6)
        src_lf.grid(row=0, column=0, sticky="ew", pady=(0, 6))

        self._src_type = tk.StringVar(value="monitor")
        tk.Radiobutton(src_lf, text="Monitor", variable=self._src_type,
                       value="monitor", command=self._on_src_change).grid(row=0, column=0, sticky="w")
        tk.Radiobutton(src_lf, text="Janela", variable=self._src_type,
                       value="window", command=self._on_src_change).grid(row=0, column=1, sticky="w", padx=16)
        tk.Radiobutton(src_lf, text="Regiao Personalizada", variable=self._src_type,
                       value="region", command=self._on_src_change).grid(row=0, column=2, sticky="w", padx=16)

        # Monitor selector
        self._mon_frame = tk.Frame(src_lf)
        self._mon_frame.grid(row=1, column=0, columnspan=3, sticky="ew", pady=4)
        tk.Label(self._mon_frame, text="Monitor:").pack(side="left")
        self._mon_var = tk.StringVar()
        self._mon_cb = ttk.Combobox(self._mon_frame, textvariable=self._mon_var,
                                    state="readonly", width=36)
        self._mon_cb.pack(side="left", padx=6)
        tk.Button(self._mon_frame, text="Atualizar",
                  command=self._refresh_monitors).pack(side="left")

        # Window selector
        self._win_frame = tk.Frame(src_lf)
        self._win_frame.grid(row=2, column=0, columnspan=3, sticky="ew", pady=4)
        tk.Label(self._win_frame, text="Janela:").pack(side="left")
        self._win_var = tk.StringVar()
        self._win_cb = ttk.Combobox(self._win_frame, textvariable=self._win_var,
                                    state="readonly", width=36)
        self._win_cb.pack(side="left", padx=6)
        tk.Button(self._win_frame, text="Atualizar",
                  command=self._refresh_windows).pack(side="left")

        # Region selector
        self._region_frame = tk.Frame(src_lf)
        self._region_frame.grid(row=3, column=0, columnspan=3, sticky="ew", pady=4)
        self._region_btn = tk.Button(
            self._region_frame, text="Selecionar Regiao na Tela",
            command=self._select_region,
            bg="#f28b00", fg="white", font=("Segoe UI", 9, "bold"),
            relief="flat", padx=10, pady=4, cursor="hand2",
        )
        self._region_btn.pack(side="left")
        self._region_lbl = tk.Label(self._region_frame, text="Nenhuma regiao selecionada", fg="#666")
        self._region_lbl.pack(side="left", padx=10)
        self._custom_region: dict | None = None

        # Capture FPS
        fps_frm = tk.Frame(src_lf)
        fps_frm.grid(row=4, column=0, columnspan=3, sticky="w", pady=(6, 2))
        tk.Label(fps_frm, text="Verificacoes por segundo:").pack(side="left")
        self._fps_var = tk.DoubleVar(value=5.0)
        tk.Spinbox(fps_frm, from_=1.0, to=30.0, increment=1.0,
                   textvariable=self._fps_var, width=6, format="%.0f").pack(side="left", padx=6)
        tk.Label(fps_frm, text="(quanto maior, mais preciso mas mais CPU)", fg="#666").pack(side="left")

        src_lf.columnconfigure(0, weight=1)

        self._settings = SettingsFrame(self)
        self._settings.grid(row=1, column=0, sticky="ew", pady=6)

        self._output = OutputFrame(self, default_name="captura_tela")
        self._output.grid(row=2, column=0, sticky="ew", pady=(0, 6))

        self._log = LogFrame(self)
        self._log.grid(row=3, column=0, sticky="ew")

        btn_frm = tk.Frame(self)
        btn_frm.grid(row=4, column=0, pady=(8, 0))
        self._start_btn = tk.Button(btn_frm, text="Iniciar Captura", command=self._start,
                                    bg="#188038", fg="white", font=("Segoe UI", 10, "bold"),
                                    relief="flat", padx=16, pady=7, cursor="hand2")
        self._start_btn.pack(side="left", padx=4)
        self._stop_btn = tk.Button(btn_frm, text="Parar", command=self._stop,
                                   bg="#c5221f", fg="white", font=("Segoe UI", 10, "bold"),
                                   relief="flat", padx=16, pady=7, cursor="hand2", state="disabled")
        self._stop_btn.pack(side="left", padx=4)

        self.columnconfigure(0, weight=1)

        # Initial populate
        self._refresh_monitors()
        self._refresh_windows()
        self._on_src_change()
        self._start_hotkey_listener()

    def _on_src_change(self):
        src = self._src_type.get()
        self._mon_frame.grid_remove()
        self._win_frame.grid_remove()
        self._region_frame.grid_remove()
        if src == "monitor":
            self._mon_frame.grid()
        elif src == "window":
            self._win_frame.grid()
        else:
            self._region_frame.grid()

    def _start_hotkey_listener(self):
        MOD_CONTROL = 0x0002
        MOD_SHIFT   = 0x0004
        VK_S        = 0x53
        WM_HOTKEY   = 0x0312
        user32      = ctypes.windll.user32

        def _run():
            if not user32.RegisterHotKey(None, 1, MOD_CONTROL | MOD_SHIFT, VK_S):
                return
            msg = ctypes.wintypes.MSG()
            while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
                if msg.message == WM_HOTKEY:
                    self.after(0, self._stop)
            user32.UnregisterHotKey(None, 1)

        threading.Thread(target=_run, daemon=True).start()

    def _select_region(self):
        # minimiza a janela principal para nao aparecer na selecao
        self.winfo_toplevel().iconify()
        self.after(300, lambda: open_region_selector(self.winfo_toplevel(), self._on_region_selected))

    def _on_region_selected(self, region: dict | None):
        self.winfo_toplevel().deiconify()
        if region:
            self._custom_region = region
            w, h = region["width"], region["height"]
            x, y = region["left"], region["top"]
            self._region_lbl.config(
                text=f"{w} x {h} px  (x={x}, y={y})",
                fg="#188038",
            )
        else:
            self._region_lbl.config(text="Selecao cancelada", fg="#c5221f")

    def _refresh_monitors(self):
        self._monitors = list_monitors()
        labels = [m["label"] for m in self._monitors]
        self._mon_cb["values"] = labels
        if labels:
            self._mon_cb.current(0)

    def _refresh_windows(self):
        self._windows = list_windows()
        labels = [w["label"] for w in self._windows]
        self._win_cb["values"] = labels
        if labels:
            self._win_cb.current(0)

    def _get_region(self) -> dict | None:
        src = self._src_type.get()
        if src == "monitor":
            idx = self._mon_cb.current()
            if idx < 0 or idx >= len(self._monitors):
                messagebox.showwarning("Atencao", "Selecione um monitor.")
                return None
            return self._monitors[idx]["monitor"]
        elif src == "window":
            idx = self._win_cb.current()
            if idx < 0 or idx >= len(self._windows):
                messagebox.showwarning("Atencao", "Selecione uma janela.")
                return None
            from screen_capture import get_window_region
            hwnd = self._windows[idx]["hwnd"]
            region = get_window_region(hwnd)
            if not region:
                messagebox.showerror("Erro", "Nao foi possivel obter a posicao da janela.")
                return None
            return region
        else:
            if not self._custom_region:
                messagebox.showwarning("Atencao", "Clique em 'Selecionar Regiao na Tela' primeiro.")
                return None
            return self._custom_region

    def _start(self):
        region = self._get_region()
        if region is None:
            return

        output_path = self._output.path
        self._log.clear()
        self._log.start()
        self._start_btn.config(state="disabled")
        self._stop_btn.config(state="normal")

        self._session = LiveCaptureSession(
            output_path=output_path,
            region=region,
            threshold=self._settings.threshold.get(),
            min_interval_sec=self._settings.interval.get(),
            capture_fps=self._fps_var.get(),
            image_format=self._settings.fmt.get(),
            log_fn=self._log.append,
            done_fn=self._on_done,
        )
        self._session.start()

        if self._src_type.get() == "region":
            self.winfo_toplevel().iconify()

    def _stop(self):
        if self._session:
            self._session.stop()
        self._stop_btn.config(state="disabled")

    def _on_done(self, total: int, path: str):
        self.after(0, self._log.stop)
        self.after(0, lambda: self._start_btn.config(state="normal"))
        self.after(0, self.winfo_toplevel().deiconify)
        if total > 0:
            self.after(0, lambda: messagebox.showinfo(
                "Pronto!", f"{total} telas capturadas.\n\nSalvo em:\n{path}"))


# ---------------------------------------------------------------------------
# Main app
# ---------------------------------------------------------------------------

class App(TkinterDnD.Tk):
    def __init__(self):
        super().__init__()
        self.title("Video Screen Capture")
        self.resizable(False, False)
        self._set_icon()
        self._build()

    def _set_icon(self):
        import sys, os
        if getattr(sys, "frozen", False):
            base = sys._MEIPASS
        else:
            base = os.path.dirname(os.path.abspath(__file__))
        ico = os.path.join(base, "icon.ico")
        if os.path.exists(ico):
            self.iconbitmap(ico)

    def _build(self):
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=8, pady=8)

        self._video_tab = VideoTab(nb)
        nb.add(self._video_tab, text="  Arquivo de Video  ")

        self._live_tab = LiveTab(nb)
        nb.add(self._live_tab, text="  Captura ao Vivo  ")

        tk.Label(self, text="Powered by Guerra", fg="#aaaaaa",
                 font=("Segoe UI", 8)).pack(side="bottom", pady=(0, 4))


if __name__ == "__main__":
    app = App()
    app.mainloop()
