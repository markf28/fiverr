# Snip & Solve — study helper

A small desktop tool for **studying and practicing** physics, biology, and math.

Press a hotkey, drag a box over a problem anywhere on your own screen (a PDF, a
textbook photo, a practice set), and Claude returns a **full worked solution
with the reasoning explained**, in a small window in the corner of your screen.

It runs in a **normal, visible window** so you can learn the method as you
practice. It is built for studying before an exam — not for running covertly
inside proctored or locked-down test software.

## What it does

- Global hotkey **Ctrl + .** opens a dimmed overlay.
- Drag a box over a single problem → it screenshots that region.
- The image goes to Claude's vision model, which **reads diagrams, equations,
  and graphs directly** (no OCR step) and solves it step by step.
- The worked solution streams into a small always-on-top corner window.

## Subjects

Strong at **physics** (named principles + equations), **biology** (the concept
behind the term), and **math** (every manipulation shown, with the rule used).
Each answer ends with a clearly labelled `Answer:` line.

## Setup

1. Install Python 3.9+.
2. Install the dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Set your Claude API key (get one at https://console.anthropic.com):

   ```bash
   export ANTHROPIC_API_KEY="sk-ant-..."      # macOS / Linux
   # setx ANTHROPIC_API_KEY "sk-ant-..."      # Windows (new terminal after)
   ```

4. Run it:

   ```bash
   python study_helper.py
   ```

Keep the terminal open. Press **Ctrl + .** to snip a problem; press **Esc**
during selection to cancel; press **Ctrl + C** in the terminal to quit.

## Platform notes

- **macOS:** the first run will prompt for **Screen Recording** and
  **Accessibility** permissions (System Settings → Privacy & Security). Grant
  both to your terminal/Python, then restart the app — the global hotkey and
  screen capture need them.
- **Linux:** works on X11. On Wayland, global hotkeys and screen capture via
  `pynput`/`mss` may be limited; an X11 session is the smoother path.
- **Windows:** runs as-is.

## Customizing

- Change the hotkey: edit `HOTKEY` in `study_helper.py` (pynput syntax, e.g.
  `"<ctrl>+<alt>+s"`).
- Change the model: edit `MODEL` (defaults to `claude-opus-4-8`).
- Tweak how it explains: edit `SYSTEM_PROMPT`.

## Cost

Each snip is one API call to Claude with one image plus the solution. You pay
Anthropic's standard per-token rates for what you use.
