#!/usr/bin/env python3
"""
Snip & Solve — a visible study helper.

Press the hotkey (default Ctrl+.), drag a box over a problem anywhere on your
own screen (a PDF, a textbook photo, a practice set), and Claude returns a
full worked solution with the reasoning explained, shown in a small window in
the corner of your screen.

This is a study tool: it runs in a normal, visible window so you can learn the
method while you practice. It is not designed to run covertly inside proctored
or locked-down exam software.

Subjects it handles well: physics, biology, and math — step-by-step
derivations, concept explanations, and follow-up practice.
"""

import base64
import io
import os
import queue
import threading
import tkinter as tk
from tkinter import scrolledtext

import mss
from PIL import Image
from pynput import keyboard

import anthropic

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

MODEL = "claude-opus-4-8"

# The global hotkey that opens the snip tool. pynput hotkey syntax:
#   <ctrl>+.  ->  Ctrl + period   (the combo you asked for)
HOTKEY = "<ctrl>+."

SYSTEM_PROMPT = """\
You are an expert physics, biology, and mathematics tutor helping a student \
study and practice. You will be shown a screenshot of a single problem.

For every problem:
1. State clearly what is being asked and list the given information.
2. Show the full solution step by step. Do not skip algebra or reasoning.
3. For physics: name the principles/equations used and why they apply.
   For biology: explain the underlying concept, not just the term.
   For math: show each manipulation and state the rule used.
4. End with a clearly labelled "Answer:" line stating the final result with units.
5. Keep it readable: short sentences, plain text, no LaTeX markup — write math \
as plain text (use / for division, ^ for exponents, sqrt() for roots).

If the image is unclear or contains more than one problem, say so and ask the \
student to snip a single, clearer problem.

Your goal is for the student to understand the method, so explain as you go."""


# ---------------------------------------------------------------------------
# Anthropic client
# ---------------------------------------------------------------------------

def make_client():
    """Build the Anthropic client, surfacing a friendly error if no key is set."""
    if not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")):
        raise RuntimeError(
            "No API key found. Set the ANTHROPIC_API_KEY environment variable "
            "to your Claude API key before running this app."
        )
    return anthropic.Anthropic()


# ---------------------------------------------------------------------------
# Screen capture
# ---------------------------------------------------------------------------

def capture_region(bbox):
    """Grab a region of the screen and return it as PNG bytes.

    bbox is (left, top, right, bottom) in screen pixels.
    """
    left, top, right, bottom = bbox
    width, height = right - left, bottom - top
    if width <= 0 or height <= 0:
        return None
    with mss.mss() as sct:
        shot = sct.grab({"left": left, "top": top, "width": width, "height": height})
        img = Image.frombytes("RGB", shot.size, shot.rgb)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Region selector overlay (visible — a dimmed full-screen window you draw on)
# ---------------------------------------------------------------------------

class RegionSelector:
    """A translucent full-screen overlay; the user drags a box to select."""

    def __init__(self, root, on_done):
        self.on_done = on_done
        self.start_x = self.start_y = 0
        self.rect = None

        self.top = tk.Toplevel(root)
        self.top.attributes("-fullscreen", True)
        self.top.attributes("-alpha", 0.25)
        self.top.attributes("-topmost", True)
        self.top.configure(bg="black", cursor="crosshair")

        self.canvas = tk.Canvas(self.top, highlightthickness=0, bg="black")
        self.canvas.pack(fill="both", expand=True)
        self.canvas.create_text(
            self.top.winfo_screenwidth() // 2, 40,
            text="Drag a box over the problem   ·   Esc to cancel",
            fill="white", font=("Helvetica", 18),
        )

        self.canvas.bind("<ButtonPress-1>", self._press)
        self.canvas.bind("<B1-Motion>", self._drag)
        self.canvas.bind("<ButtonRelease-1>", self._release)
        self.top.bind("<Escape>", lambda e: self._cancel())

    def _press(self, event):
        self.start_x, self.start_y = event.x, event.y
        self.rect = self.canvas.create_rectangle(
            event.x, event.y, event.x, event.y, outline="#4ea1ff", width=2
        )

    def _drag(self, event):
        if self.rect is not None:
            self.canvas.coords(self.rect, self.start_x, self.start_y, event.x, event.y)

    def _release(self, event):
        x1, y1 = self.start_x, self.start_y
        x2, y2 = event.x, event.y
        # Translate canvas coords to absolute screen coords.
        ox, oy = self.top.winfo_rootx(), self.top.winfo_rooty()
        bbox = (
            ox + min(x1, x2), oy + min(y1, y2),
            ox + max(x1, x2), oy + max(y1, y2),
        )
        self.top.destroy()
        self.on_done(bbox)

    def _cancel(self):
        self.top.destroy()
        self.on_done(None)


