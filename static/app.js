/* ── SmartCoffee HMI ───────────────────────────────────────────────────────── */

// ── Gauge maths ───────────────────────────────────────────────────────────────
const GAUGE_CX    = 150;
const GAUGE_CY    = 150;
const GAUGE_R     = 110;
const GAUGE_SW    = 16;   // stroke width
const GAUGE_START = 225;  // degrees from 12-o'clock, clockwise = lower-left
const GAUGE_SWEEP = 270;  // total arc
const GAUGE_MIN   = 80;
const GAUGE_MAX   = 130;

function polarXY(cx, cy, r, deg) {
  const rad = (deg - 90) * Math.PI / 180;
  return { x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) };
}

function arcPath(cx, cy, r, startDeg, endDeg, sweep) {
  // sweep: 1 = clockwise (SVG), 0 = counterclockwise
  const s = polarXY(cx, cy, r, startDeg);
  const e = polarXY(cx, cy, r, endDeg);
  const delta = endDeg - startDeg;
  const large = delta > 180 ? 1 : 0;
  return `M ${s.x.toFixed(2)} ${s.y.toFixed(2)} A ${r} ${r} 0 ${large} ${sweep} ${e.x.toFixed(2)} ${e.y.toFixed(2)}`;
}

function tempToAngle(temp) {
  const f = Math.max(0, Math.min(1, (temp - GAUGE_MIN) / (GAUGE_MAX - GAUGE_MIN)));
  return GAUGE_START + f * GAUGE_SWEEP;
}

function gaugeColor(temp, target) {
  const diff = temp - target;
  if (diff < -5)  return '#60a5fa';   // cold  — blue
  if (diff < -1)  return '#fbbf24';   // rising — amber
  if (diff <= 1)  return '#34d399';   // on target — green
  return '#f87171';                    // overshot — red
}

function initGauge() {
  const track = document.getElementById('gauge-track');
  track.setAttribute('d', arcPath(GAUGE_CX, GAUGE_CY, GAUGE_R, GAUGE_START, GAUGE_START + GAUGE_SWEEP - 0.01, 1));
  track.setAttribute('stroke', 'rgba(255,255,255,0.07)');
  track.setAttribute('stroke-width', GAUGE_SW);

  // 5 tick marks at 0 / 25 / 50 / 75 / 100 %
  const tg = document.getElementById('gauge-ticks');
  [0, 0.25, 0.5, 0.75, 1].forEach(f => {
    const deg = GAUGE_START + f * GAUGE_SWEEP;
    const inner = polarXY(GAUGE_CX, GAUGE_CY, GAUGE_R - 10, deg);
    const outer = polarXY(GAUGE_CX, GAUGE_CY, GAUGE_R + 2, deg);
    const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
    line.setAttribute('x1', inner.x.toFixed(2));
    line.setAttribute('y1', inner.y.toFixed(2));
    line.setAttribute('x2', outer.x.toFixed(2));
    line.setAttribute('y2', outer.y.toFixed(2));
    line.setAttribute('stroke', 'rgba(255,255,255,0.15)');
    line.setAttribute('stroke-width', '1.5');
    line.setAttribute('stroke-linecap', 'round');
    tg.appendChild(line);
  });
}

function updateGauge(temp, target) {
  const fill = document.getElementById('gauge-fill');
  const tick = document.getElementById('gauge-target-tick');
  const gTemp = document.getElementById('g-temp');
  const gTarget = document.getElementById('g-target');

  // Fill arc
  const endDeg = tempToAngle(temp);
  const delta = endDeg - GAUGE_START;
  if (delta > 1) {
    const large = delta > 180 ? 1 : 0;
    const s = polarXY(GAUGE_CX, GAUGE_CY, GAUGE_R, GAUGE_START);
    const e = polarXY(GAUGE_CX, GAUGE_CY, GAUGE_R, endDeg);
    fill.setAttribute('d', `M ${s.x.toFixed(2)} ${s.y.toFixed(2)} A ${GAUGE_R} ${GAUGE_R} 0 ${large} 1 ${e.x.toFixed(2)} ${e.y.toFixed(2)}`);
    fill.setAttribute('stroke', gaugeColor(temp, target));
    fill.setAttribute('stroke-width', GAUGE_SW);
  } else {
    fill.setAttribute('d', '');
  }

  // Target tick
  const tDeg = tempToAngle(target);
  const ti = polarXY(GAUGE_CX, GAUGE_CY, GAUGE_R - 13, tDeg);
  const to = polarXY(GAUGE_CX, GAUGE_CY, GAUGE_R + 6, tDeg);
  tick.setAttribute('x1', ti.x.toFixed(2)); tick.setAttribute('y1', ti.y.toFixed(2));
  tick.setAttribute('x2', to.x.toFixed(2)); tick.setAttribute('y2', to.y.toFixed(2));
  tick.setAttribute('stroke', '#e8924a');
  tick.setAttribute('stroke-width', '2.5');
  tick.setAttribute('stroke-linecap', 'round');

  gTemp.textContent   = temp.toFixed(1);
  gTarget.textContent = `→ ${target.toFixed(1)} °C`;
}

