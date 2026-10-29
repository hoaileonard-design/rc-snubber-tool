"""Run real CircuitJS in a fresh browser, receive three captures in existing CTk app."""

import json
import math
import subprocess
import sys
from pathlib import Path
from tkinter import messagebox

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.app import SnubberApp


def verify():
    output = ROOT / "verification" / "falstad"
    output.mkdir(parents=True, exist_ok=True)
    errors = []
    messagebox.showerror = lambda title, text, **kw: errors.append([title, text])
    messagebox.showwarning = lambda title, text, **kw: errors.append([title, text])
    app = SnubberApp()
    app.withdraw()
    from app.core.circuit_bridge import CircuitBridge
    tab = app.circuit_tab
    tab.bridge = CircuitBridge(tab._web_root, tab._vendor_root, output / "captures", tab._state())
    url = tab.bridge.start()
    runtime = Path.home() / ".local" / "share" / "rea-6.8.0"
    try:
        process = subprocess.run([str(runtime / "node" / "node.exe"), str(ROOT / "tools" / "verify_falstad_browser.mjs"),
                                  url, str(output), str(runtime / "node_modules" / "rea-agents"),
                                  r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"],
                                 cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=150)
        (output / "browser_stdout.txt").write_text(process.stdout, encoding="utf-8")
        (output / "browser_stderr.txt").write_text(process.stderr, encoding="utf-8")
        assert process.returncode == 0, process.stderr[-6000:]
        captures = []
        while capture := tab.bridge.pop_capture():
            tab.accept_capture(capture)
            captures.append(capture)
        assert len(captures) == 3, len(captures)
        assert not errors, errors
        w = app.waveform_tab
        assert w.metrics_a and w.metrics_b and w.parasitics
        assert w.metrics_a.v_peak > 45  # RLC step demo, NOT P6's Buck waveform.
        assert w.metrics_b.v_peak < w.metrics_a.v_peak
        assert abs(w.parasitics.Lp_H / 100e-9 - 1) < .05
        assert abs(w.parasitics.Cp_F / 274e-12 - 1) < .05
        assert all(c["metadata"]["source"] == CircuitBridge.SOURCE for c in captures)
        assert len({c["metadata"]["context_id"] for c in captures}) == 1
        w.figure.savefig(output / "waveforms_received_in_app.png", dpi=130)
        report = dict(status="passed", captures=[dict(path=c["path"], sha256=c["sha256"], role=c["metadata"]["role"]) for c in captures],
                      before_peak_V=w.metrics_a.v_peak, after_peak_V=w.metrics_b.v_peak,
                      before_frequency_MHz=w.metrics_a.f_ring / 1e6,
                      Lp_nH=w.parasitics.Lp_H * 1e9, Cp_pF=w.parasitics.Cp_F * 1e12,
                      desktop_callback_errors=errors,
                      scope="Real local CircuitJS v115 browser interaction and CTk receive/analyze; equivalent RLC illustration, not P6/hardware")
        (output / "integration_result.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False, indent=2))
    finally:
        app.destroy()


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    verify()
