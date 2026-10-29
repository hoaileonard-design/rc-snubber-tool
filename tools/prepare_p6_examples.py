"""Sao chép đối chứng P6 vào app; chỉ đọc nguồn, không chạy/sửa mô phỏng."""

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from spicelib import RawRead

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT.parent / "LTspice" / "Driver" / "khao_sat_p6"
DEST = ROOT / "examples" / "p6_buck"


def prepare():
    DEST.mkdir(parents=True, exist_ok=True)
    provenance = {}
    for path in sorted(SOURCE.glob("*_grid.csv")):
        case = path.stem.removesuffix("_grid")
        details_path = SOURCE / f"{case}_result.json"
        if not details_path.exists():
            continue
        details = json.loads(details_path.read_text(encoding="utf-8"))
        frame = pd.read_csv(path, encoding="utf-8-sig")
        frame["case"] = case
        frame["topology"] = "Buck"
        frame["node"] = "drain, sw"
        frame["evidence"] = "LTspice sàng lọc 1 ns; chưa kiểm tra giữ dải 500 ns cho từng điểm"
        selected = details["selected"]
        # Kể cả điểm KHÔNG đạt khi chạy mịn: không quay lại dùng số sàng lọc đẹp hơn.
        for candidate in [*details["fine_candidates"], selected]:
            mask = np.isclose(frame.R_ohm, candidate["R_ohm"], rtol=1e-10) & np.isclose(
                frame.C_F, candidate["C_F"], rtol=1e-10, atol=0)
            assert mask.sum() == 1
            for key, val in candidate.items():
                if key in frame:
                    frame.loc[mask, key] = val
            frame.loc[mask, "evidence"] = "LTspice 0.5 ns; chưa đối chiếu hội tụ và giữ dải cho điểm này"
        mask = np.isclose(frame.R_ohm, selected["R_ohm"], rtol=1e-10) & np.isclose(
            frame.C_F, selected["C_F"], rtol=1e-10, atol=0)
        frame.loc[mask, "evidence"] = "LTspice 0.5 ns; đã đối chiếu 0.25 ns và giữ dải ±5% 500 ns (P6)"
        frame.to_csv(DEST / path.name, index=False, encoding="utf-8-sig")
        metadata = dict(circuit=f"Buck 24 V, Lstray={details['Lstray_nH']} nH, tải {details['Rload_ohm']} Ω",
                        topology="Buck", node="drain – sw", source="P6, mô hình chức năng gần đúng",
                        v_target=1.15 * selected["Vplateau_V"], ts_max_ns=200,
                        settling_band=0.05, settling_hold_ns=500,
                        operating_point=dict(Vin=24, Lout_uH=220, fsw_kHz=20, duty_percent=50.84926657397271),
                        evidence_scope="Chỉ mạch Buck; sàng lọc và điểm chọn có mức kiểm chứng khác nhau",
                        source_csv_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                        source_json_sha256=hashlib.sha256(details_path.read_bytes()).hexdigest())
        metadata["selected_reference"] = {key: selected[key] for key in ("R_ohm", "C_F")}
        (DEST / path.with_suffix(".json").name).write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        provenance[case] = metadata
    duty = 0.5084926657397271
    command = .01425 - 50e-6 + duty * 50e-6 + 20e-9
    for tag, name in (("none", "before"), ("add470p", "with_470pF"), ("fine_R10_C4.7n", "after_RC")):
        raw_path = SOURCE / f"L100_Rload10_{tag}.raw"
        raw = RawRead(str(raw_path), verbose=False)
        t = np.abs(raw.get_trace("time").get_wave())
        if t[-1] < .01425 - 1e-8:
            t += .01425 - t[-1]
        v = raw.get_trace("V(drain)").get_wave() - raw.get_trace("V(sw)").get_wave()
        mask = (t >= command - 100e-9) & (t <= command + 5e-6)
        pd.DataFrame({"Time": t[mask] - command, "V(drain,sw)": v[mask]}).to_csv(DEST / f"{name}.csv", index=False)
        provenance[name] = dict(raw=str(raw_path), sha256=hashlib.sha256(raw_path.read_bytes()).hexdigest())
    (DEST / "provenance.json").write_text(json.dumps(provenance, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Prepared {len(list(DEST.glob('*_grid.csv')))} P6 cases and 3 waveform files")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    prepare()