// ── Chart ─────────────────────────────────────────────────────────────────────
const MAX_POINTS = 120;
const tempData   = [];
const outData    = [];

let chart;
function initChart() {
  const ctx = document.getElementById('live-chart').getContext('2d');
  chart = new Chart(ctx, {
    type: 'line',
    data: {
      labels: Array(MAX_POINTS).fill(''),
      datasets: [
        {
          label: 'Temp (°C)',
          data: Array(MAX_POINTS).fill(null),
          borderColor: '#e8924a',
          borderWidth: 2,
          pointRadius: 0,
          tension: 0.4,
          yAxisID: 'yTemp',
          fill: false,
        },
        {
          label: 'Heater (%)',
          data: Array(MAX_POINTS).fill(null),
          borderColor: 'rgba(96,165,250,0.7)',
          borderWidth: 1.5,
          borderDash: [3, 3],
          pointRadius: 0,
          tension: 0.4,
          yAxisID: 'yOut',
          fill: false,
        },
      ],
    },
    options: {
      animation: false,
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: { enabled: false },
      },
      scales: {
        x: {
          display: false,
        },
        yTemp: {
          position: 'left',
          min: 70, max: 135,
          grid:  { color: 'rgba(255,255,255,0.04)' },
          ticks: { color: '#8892b0', font: { size: 10 }, maxTicksLimit: 6 },
          border: { color: 'rgba(255,255,255,0.06)' },
        },
        yOut: {
          position: 'right',
          min: 0, max: 100,
          grid: { display: false },
          ticks: { color: '#60a5fa', font: { size: 10 }, maxTicksLimit: 4,
                   callback: v => v + '%' },
          border: { color: 'rgba(255,255,255,0.06)' },
        },
      },
    },
  });
}

function pushChart(temp, output) {
  tempData.push(temp);
  outData.push(output);
  if (tempData.length > MAX_POINTS) { tempData.shift(); outData.shift(); }

  chart.data.datasets[0].data = [...tempData];
  chart.data.datasets[1].data = [...outData];
  chart.update('none');
}

// ── SocketIO ──────────────────────────────────────────────────────────────────
let serverConfig = {};
let brewStartTime = null;
let brewTimerInterval = null;
let connected = false;

const socket = io({ transports: ['websocket', 'polling'] });

socket.on('connect', () => {
  connected = true;
  document.getElementById('conn-dot').classList.add('connected');
});

socket.on('disconnect', () => {
  connected = false;
  document.getElementById('conn-dot').classList.remove('connected');
  setPhase('idle');
});

socket.on('config', cfg => {
  serverConfig = cfg;
  applyConfigToUI(cfg);
});

socket.on('state', applyState);

function applyState(s) {
  const temp   = s.current_temp ?? 0;
  const target = s.target_temp  ?? 97.5;
  const output = s.pid_output   ?? 0;
  const phase  = s.brew_phase   ?? 'idle';

  updateGauge(temp, target);
  pushChart(temp, output);

  // Heater output bar
  document.getElementById('output-fill').style.width = output + '%';
  document.getElementById('output-val').textContent  = output.toFixed(0) + ' %';

  // Status chips
  setChip('chip-sensor', s.sensor_ok         ? 'ok' : 'error');
  setChip('chip-heater', s.heater_enabled     ? 'ok' : '');
  setChip('chip-pump',   phase !== 'idle'     ? 'active' : '');

  // PID mini bars (normalised to output, clamped 0–100%)
  updateMiniBar('pm-p', 'pm-p-val', s.pid_p, output);
  updateMiniBar('pm-i', 'pm-i-val', s.pid_i, output);
  updateMiniBar('pm-d', 'pm-d-val', s.pid_d, output);

  // Centred component bars (±100 range)
  updateCompBar('comp-p', 'comp-p-val', s.pid_p);
  updateCompBar('comp-i', 'comp-i-val', s.pid_i);
  updateCompBar('comp-d', 'comp-d-val', s.pid_d);

  // Phase label + dot
  setPhase(phase);

  // Shot timer — only count while active
  if (phase !== 'idle' && phase !== 'done') {
    if (!brewStartTime) {
      brewStartTime = Date.now() - ((serverConfig?.brew?.brew_duration ?? 25) - (s.brew_time_remaining ?? 0)) * 1000;
      if (!brewTimerInterval) {
        brewTimerInterval = setInterval(tickShotTimer, 100);
      }
    }
  } else {
    brewStartTime = null;
    if (brewTimerInterval) { clearInterval(brewTimerInterval); brewTimerInterval = null; }
    if (phase === 'idle') document.getElementById('shot-timer').textContent = '0:00';
  }

  // Uptime
  const u = s.uptime ?? 0;
  const hh = String(Math.floor(u / 3600)).padStart(2, '0');
  const mm = String(Math.floor((u % 3600) / 60)).padStart(2, '0');
  const ss = String(u % 60).padStart(2, '0');
  document.getElementById('uptime-display').textContent = `${hh}:${mm}:${ss}`;

  // Sync setpoint slider if changed server-side
  const slider = document.getElementById('setpoint-slider');
  if (Math.abs(parseFloat(slider.value) - target) > 0.4) {
    slider.value = target;
    document.getElementById('setpoint-disp').textContent = target.toFixed(1) + ' °C';
  }
}

