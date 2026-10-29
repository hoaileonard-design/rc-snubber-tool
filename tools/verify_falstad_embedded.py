"""Exercise the real Windows child WebView and the existing desktop analysis."""

import ctypes
import json
import sys
import time
import webbrowser
from pathlib import Path
from tkinter import messagebox

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app import config
from app.app import SnubberApp


def verify():
    output = ROOT / "verification" / "falstad_embedded"
    output.mkdir(parents=True, exist_ok=True)
    errors = []
    messagebox.showerror = lambda *args, **kw: errors.append(args)
    messagebox.showwarning = lambda *args, **kw: errors.append(args)
    webbrowser.open_new_tab = lambda *args: (_ for _ in ()).throw(AssertionError("External browser opened"))
    app = SnubberApp()
    app.title("Snubber — kiểm tra bàn mạch nhúng")
    app.report_callback_exception = lambda *args: errors.append([str(x) for x in args])
    tab = app.circuit_tab
    tab._capture_root = output / "captures"

    def pump(predicate, timeout=40):
        deadline = time.monotonic() + timeout
        outcome = []
        def check():
            try:
                if errors:
                    raise AssertionError(errors)
                if predicate():
                    outcome.append(True)
                    app.quit()
                    return
                if time.monotonic() >= deadline:
                    raise TimeoutError(f"Embedded WebView timed out; {tab.status.cget('text')}; {errors}")
                app.after(15, check)
            except Exception as exc:
                outcome.append(exc)
                app.quit()
        app.after(15, check)
        app.mainloop()
        if outcome and isinstance(outcome[0], Exception):
            raise outcome[0]

    def js(script):
        result = []
        tab.webview.eval_js_with_callback(script, result.append, on_error=lambda e: errors.append(str(e)))
        pump(lambda: bool(result))
        return json.loads(result[0])

    def select_tab(name):
        # CTkTabview defers hiding the previous page by 100 ms.
        settle_at = time.monotonic() + .2
        pump(lambda: time.monotonic() >= settle_at)
        app.tabview.set(name)
        settle_at = time.monotonic() + .2
        pump(lambda: time.monotonic() >= settle_at)

    def ready():
        pump(lambda: tab.webview is not None and tab.webview.ready)
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            if js("Boolean(window.snubberBridge && window.snubberBridge.getSnapshot().ready)"):
                return
            app.update()
            time.sleep(.05)
        print(js("({url:location.href, text:document.body?.innerText, iframe:document.querySelector('iframe')?.contentDocument?.body?.innerText})"), flush=True)
        raise TimeoutError("CircuitJS did not become ready inside WebView")

    def child_windows():
        children = []
        callback_type = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
        @callback_type
        def collect(hwnd, _):
            name = ctypes.create_unicode_buffer(256)
            ctypes.windll.user32.GetClassNameW(ctypes.c_void_p(hwnd), name, 256)
            children.append(dict(hwnd=hwnd, window_class=name.value,
                                 visible=bool(ctypes.windll.user32.IsWindowVisible(ctypes.c_void_p(hwnd)))))
            return True
        ctypes.windll.user32.EnumChildWindows(ctypes.c_void_p(tab.web_host.winfo_id()), collect, 0)
        return children

    try:
        settle_at = time.monotonic() + .25
        pump(lambda: time.monotonic() >= settle_at)
        select_tab(config.TAB_CIRCUIT)
        settle_at = time.monotonic() + .25
        pump(lambda: time.monotonic() >= settle_at)
        tab.open_circuit()
        print("opened", flush=True)
        ready()
        print("ready", flush=True)
        layout = js("(() => {const f=document.querySelector('iframe').getBoundingClientRect();return {width:f.width,height:f.height,bottom:f.bottom,viewportHeight:innerHeight,controlsScroll:getComputedStyle(document.querySelector('.controls')).overflowY};})()")
        assert layout["width"] > 500 and layout["height"] > 350, layout
        assert layout["bottom"] <= layout["viewportHeight"] and layout["controlsScroll"] == "auto", layout
        children = child_windows()
        assert children and any(c["visible"] for c in children), children
        initial_width = js("innerWidth")
        app.geometry("1200x800")
        pump(lambda: js("innerWidth") != initial_width)
        resized_width = js("innerWidth")
        print("resized", flush=True)
        assert resized_width < initial_width, (initial_width, resized_width)
        select_tab(config.TAB_CALCULATOR)
        pump(lambda: not tab.web_host.winfo_ismapped())
        assert not any(c["visible"] for c in child_windows()), child_windows()
        select_tab(config.TAB_CIRCUIT)
        pump(lambda: tab.web_host.winfo_ismapped())
        ready()
        print("hide/show passed", flush=True)
        app.geometry("1440x900")
        results = []
        for role in ("before", "after", "test_cap"):
            print(f"recording {role}", flush=True)
            select_tab(config.TAB_CIRCUIT)
            pump(lambda: tab.web_host.winfo_ismapped())
            ready()
            js(f"(() => {{const e=document.querySelector('#variant'); e.value='{role}'; e.dispatchEvent(new Event('change')); document.querySelector('#record').click(); return true;}})()")
            pump(lambda: tab.last_capture is not None and tab.last_capture["metadata"]["role"] == role, 60)
            results.append(dict(role=role, path=tab.last_capture["path"]))
            assert app.tabview.get() == config.TAB_WAVEFORM
        wave = app.waveform_tab
        assert wave.metrics_a and wave.metrics_b and wave.parasitics
        assert wave.metrics_a.v_peak > 45 and wave.metrics_b.v_peak < 30
        assert abs(wave.parasitics.Lp_H / 100e-9 - 1) < .05
        assert abs(wave.parasitics.Cp_F / 274e-12 - 1) < .05
        wave.figure.savefig(output / "waveforms.png", dpi=130)
        metrics = dict(before_peak_V=wave.metrics_a.v_peak, after_peak_V=wave.metrics_b.v_peak,
                       Lp_nH=wave.parasitics.Lp_H * 1e9, Cp_pF=wave.parasitics.Cp_F * 1e12)
        tab.close()
        assert tab.webview is None and tab.bridge is None
        select_tab(config.TAB_CIRCUIT)
        app.update()
        tab.open_circuit()
        ready()
        assert not errors, errors
        report = dict(status="passed", native_child_windows=children, layout=layout, initial_width=initial_width,
                      resized_width=resized_width, hide_show="passed", close_reopen="passed",
                      captures=results, metrics=metrics, callback_errors=errors,
                      scope="Real embedded Windows WebView2; DOM controls, native child/visibility/resize and desktop analysis checked. No physical mouse test or hardware validation.")
        (output / "result.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)
    finally:
        app.destroy()


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    verify()
