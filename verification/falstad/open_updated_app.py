"""Open the existing desktop app on its newly added circuit tab."""
import sys
import json
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from app.app import SnubberApp
from app import config

app = SnubberApp()
app.title(config.APP_TITLE + " — Falstad trong ứng dụng")

def open_embedded():
    app.tabview.set(config.TAB_CIRCUIT)
    app.after(200, app.circuit_tab.open_circuit)

def check_ready(attempt=0):
    web = app.circuit_tab.webview
    if web is not None and web.ready:
        def received(value):
            snapshot = json.loads(value)
            if snapshot and snapshot.get("ready"):
                (Path(__file__).parent.parent / "falstad_embedded" / "launch_state.json").write_text(
                    json.dumps(dict(pid=os.getpid(), title=app.title(), tab=app.tabview.get(),
                                    embedded_ready=True, snapshot=snapshot), ensure_ascii=False, indent=2), encoding="utf-8")
            elif attempt < 120:
                app.after(500, lambda: check_ready(attempt + 1))
        web.eval_js_with_callback("window.snubberBridge?.getSnapshot() || null", received)
    elif attempt < 120:
        app.after(500, lambda: check_ready(attempt + 1))

app.after(300, open_embedded)
app.after(1000, check_ready)
app.mainloop()
