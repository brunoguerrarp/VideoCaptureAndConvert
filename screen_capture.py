import cv2
import numpy as np
import zipfile
import os
import time
import threading
import tkinter as tk
from typing import Callable

import mss
from PIL import Image, ImageTk
import win32gui
import win32con


def list_monitors() -> list[dict]:
    with mss.mss() as sct:
        # index 0 is the virtual full-desktop; skip it
        return [
            {"label": f"Monitor {i} ({m['width']}x{m['height']})", "monitor": dict(m)}
            for i, m in enumerate(sct.monitors[1:], start=1)
        ]


def list_windows() -> list[dict]:
    windows = []

    def _enum(hwnd, _):
        if not win32gui.IsWindowVisible(hwnd):
            return
        title = win32gui.GetWindowText(hwnd)
        if not title:
            return
        rect = win32gui.GetWindowRect(hwnd)
        w = rect[2] - rect[0]
        h = rect[3] - rect[1]
        if w > 0 and h > 0:
            windows.append({"label": title, "hwnd": hwnd})

    win32gui.EnumWindows(_enum, None)
    return windows


def capture_region(sct: mss.mss, region: dict) -> np.ndarray:
    img = sct.grab(region)
    return cv2.cvtColor(np.array(img), cv2.COLOR_BGRA2BGR)


def get_window_region(hwnd: int) -> dict | None:
    try:
        rect = win32gui.GetWindowRect(hwnd)
        # bring window to foreground so it's not hidden behind others
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        win32gui.SetForegroundWindow(hwnd)
        time.sleep(0.1)
        rect = win32gui.GetWindowRect(hwnd)
        left, top, right, bottom = rect
        return {"left": left, "top": top, "width": right - left, "height": bottom - top}
    except Exception:
        return None


def open_region_selector(root: tk.Tk, callback: Callable[[dict | None], None]) -> None:
    """
    Abre overlay fullscreen para selecao de regiao com clique e arraste.
    Chama callback(region) ao soltar o mouse, ou callback(None) se ESC.
    A captura do screenshot roda em thread separada para nao travar a UI.
    """

    def _grab():
        with mss.mss() as sct:
            virtual = dict(sct.monitors[0])  # area total cobrindo todos os monitores
            shot = sct.grab(virtual)
            bg_img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
        root.after(0, lambda: _show(virtual, bg_img))

    def _show(virtual: dict, bg_img: Image.Image):
        overlay = tk.Toplevel(root)
        overlay.overrideredirect(True)
        overlay.attributes("-topmost", True)
        overlay.geometry(f"{virtual['width']}x{virtual['height']}+{virtual['left']}+{virtual['top']}")

        tk_img = ImageTk.PhotoImage(bg_img)
        canvas = tk.Canvas(overlay, cursor="cross", highlightthickness=0,
                           width=virtual["width"], height=virtual["height"])
        canvas.pack()
        canvas.create_image(0, 0, anchor="nw", image=tk_img)
        canvas.image = tk_img

        # escurece levemente a tela toda
        canvas.create_rectangle(
            0, 0, virtual["width"], virtual["height"],
            fill="black", stipple="gray25", outline="",
        )

        # instrucao no topo
        canvas.create_rectangle(0, 0, virtual["width"], 36, fill="#000000", outline="")
        canvas.create_text(
            virtual["width"] // 2, 18,
            text="Clique e arraste para selecionar a regiao.  ESC para cancelar.",
            fill="white", font=("Segoe UI", 12, "bold"),
        )

        state: dict = {}
        rect_id: list = [None]
        dim_id: list = [None]

        def on_press(e):
            state["x0"], state["y0"] = e.x, e.y

        def on_drag(e):
            for item in (rect_id[0], dim_id[0]):
                if item:
                    canvas.delete(item)
            x0, y0 = state.get("x0", e.x), state.get("y0", e.y)
            x1, y1 = min(x0, e.x), min(y0, e.y)
            x2, y2 = max(x0, e.x), max(y0, e.y)
            rect_id[0] = canvas.create_rectangle(x1, y1, x2, y2, outline="#ff3333", width=2)
            w, h = x2 - x1, y2 - y1
            label_y = y1 - 16 if y1 > 30 else y2 + 16
            dim_id[0] = canvas.create_text(
                x1 + w // 2, label_y,
                text=f"{w} x {h} px",
                fill="white", font=("Segoe UI", 10, "bold"),
            )

        def on_release(e):
            x0, y0 = state.get("x0", e.x), state.get("y0", e.y)
            x1 = min(x0, e.x) + virtual["left"]
            y1 = min(y0, e.y) + virtual["top"]
            x2 = max(x0, e.x) + virtual["left"]
            y2 = max(y0, e.y) + virtual["top"]
            overlay.grab_release()
            overlay.destroy()
            if x2 - x1 > 5 and y2 - y1 > 5:
                callback({"left": x1, "top": y1, "width": x2 - x1, "height": y2 - y1})
            else:
                callback(None)

        def on_escape(_e):
            overlay.grab_release()
            overlay.destroy()
            callback(None)

        canvas.bind("<ButtonPress-1>", on_press)
        canvas.bind("<B1-Motion>", on_drag)
        canvas.bind("<ButtonRelease-1>", on_release)
        overlay.bind("<Escape>", on_escape)
        canvas.bind("<Escape>", on_escape)
        overlay.focus_force()
        overlay.grab_set()

    threading.Thread(target=_grab, daemon=True).start()