function tickShotTimer() {
  if (!brewStartTime) return;
  const elapsed = (Date.now() - brewStartTime) / 1000;
  const m = Math.floor(elapsed / 60);
  const s = Math.floor(elapsed % 60);
  document.getElementById('shot-timer').textContent = `${m}:${String(s).padStart(2, '0')}`;
}

// ── Helpers ───────────────────────────────────────────────────────────────────
function setChip(id, cls) {
  const el = document.getElementById(id);
  el.classList.remove('ok', 'active', 'error');
  if (cls) el.classList.add(cls);
}

function updateMiniBar(barId, valId, component, total) {
  const pct = total > 0 ? Math.min(100, Math.abs(component) / total * 100) : 0;
  document.getElementById(barId).style.width = pct.toFixed(1) + '%';
  document.getElementById(valId).textContent = component.toFixed(3);
}

function updateCompBar(barId, valId, value) {
  const el = document.getElementById(barId);
  const range = 100;
  const half = 50;
  const normAbs = Math.min(range, Math.abs(value)) / range * half;
  if (value >= 0) {
    el.style.left  = half + '%';
    el.style.width = normAbs.toFixed(1) + '%';
  } else {
    el.style.left  = (half - normAbs).toFixed(1) + '%';
    el.style.width = normAbs.toFixed(1) + '%';
  }
  document.getElementById(valId).textContent = value.toFixed(3);
}

const PHASE_LABELS = {
  idle:          'Ready',
  pre_infusion:  'Pre-infusion',
  brewing:       'Brewing',
  purging:       'Purging',
  done:          'Done',
};
const PHASE_DOT = {
  idle:         '',
  pre_infusion: 'brewing',
  brewing:      'brewing',
  purging:      'warn',
  done:         'ok',
};
function setPhase(phase) {
  document.getElementById('phase-label').textContent = PHASE_LABELS[phase] ?? phase;
  const dot = document.getElementById('phase-dot');
  dot.className = 'phase-dot';
  const cls = PHASE_DOT[phase];
  if (cls) dot.classList.add(cls);
}

// ── Tab switching ─────────────────────────────────────────────────────────────
document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById('tab-' + btn.dataset.tab).classList.add('active');
  });
});

// ── Setpoint slider ───────────────────────────────────────────────────────────
const setpointSlider = document.getElementById('setpoint-slider');
const setpointDisp   = document.getElementById('setpoint-disp');

let setpointDebounce;
setpointSlider.addEventListener('input', () => {
  const v = parseFloat(setpointSlider.value);
  setpointDisp.textContent = v.toFixed(1) + ' °C';
  clearTimeout(setpointDebounce);
  setpointDebounce = setTimeout(() => sendSetpoint(v), 400);
});

document.querySelectorAll('.preset[data-temp]').forEach(btn => {
  btn.addEventListener('click', () => {
    const t = parseFloat(btn.dataset.temp);
    setpointSlider.value = t;
    setpointDisp.textContent = t.toFixed(1) + ' °C';
    sendSetpoint(t);
  });
});

function sendSetpoint(temp) {
  fetch('/api/setpoint', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ temp }),
  });
}

