# ShopGuard

Offline desktop app that finds suspected shoplifting in recorded CCTV footage.
Upload a video, and ShopGuard lists the moments worth reviewing, with snapshots,
confidence scores, a clickable timeline, saved clips and an exportable report.
Everything runs on the local computer: no internet, no cloud APIs.

> "ShopGuard" is a placeholder name. Change `APP_NAME` in `shopguard/config.py`.

---

## 1. Run it

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows  (macOS/Linux: source .venv/bin/activate)
pip install -r requirements.txt
```

Copy your trained model into `models/best.onnx` (or choose it later in Settings), then:

```bash
python main.py
```

Run the tests with `pytest`.

---

## 2. How the project is organised

```
main.py                    Starts the app: logging, style sheet, main window
ShopGuard.spec             PyInstaller build recipe
models/best.onnx           Your trained model (not included)
shopguard/
  config.py                App name, constants and saved user settings
  core/                    Detection engine. No UI code at all.
    detector.py            Runs the ONNX model on one frame (letterbox, decode, NMS)
    video.py               Reading video info and frames; time/size formatting
    analyzer.py            Whole-video loop: sample frames → detect → incidents → snapshots
    incidents.py           Temporal smoothing: per-frame scores → incidents
    clips.py               Saving incident clips as MP4
    report.py              Self-contained HTML report
    common.py              Cancel/progress types shared by long operations
  ui/                      Everything you see
    main_window.py         Sidebar + pages; runs the Upload → Processing → Results flow
    theme.py               All colours and the style sheet (QSS)
    icons.py               Line icons drawn from inline SVG
    tasks.py               BackgroundTask: runs slow work off the UI thread
    pages/                 upload_page, processing_page, results_page, settings_page
    widgets/               drop_zone, timeline, incident_card, common building blocks
tests/                     Unit tests for the engine
```

The most important design rule is that **`core/` knows nothing about the UI**.
That's what lets you:
- test the detection logic with `pytest` without opening a window
- swap the model, or later add a command-line version, without touching the UI
- change the UI freely without breaking detection

---

## 3. Desktop development concepts used here

If you're new to desktop apps, these four ideas explain almost all of the code.

**1. Widgets and layouts.** Everything on screen is a widget (`QLabel`, `QPushButton`,
`QFrame`...). Widgets are arranged with layouts (`QVBoxLayout` stacks them vertically,
`QHBoxLayout` horizontally) instead of fixed pixel positions, so the window resizes properly.
`ui/widgets/common.py` has helpers (`vbox`, `hbox`, `label`, `button`) that keep page code short.

**2. Signals and slots.** Widgets talk to each other through signals instead of calling
each other directly. For example, `UploadPage` emits `analysisRequested(video)`, and
`MainWindow` connects it to `start_analysis`. A page never needs to know who is listening,
so pages stay independent.

**3. Never block the UI thread.** If a slow task runs on the main thread, the window freezes
and Windows shows "Not responding". `ui/tasks.py` runs analysis and clip saving on a `QThread`.
The worker reports back through signals (`progress`, `succeeded`, `failed`, `cancelled`),
which Qt safely delivers to the main thread. Cancelling works by setting a flag that the
analysis loop checks on every frame.

**4. Styling with QSS.** `ui/theme.py` holds a style sheet, which is CSS-like rules for Qt.
Widgets get an `objectName` (`#Card`, `#H1`) or a property (`variant="primary"`) that the
style sheet targets. To restyle the app, edit `theme.py` only.
Gotcha: Qt reads 8-digit hex colours as `#AARRGGBB`, so use `rgba(r, g, b, a)` for transparency.

---

## 4. How detection works

1. **Sampling.** Only some frames are analysed (5 per second by default, set in Settings).
   Skipped frames use `grab()`, which doesn't decode the image, so they're nearly free.
2. **Skipping empty scenes.** If the previous frame had no people and almost nothing
   changed, the model is skipped. If anyone is in view, every sampled frame is analysed,
   because concealing an item can involve very little movement.
3. **Detection.** `Detector` letterboxes the frame to 640×640 the same way Ultralytics does
   in training, runs ONNX Runtime on the CPU, and decodes the output. It supports both
   NMS-free (end-to-end) and classic YOLO output layouts, and reads class names from the
   model's metadata.
4. **Temporal smoothing.** A frame is suspicious if its best `shoplifting` score passes the
   sensitivity threshold. An incident needs several suspicious frames (about 0.6 s worth)
   within 2 s of each other, which filters out one-frame flickers. Incidents are padded by
   1.5 s on each side so clips show context.
5. **Results.** For each incident, the frame with the highest confidence is saved as a
   snapshot. Times, confidences and severity (High ≥ 75%, Medium ≥ 50%) appear in the app
   and the report.

Tuning knobs:

| What | Where |
|---|---|
| Sensitivity thresholds | `SENSITIVITY_THRESHOLDS` in `config.py` |
| Frames needed, gap, padding | `group_incidents(...)` call in `core/analyzer.py` |
| Severity cut-offs | `Incident.severity` in `core/incidents.py` |
| Empty-scene skipping | `STILL_*` constants in `core/analyzer.py` |

---

## 5. Build a Windows app for release

Build on Windows, in a **clean virtual environment** containing only `requirements.txt`.
If PyTorch, Ultralytics or full `opencv-python` are installed, the build gets much bigger.

```bash
pyinstaller ShopGuard.spec
```

The output is `dist/ShopGuard/`. Zip that folder, or turn it into a proper installer with
[Inno Setup](https://jrsoftware.org/isinfo.php) (free), which adds a Start Menu shortcut
and an uninstaller.

Before releasing, test on a low-end PC without a GPU, and with real footage from the
DVR brands shops actually use. Some DVRs export `.dav` or other formats that need
converting to MP4 first.

---

## 6. Where files go

| What | Location |
|---|---|
| Settings | Windows registry (`HKCU\Software\ShopGuard\ShopGuard`), via `QSettings` |
| Logs | `%APPDATA%\ShopGuard\ShopGuard\shopguard.log` |
| Snapshots for each analysis | `%APPDATA%\ShopGuard\ShopGuard\runs\<date_time>\` |
| Saved clips and reports | `Videos\ShopGuard\<video name>\` (changeable in Settings) |

---

## 7. Ideas for the next version

- **History page:** save each `AnalysisResult` (e.g. as JSON) and list past analyses
- **Batch mode:** queue several videos and analyse them one after another
- **Light theme:** add a second colour set in `theme.py`
- **Sinhala and Tamil:** wrap UI strings with `self.tr()` and use Qt Linguist
- **Faster inference:** try OpenVINO, or INT8 quantisation of the ONNX model
- **Incident types:** once the model has more classes, map them to labels in `Incident.label`

---

## Credits

Icon shapes are based on [Feather Icons](https://feathericons.com) (MIT licence).
Check the licences of your model and training data before release; see the training notebook.