def compute_diff(frame1: np.ndarray, frame2: np.ndarray) -> float:
    gray1 = cv2.cvtColor(frame1, cv2.COLOR_BGR2GRAY)
    gray2 = cv2.cvtColor(frame2, cv2.COLOR_BGR2GRAY)
    return float(np.mean(cv2.absdiff(gray1, gray2)))


class LiveCaptureSession:
    """Runs in a background thread; caller controls start/stop."""

    def __init__(
        self,
        output_path: str,
        region: dict,
        threshold: float = 5.0,
        min_interval_sec: float = 0.5,
        capture_fps: float = 5.0,
        image_format: str = "png",
        log_fn: Callable[[str], None] = print,
        done_fn: Callable[[int, str], None] | None = None,
    ):
        self.output_path = output_path
        self.region = region
        self.threshold = threshold
        self.min_interval_sec = min_interval_sec
        self.capture_fps = capture_fps
        self.image_format = image_format
        self.log_fn = log_fn
        self.done_fn = done_fn
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self):
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_event.set()

    def _run(self):
        interval = 1.0 / self.capture_fps
        count = 0
        prev_frame = None
        last_captured_time = -self.min_interval_sec

        try:
            with mss.mss() as sct, zipfile.ZipFile(self.output_path, "w", zipfile.ZIP_DEFLATED) as zf:
                self.log_fn("Captura iniciada. Clique em Parar quando terminar.")
                start_time = time.time()

                while not self._stop_event.is_set():
                    tick = time.time()
                    frame = capture_region(sct, self.region)
                    now = time.time() - start_time

                    should_capture = False
                    if prev_frame is None:
                        should_capture = True
                        self.log_fn("Primeiro frame capturado")
                    else:
                        diff = compute_diff(prev_frame, frame)
                        if diff >= self.threshold and (now - last_captured_time) >= self.min_interval_sec:
                            should_capture = True
                            self.log_fn(f"[{now:.1f}s] Mudanca detectada (diff={diff:.2f})")

                    if should_capture:
                        count += 1
                        filename = f"Screen{count:04d}.{self.image_format}"
                        success, encoded = cv2.imencode(f".{self.image_format}", frame)
                        if success:
                            zf.writestr(filename, encoded.tobytes())
                            self.log_fn(f"  >> {filename}")
                        last_captured_time = now

                    prev_frame = frame

                    elapsed = time.time() - tick
                    sleep_for = interval - elapsed
                    if sleep_for > 0:
                        time.sleep(sleep_for)

            size_mb = os.path.getsize(self.output_path) / (1024 * 1024)
            self.log_fn(f"ZIP gerado: {self.output_path} ({size_mb:.1f} MB, {count} imagens)")
            if self.done_fn:
                self.done_fn(count, self.output_path)

        except Exception as e:
            self.log_fn(f"ERRO: {e}")
            if self.done_fn:
                self.done_fn(0, "")
