"use strict";

(() => {
  const $ = id => document.getElementById(id);
  const frame = $("simulator");
  const MAX_POINTS = 20000;
  const numericIds = ["r_ohm", "c_nf", "lp_nh", "cp_pf", "vin_v", "added_pf"];
  let sim = null;
  let capture = null;
  let ownImportPending = false;
  let lastSent = null;
  let watchdog = null;
  let startupTimer = null;

  function setStatus(message, phase = "ready") {
    $("status").textContent = message;
    $("status").dataset.phase = phase;
  }

  function showError(error) {
    setStatus(error && error.message ? error.message : String(error), "error");
  }

  function number(id, label) {
    const value = Number($(id).value);
    if (!$(id).value.trim() || !Number.isFinite(value) || value <= 0) {
      throw new Error(`${label} phải là số hữu hạn lớn hơn 0.`);
    }
    return value;
  }

  function readParameters() {
    return {
      R_ohm: number("r_ohm", "R"),
      C_F: number("c_nf", "C snubber") * 1e-9,
      Lp_H: number("lp_nh", "Lp") * 1e-9,
      Cp_F: number("cp_pf", "Cp") * 1e-12,
      Vin: number("vin_v", "Bước nguồn"),
      added_cap_F: number("added_pf", "Tụ thử") * 1e-12
    };
  }

  const isDemo = () => $("source_mode").value === "demo";

  function busy(active) {
    $("record").disabled = active || !sim;
    $("stop").disabled = !active;
    $("source_mode").disabled = active;
    $("variant").disabled = active;
    $("positive_node").disabled = active;
    $("negative_node").disabled = active;
    $("duration_ns").disabled = active;
    $("dt_ns").disabled = active;
    $("custom_context").disabled = active;
    numericIds.forEach(id => { $(id).disabled = active || !isDemo(); });
    $("load_app").disabled = active || !isDemo();
    $("rebuild").disabled = active || !isDemo();
  }

  function stopRecording(message = "Đã dừng. Bản ghi chưa gửi về app.") {
    capture = null;
    if (watchdog) clearTimeout(watchdog);
    watchdog = null;
    if (sim) sim.setSimRunning(false);
    busy(false);
    setStatus(message, "stopped");
  }

  function demoCircuit(parameters, variant) {
    const cp = parameters.Cp_F + (variant === "test_cap" ? parameters.added_cap_F : 0);
    const lines = [
      "$ 1 5e-10 10.20027730826997 50 50 50 5e-12",
      "418 96 96 64 96 0 1 40 0 0 0 0.5 drive",
      "r 96 96 176 96 0 0.05",
      `l 176 96 272 96 0 ${parameters.Lp_H} 0 0`,
      `c 272 96 272 224 0 ${cp} 0 0`,
      "g 272 224 272 256 0 0",
      "207 272 96 272 64 4 OUT"
    ];
    if (variant === "after") lines.push(
      `r 272 96 384 96 0 ${parameters.R_ohm}`,
      `c 384 96 384 224 0 ${parameters.C_F} 0 0`,
      "w 384 224 272 224 0"
    );
    return lines.join("\n") + "\n";
  }

  function rebuildDemo(quiet = false) {
    if (!sim) throw new Error("CircuitJS chưa sẵn sàng.");
    if (!isDemo()) throw new Error("Mạch tự vẽ được sửa trực tiếp trong CircuitJS; app không thay linh kiện tự động.");
    if (capture) stopRecording();
    const parameters = readParameters();
    const dt = number("dt_ns", "Bước thời gian") * 1e-9;
    sim.setSimRunning(false);
    ownImportPending = true;
    sim.importCircuit(demoCircuit(parameters, $("variant").value), false);
    sim.setMaxTimeStep(dt);
    sim.setExtVoltage("drive", 0);
    refreshNodes();
    $("positive_node").value = "label:OUT";
    $("negative_node").value = "ground";
    if (!quiet) setStatus("Đã dựng mẫu. Bấm Ghi và gửi để chạy một lần và chuyển dạng sóng.");
  }

  function refreshNodes() {
    if (!sim) return;
    const options = [{ value: "ground", label: "GND · 0 V" }];
    const labels = new Set();
    const elements = sim.getElements();
    elements.forEach((element, index) => {
      const type = element.getType();
      if (type === "LabeledNodeElm" && typeof element.getLabelName === "function") {
        const label = element.getLabelName();
        if (label && !labels.has(label)) {
          labels.add(label);
          options.push({ value: `label:${label}`, label });
        }
      }
      const count = element.getPostCount();
      for (let post = 0; post < count; post++) {
        options.push({ value: `element:${index}:${post}`, label: `${index + 1} · ${type.replace(/Elm$/, "")} · chân ${post + 1}` });
      }
    });
    for (const id of ["positive_node", "negative_node"]) {
      const select = $(id);
      const previous = select.value;
      select.replaceChildren();
      options.forEach(option => select.add(new Option(option.label, option.value)));
      const fallback = id === "positive_node" && isDemo() && options.some(option => option.value === "label:OUT") ? "label:OUT" : "ground";
      select.value = options.some(option => option.value === previous) ? previous : fallback;
    }
  }

  function voltageAt(selection) {
    if (selection === "ground") return 0;
    if (selection.startsWith("label:")) return Number(sim.getNodeVoltage(selection.slice(6)));
    const parts = selection.split(":");
    if (parts.length !== 3 || parts[0] !== "element") throw new Error("Nút đo không hợp lệ; chọn lại sau khi sửa mạch.");
    const element = sim.getElements()[Number(parts[1])];
    const post = Number(parts[2]);
    if (!element || !Number.isInteger(post) || post < 0 || post >= element.getPostCount()) {
      throw new Error("Sơ đồ đã đổi; chọn lại hai nút đo.");
    }
    return Number(element.getVoltage(post));
  }

  async function hashText(text) {
    const bytes = new TextEncoder().encode(text);
    const result = await crypto.subtle.digest("SHA-256", bytes);
    return Array.from(new Uint8Array(result), byte => byte.toString(16).padStart(2, "0")).join("");
  }

  async function fetchJson(path, options = {}) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 10000);
    try {
      const response = await fetch(path, { ...options, credentials: "omit", cache: "no-store", signal: controller.signal });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || `Cầu nối trả lỗi ${response.status}.`);
      return data;
    } finally {
      clearTimeout(timeout);
    }
  }

  async function loadAppParameters() {
    if (!isDemo()) throw new Error("Thông số app chỉ tự điền vào mẫu minh họa.");
    const state = await fetchJson("api/state");
    const mappings = [["R_ohm", "r_ohm", 1], ["C_F", "c_nf", 1e9], ["Lp_H", "lp_nh", 1e9],
      ["Cp_F", "cp_pf", 1e12], ["Vin", "vin_v", 1], ["added_cap_F", "added_pf", 1e12]];
    mappings.forEach(([key, id, scale]) => {
      if (Number.isFinite(state[key]) && state[key] > 0) $(id).value = Number((state[key] * scale).toPrecision(10));
    });
    rebuildDemo();
    setStatus("Đã lấy thông số từ app và dựng mẫu RLC. Kết quả vẫn chỉ là minh họa.");
  }

  async function beginCapture() {
    if (!sim || capture) return;
    const durationNs = number("duration_ns", "Cửa sổ");
    const dtNs = number("dt_ns", "Bước thời gian");
    if (dtNs < .001) throw new Error("Bước thời gian tối thiểu của công cụ minh họa là 0,001 ns.");
    if (durationNs / dtNs + 2 > MAX_POINTS) throw new Error("Cửa sổ quá dài so với bước lấy mẫu: chọn tối đa khoảng 20.000 điểm.");
    const mode = isDemo() ? "demo" : "custom";
    const role = $("variant").value;
    if (!["before", "after", "test_cap"].includes(role)) throw new Error("Chọn rõ vai trò A/B/tụ thử của bản ghi.");
    if (mode === "demo" && durationNs <= 300 + 10 * dtNs) throw new Error("Cửa sổ mẫu phải đủ dài sau bước nguồn ở 300 ns.");
    let parameters = null;
    let context;
    if (mode === "demo") {
      parameters = readParameters();
      context = "demo-rlc-v1:" + await hashText(JSON.stringify({ Lp_H: parameters.Lp_H, Cp_F: parameters.Cp_F, Vin: parameters.Vin, series_R: .05, step_s: 300e-9 }));
      rebuildDemo(true);
    } else {
      const description = $("custom_context").value.trim();
      if (!description) throw new Error("Ghi tên mạch và điều kiện dùng chung trước khi ghi mạch tự vẽ.");
      ownImportPending = false;
      sim.setSimRunning(false);
      sim.setMaxTimeStep(dtNs * 1e-9);
      refreshNodes();
      context = "custom:" + await hashText(JSON.stringify({ condition: description,
        positive: $("positive_node").value, negative: $("negative_node").value }));
    }
    const positive = $("positive_node").value;
    const negative = $("negative_node").value;
    if (positive === negative) throw new Error("Hai nút đo đang giống nhau; chọn điện áp cần khảo sát.");
    const metadata = { role, context_id: context, source_mode: mode, node_positive: positive, node_negative: negative,
      node_positive_name: $("positive_node").selectedOptions[0].textContent,
      node_negative_name: $("negative_node").selectedOptions[0].textContent,
      dt_ns: dtNs, duration_ns: durationNs,
      interpretation: "Illustration; not P6 Buck, LTspice or hardware validation" };
    if (parameters) Object.assign(metadata, parameters, { plateau_V: parameters.Vin });
    else metadata.circuit_condition = $("custom_context").value.trim();
    capture = { start: Number(sim.getTime()), duration: durationNs * 1e-9, positive, negative,
      times: [], voltages: [], metadata, lastTime: -Infinity };
    busy(true);
    setStatus("Đang ghi điện áp tại hai nút đã chọn…", "recording");
    $("capture_count").textContent = "0 điểm";
    watchdog = setTimeout(() => {
      if (capture) stopRecording("Mạch chưa chạy hết cửa sổ trong 30 giây. Kiểm tra lỗi mạch/bước thời gian rồi thử lại.");
    }, 30000);
    sim.setSimRunning(true);
  }

  async function finishCapture(recording) {
    capture = null;
    if (watchdog) clearTimeout(watchdog);
    watchdog = null;
    sim.setSimRunning(false);
    if (recording.times.length < 10) {
      busy(false);
      throw new Error("Chưa có đủ 10 điểm để gửi về app.");
    }
    setStatus("Đang lưu và chuyển dạng sóng về app…", "sending");
    $("stop").disabled = true;
    const result = await fetchJson("api/waveform", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ times: recording.times, voltages: recording.voltages,
        circuit_text: sim.exportCircuit(), metadata: recording.metadata }) });
    lastSent = result;
    busy(false);
    setStatus(`Đã gửi ${result.n_points} điểm về app. ${result.filename}`, "sent");
    $("capture_count").textContent = `Đã lưu bản ghi ${recording.metadata.role}; xem kết quả ở tab Phân tích dạng sóng.`;
  }

  function onTimestep() {
    try {
      const now = Number(sim.getTime());
      if (isDemo()) sim.setExtVoltage("drive", now >= 300e-9 ? number("vin_v", "Bước nguồn") : 0);
      if (!capture) return;
      const elapsed = now - capture.start;
      if (!Number.isFinite(elapsed) || elapsed < 0) throw new Error("Thời gian mô phỏng đã đổi; bản ghi bị hủy.");
      if (elapsed <= capture.lastTime) return;
      const value = voltageAt(capture.positive) - voltageAt(capture.negative);
      if (!Number.isFinite(value)) throw new Error("Điện áp không hữu hạn; kiểm tra sơ đồ và hai nút đo.");
      if (capture.times.length >= MAX_POINTS) throw new Error("Đã vượt 20.000 điểm trước khi hết cửa sổ; tăng bước hoặc giảm cửa sổ.");
      capture.times.push(elapsed);
      capture.voltages.push(value);
      capture.lastTime = elapsed;
      if (capture.times.length % 500 === 0) $("capture_count").textContent = `${capture.times.length.toLocaleString("vi-VN")} điểm · ${(elapsed * 1e9).toFixed(1)} ns`;
      if (elapsed >= capture.duration) {
        const completed = capture;
        finishCapture(completed).catch(error => { busy(false); showError(error); });
      }
    } catch (error) {
      stopRecording();
      showError(error);
    }
  }

  function onAnalyze() {
    if (ownImportPending) ownImportPending = false;
    else if (capture) stopRecording("Sơ đồ thay đổi trong lúc ghi; đã hủy bản ghi. Chọn lại hai nút và ghi lại.");
    try { refreshNodes(); } catch (error) { showError(error); }
  }

  function applyMode() {
    stopRecording("Đã đổi nguồn sơ đồ. Kiểm tra vai trò và hai nút trước khi ghi.");
    $("custom_context_group").hidden = isDemo();
    if (!isDemo()) {
      if (!$("variant").querySelector('option[value=""]')) {
        const placeholder = new Option("Chọn rõ vai trò bản ghi…", "");
        placeholder.disabled = true;
        $("variant").prepend(placeholder);
      }
      $("variant").value = "";
    } else if (!$("variant").value) $("variant").value = "before";
    $("capture_hint").textContent = isDemo()
      ? "Mẫu bắt đầu lại từ 0; bước nguồn xuất hiện ở 300 ns. Ghi tối đa 20.000 điểm."
      : "Bản ghi bắt đầu từ trạng thái hiện tại của mạch. Dùng Reset của CircuitJS nếu cần; cửa sổ phải chứa một cạnh tăng.";
    if (isDemo() && sim) rebuildDemo();
    busy(false);
  }

  function connectSimulator() {
    try {
      const candidate = frame.contentWindow.CircuitJS1;
      if (!candidate || typeof candidate.importCircuit !== "function" || typeof candidate.getElements !== "function") return;
      sim = candidate;
      clearInterval(startupTimer);
      sim.setSimRunning(false);
      sim.ontimestep = onTimestep;
      sim.onanalyze = onAnalyze;
      rebuildDemo();
      document.body.dataset.ready = "true";
      busy(false);
      loadAppParameters().catch(showError);
    } catch (error) { showError(error); }
  }

  $("load_app").addEventListener("click", () => loadAppParameters().catch(showError));
  $("rebuild").addEventListener("click", () => { try { rebuildDemo(); } catch (error) { showError(error); } });
  $("record").addEventListener("click", () => beginCapture().catch(error => { busy(false); showError(error); }));
  $("stop").addEventListener("click", () => stopRecording());
  $("source_mode").addEventListener("change", () => { try { applyMode(); } catch (error) { showError(error); } });
  $("variant").addEventListener("change", () => {
    if (isDemo() && sim) { try { rebuildDemo(); } catch (error) { showError(error); } }
  });
  frame.addEventListener("load", connectSimulator);
  startupTimer = setInterval(connectSimulator, 250);
  setTimeout(() => {
    if (!sim) { clearInterval(startupTimer); setStatus("CircuitJS chưa mở được. Kiểm tra bản mô phỏng đi kèm app rồi mở lại tab.", "error"); }
  }, 30000);
  window.addEventListener("beforeunload", () => { if (sim) sim.setSimRunning(false); });
  window.snubberBridge = Object.freeze({ getSnapshot: () => ({ ready: !!sim, phase: $("status").dataset.phase,
    points: capture ? capture.times.length : 0, lastSent, sourceMode: $("source_mode").value }) });
})();