// ── Brew controls ─────────────────────────────────────────────────────────────
document.getElementById('btn-brew').addEventListener('click', () => {
  fetch('/api/brew', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
});
document.getElementById('btn-purge').addEventListener('click', () => {
  fetch('/api/purge', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
});
document.getElementById('btn-stop').addEventListener('click', () => {
  fetch('/api/stop', { method: 'POST' });
});

// ── PID gains ─────────────────────────────────────────────────────────────────
function syncGainPair(sliderId, inputId) {
  const slider = document.getElementById(sliderId);
  const input  = document.getElementById(inputId);
  slider.addEventListener('input', () => { input.value = parseFloat(slider.value).toFixed(slider.step.includes('0.001') ? 3 : 2); });
  input.addEventListener('change', () => { slider.value = input.value; });
}
syncGainPair('kp-slider', 'kp-input');
syncGainPair('ki-slider', 'ki-input');
syncGainPair('kd-slider', 'kd-input');

const PID_PRESETS = {
  aggressive:  { kp: 4.0, ki: 0.08, kd: 2.0 },
  normal:      { kp: 2.0, ki: 0.05, kd: 1.0 },
  soft:        { kp: 0.8, ki: 0.02, kd: 0.5 },
};
document.querySelectorAll('.pid-preset-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    const p = PID_PRESETS[btn.dataset.preset];
    if (!p) return;
    document.getElementById('kp-slider').value = p.kp;
    document.getElementById('kp-input').value  = p.kp.toFixed(2);
    document.getElementById('ki-slider').value = p.ki;
    document.getElementById('ki-input').value  = p.ki.toFixed(3);
    document.getElementById('kd-slider').value = p.kd;
    document.getElementById('kd-input').value  = p.kd.toFixed(2);
  });
});

document.getElementById('btn-apply-pid').addEventListener('click', () => {
  const kp = parseFloat(document.getElementById('kp-input').value);
  const ki = parseFloat(document.getElementById('ki-input').value);
  const kd = parseFloat(document.getElementById('kd-input').value);
  fetch('/api/config', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ pid: { kp, ki, kd } }),
  }).then(() => flashApply('btn-apply-pid'));
});

function flashApply(id) {
  const btn = document.getElementById(id);
  btn.classList.add('saved');
  btn.textContent = '✓ Saved';
  setTimeout(() => {
    btn.classList.remove('saved');
    btn.textContent = id === 'btn-apply-pid' ? 'Apply PID gains' : 'Save settings';
  }, 2000);
}

// ── Heater toggle ─────────────────────────────────────────────────────────────
document.getElementById('heater-toggle').addEventListener('change', e => {
  fetch('/api/heater', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ enabled: e.target.checked }),
  });
});

// ── Advanced save ─────────────────────────────────────────────────────────────
document.getElementById('btn-save-adv').addEventListener('click', () => {
  const payload = {
    brew: {
      pre_infusion_enabled: document.getElementById('pre-inf-toggle').checked,
      pre_infusion_time:    parseInt(document.getElementById('pre-inf-time').value),
      brew_duration:        parseInt(document.getElementById('brew-dur').value),
      purge_duration:       parseInt(document.getElementById('purge-dur').value),
    },
    safety: {
      max_temp:           parseFloat(document.getElementById('max-temp-inp').value),
      emergency_shutoff:  document.getElementById('emergency-toggle').checked,
    },
  };
  fetch('/api/config', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  }).then(() => flashApply('btn-save-adv'));
});

// ── Apply server config to UI inputs ─────────────────────────────────────────
function applyConfigToUI(cfg) {
  if (!cfg) return;
  if (cfg.pid) {
    setVal('kp-slider', cfg.pid.kp); setVal('kp-input', cfg.pid.kp?.toFixed(2));
    setVal('ki-slider', cfg.pid.ki); setVal('ki-input', cfg.pid.ki?.toFixed(3));
    setVal('kd-slider', cfg.pid.kd); setVal('kd-input', cfg.pid.kd?.toFixed(2));
    setVal('setpoint-slider', cfg.pid.setpoint);
    setpointDisp.textContent = (cfg.pid.setpoint ?? 97.5).toFixed(1) + ' °C';
  }
  if (cfg.brew) {
    document.getElementById('pre-inf-toggle').checked = !!cfg.brew.pre_infusion_enabled;
    setVal('pre-inf-time', cfg.brew.pre_infusion_time);
    setVal('brew-dur',     cfg.brew.brew_duration);
    setVal('purge-dur',    cfg.brew.purge_duration);
  }
  if (cfg.safety) {
    setVal('max-temp-inp',    cfg.safety.max_temp);
    document.getElementById('emergency-toggle').checked = !!cfg.safety.emergency_shutoff;
  }
}

function setVal(id, v) {
  const el = document.getElementById(id);
  if (el && v !== undefined && v !== null) el.value = v;
}

// ── Initialise ────────────────────────────────────────────────────────────────
initGauge();
initChart();

// Fallback: load config via REST if SocketIO config event is slow
fetch('/api/config').then(r => r.json()).then(cfg => {
  if (!Object.keys(serverConfig).length) applyConfigToUI(cfg);
});