# ---------------------------------------------------------------------------
# Result window (visible — small, corner, always on top)
# ---------------------------------------------------------------------------

class ResultWindow:
    """A small always-on-top window in the corner that shows the solution."""

    def __init__(self, root):
        self.top = tk.Toplevel(root)
        self.top.title("Snip & Solve")
        self.top.attributes("-topmost", True)

        w, h = 460, 540
        sw = self.top.winfo_screenwidth()
        self.top.geometry(f"{w}x{h}+{sw - w - 20}+20")  # top-right corner
        self.top.configure(bg="#1e1e1e")

        header = tk.Frame(self.top, bg="#1e1e1e")
        header.pack(fill="x", padx=10, pady=(8, 0))
        tk.Label(
            header, text="Snip & Solve — study helper",
            bg="#1e1e1e", fg="#9ecbff", font=("Helvetica", 11, "bold"),
        ).pack(side="left")

        self.text = scrolledtext.ScrolledText(
            self.top, wrap="word", bg="#1e1e1e", fg="#e8e8e8",
            insertbackground="#e8e8e8", font=("Menlo", 11), relief="flat",
            padx=10, pady=10,
        )
        self.text.pack(fill="both", expand=True, padx=6, pady=6)
        self.set_text("Solving…")

    def set_text(self, content):
        self.text.delete("1.0", "end")
        self.text.insert("1.0", content)

    def append(self, chunk):
        self.text.insert("end", chunk)
        self.text.see("end")


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

class App:
    def __init__(self):
        self.client = make_client()
        self.root = tk.Tk()
        self.root.withdraw()  # main window stays hidden; we use Toplevels

        # Thread-safe channel for streamed text from the API worker thread.
        self.stream_q = queue.Queue()
        self.busy = False

        # The hotkey listener runs on its own thread; it can't touch tkinter
        # directly, so it just schedules work back onto the main loop.
        self.listener = keyboard.GlobalHotKeys({HOTKEY: self._hotkey})
        self.listener.start()

        self.root.after(100, self._drain_queue)

    # -- hotkey -> region selector -------------------------------------------------

    def _hotkey(self):
        if self.busy:
            return
        self.root.after(0, self._open_selector)

    def _open_selector(self):
        if self.busy:
            return
        RegionSelector(self.root, self._on_region)

    def _on_region(self, bbox):
        if not bbox:
            return
        png = capture_region(bbox)
        if not png:
            return
        self.busy = True
        self.result = ResultWindow(self.root)
        self.result.set_text("")
        threading.Thread(target=self._solve, args=(png,), daemon=True).start()

    # -- API call (worker thread) --------------------------------------------------

    def _solve(self, png_bytes):
        b64 = base64.standard_b64encode(png_bytes).decode("utf-8")
        try:
            with self.client.messages.stream(
                model=MODEL,
                max_tokens=8000,
                thinking={"type": "adaptive", "display": "summarized"},
                output_config={"effort": "high"},
                system=SYSTEM_PROMPT,
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": b64,
                            },
                        },
                        {
                            "type": "text",
                            "text": "Solve this problem and explain each step.",
                        },
                    ],
                }],
            ) as stream:
                for text in stream.text_stream:
                    self.stream_q.put(("chunk", text))
            self.stream_q.put(("done", None))
        except anthropic.APIError as e:
            self.stream_q.put(("error", f"\n\n[API error: {e}]"))
        except Exception as e:  # noqa: BLE001 - surface anything to the UI
            self.stream_q.put(("error", f"\n\n[Error: {e}]"))

    # -- pump streamed text onto the UI (main thread) ------------------------------

    def _drain_queue(self):
        try:
            while True:
                kind, payload = self.stream_q.get_nowait()
                if kind == "chunk":
                    self.result.append(payload)
                elif kind == "error":
                    self.result.append(payload)
                    self.busy = False
                elif kind == "done":
                    self.busy = False
        except queue.Empty:
            pass
        self.root.after(100, self._drain_queue)

    def run(self):
        print(f"Snip & Solve is running. Press {HOTKEY} to snip a problem.")
        print("(Keep this terminal open. Press Ctrl+C here to quit.)")
        try:
            self.root.mainloop()
        finally:
            self.listener.stop()


if __name__ == "__main__":
    App().run()
