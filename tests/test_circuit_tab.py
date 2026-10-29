"""Guard existing P6 inputs against silent mixing with interactive captures."""

from pathlib import Path
from tkinter import messagebox

import numpy as np
import pytest

from app.app import SnubberApp


@pytest.fixture(scope="module")
def application():
    # The desktop product owns one Tk root per process.
    monkeypatch = pytest.MonkeyPatch()
    messages = []
    monkeypatch.setattr(messagebox, "showerror", lambda *args, **kwargs: messages.append(args))
    app = SnubberApp()
    app.withdraw()
    yield app, messages
    app.destroy()
    monkeypatch.undo()


def _capture(tmp_path, role="before", context="rlc-example"):
    t = np.linspace(0, 4e-6, 8000)
    tau = np.maximum(t - 200e-9, 0)
    v = np.where(t < 200e-9, 0, 24 + 12 * np.exp(-1e6 * tau) * np.cos(2 * np.pi * 20e6 * tau))
    path = tmp_path / f"{role}.csv"
    np.savetxt(path, np.column_stack([t, v]), delimiter=",", header="Time,Voltage", comments="")
    return dict(path=str(path), metadata=dict(role=role, context_id=context, plateau_V=24))


def test_falstad_replaces_previous_p6_context(application, tmp_path):
    app, errors = application
    wave = app.waveform_tab
    wave._load_demo()
    assert wave.path_b and wave.path_cap
    app.circuit_tab.accept_capture(_capture(tmp_path))
    assert not errors
    assert wave.path_a and wave.path_b is None and wave.path_cap is None
    assert wave.external_context == "rlc-example"
    assert "Falstad" in wave.warning_label.cget("text")
    wave._on_analyze()
    assert "Falstad" in wave.warning_label.cget("text")  # retained on re-analysis


def test_p6_reload_cannot_mix_with_later_falstad_file(application, tmp_path):
    app, errors = application
    wave = app.waveform_tab
    app.circuit_tab.accept_capture(_capture(tmp_path))
    wave._load_demo()
    assert wave.external_context is None and wave.source_note is None
    app.circuit_tab.accept_capture(_capture(tmp_path, role="after"))
    assert not errors
    assert wave.path_a is None and wave.path_cap is None and wave.path_b


def test_copy_selected_rc_keeps_demo_parasitics(application):
    app, _ = application
    tab = app.circuit_tab
    tab.entries["Lp_H"].set(220)
    app.calculator_tab.last_result = dict(R_sn=15, C_sn=6.8e-9)
    tab.load_selected()
    assert float(tab.entries["R_ohm"].get()) == 15
    assert float(tab.entries["C_F"].get()) == pytest.approx(6800)
    assert float(tab.entries["Lp_H"].get()) == 220
