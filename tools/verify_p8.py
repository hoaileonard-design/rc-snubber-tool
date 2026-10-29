"""Verify the existing P6 workflow without changing its original evidence directory."""
import hashlib
import json
import sys
from pathlib import Path
from tkinter import messagebox

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import config
from app.app import SnubberApp
from app.core.sweep_data import SweepDataset


def verify(output_dir=None):
    out = Path(output_dir) if output_dir else ROOT / "verification" / "p8"
    out.mkdir(parents=True, exist_ok=True)
    errors = []
    messagebox.showerror = lambda title, text, **kw: errors.append((title, text))
    messagebox.showwarning = lambda title, text, **kw: errors.append((title, text))
    messagebox.showinfo = lambda *args, **kw: None
    application = SnubberApp()
    application.withdraw()
    try:
        w = application.waveform_tab
        w._load_demo()
        assert not errors, errors
        assert w.metrics_a.v_peak > 38.84 and w.metrics_a.settling_censored
        assert not w.metrics_b.settling_censored
        assert w.parasitics and abs(w.parasitics.Lp_H / 100e-9 - 1) < .02
        w.send_to_calculator()
        assert application.tabview.get() == config.TAB_CALCULATOR
        application.calculator_tab._on_calculate()
        assert application.calculator_tab.last_result is not None
        w.send_to_optimizer()
        assert application.tabview.get() == config.TAB_OPTIMIZER
        o = application.optimizer_tab
        assert float(o.entry_vin.get()) == 24  # plateau không ghi đè Vin
        o._load_dataset(ROOT / "examples" / "p6_buck" / "L100_Rload10_grid.csv")
        o.entry_w_power.set(1)
        o.entry_w_cost.set(0)
        o.entry_w_size.set(0)
        o._on_run_optimization()
        assert not errors, errors
        assert o.last_result is not None
        assert np.isclose(o.last_result.R_opt, 10)
        assert np.isclose(o.last_result.C_opt, 4.7e-9, rtol=1e-10, atol=0)
        o.figure.savefig(out / "optimizer_P6.png", dpi=130)
        w.figure.savefig(out / "waveform_P6.png", dpi=130)
        dataset, result, criteria, circuit, node = o.result_snapshot
        dataset.export(out / "BAO_CAO_DEMO_P6.md", result, criteria, circuit, node)
        rows = []
        for path in sorted((ROOT / "examples" / "p6_buck").glob("*_grid.csv")):
            data = SweepDataset.load(path)
            result = data.select(data.metadata["v_target"], 200, (1, 0, 0))
            rows.append(dict(case=path.stem, R_ohm=result.R_opt, C_nF=result.C_opt * 1e9,
                             Vpeak=result.V_peak_opt, ts_ns=result.settling_time_opt * 1e9,
                             Psn_W=result.P_loss_opt, n_feasible=result.n_feasible,
                             evidence=data.ranked_rows(result).query("selected").iloc[0].get("evidence")))
        report = dict(gui="Constructed CTk app; invoked original analysis, transfer, selection and rendering callbacks; no manual Windows clicks",
                      waveform=dict(Vpeak=w.metrics_a.v_peak, f0_MHz=w.metrics_a.f_ring / 1e6,
                                    zeta=w.metrics_a.zeta, censored=w.metrics_a.settling_censored,
                                    Lp_nH=w.parasitics.Lp_H * 1e9, Cp_pF=w.parasitics.Cp_F * 1e12),
                      cases=rows, errors=errors)
        (out / "verification.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        manifest = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                    for folder in (ROOT / "app", ROOT / "tests", ROOT / "examples") for p in folder.rglob("*")
                    if p.is_file() and p.suffix in (".py", ".json", ".csv")}
        (out / "source_hashes.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False, indent=2))
    finally:
        application.destroy()


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    verify(sys.argv[1] if len(sys.argv) > 1 else None)
