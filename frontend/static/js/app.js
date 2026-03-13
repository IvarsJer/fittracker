const API = '/api';
let exercises = [];
let charts = {};

// ── Utils ──────────────────────────────────────────────────────────────────

const $  = (sel, ctx = document) => ctx.querySelector(sel);
const $$ = (sel, ctx = document) => [...ctx.querySelectorAll(sel)];

function toast(msg, dur = 2400) {
  const t = document.createElement('div');
  t.className = 'toast';
  t.textContent = msg;
  document.body.appendChild(t);
  setTimeout(() => t.remove(), dur);
}

async function api(path, opts = {}) {
  const res = await fetch(API + path, {
    headers: { 'Content-Type': 'application/json' },
    ...opts
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

function formatDate(iso) {
  return new Date(iso + 'T00:00:00').toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' });
}

function today() {
  return new Date().toISOString().slice(0, 10);
}

function destroyChart(key) {
  if (charts[key]) { charts[key].destroy(); delete charts[key]; }
}

const CHART_DEFAULTS = {
  color: '#e8e8ef',
  plugins: { legend: { display: false } },
  scales: {
    x: { ticks: { color: '#6b6b7e', font: { family: 'Space Mono', size: 10 } }, grid: { color: '#2a2a32' } },
    y: { ticks: { color: '#6b6b7e', font: { family: 'Space Mono', size: 10 } }, grid: { color: '#2a2a32' } }
  }
};

// ── Navigation ──────────────────────────────────────────────────────────────

$$('.nav-link').forEach(link => {
  link.addEventListener('click', e => {
    e.preventDefault();
    const page = link.dataset.page;
    $$('.nav-link').forEach(l => l.classList.remove('active'));
    link.classList.add('active');
    $$('.page').forEach(p => p.classList.remove('active'));
    $(`#page-${page}`).classList.add('active');
    $('#sidebar').classList.remove('open');
    loadPage(page);
  });
});

$('#menuBtn').addEventListener('click', () => $('#sidebar').classList.toggle('open'));

function loadPage(page) {
  if (page === 'dashboard')   loadDashboard();
  if (page === 'log')         initLogPage();
  if (page === 'history')     loadHistory();
  if (page === 'progress')    loadProgress();
  if (page === 'bodyweight')  loadBodyWeight();
  if (page === 'exercises')   loadExercises();
}

// ── Dashboard ───────────────────────────────────────────────────────────────

async function loadDashboard() {
  $('#today-date').textContent = new Date().toLocaleDateString('en-GB', { weekday: 'long', day: 'numeric', month: 'long' });
  const stats = await api('/stats/overview');

  $('#sc-workouts .stat-val').textContent = stats.total_workouts;
  $('#sc-streak .stat-val').textContent   = stats.current_streak + ' 🔥';
  $('#sc-sets .stat-val').textContent     = stats.total_sets;
  $('#sc-bw .stat-val').textContent       = stats.latest_bodyweight ? stats.latest_bodyweight.weight_kg + ' kg' : '—';

  if (stats.current_streak > 0) {
    const badge = $('#streak-badge');
    badge.classList.remove('hidden');
    $('#streak-count').textContent = stats.current_streak;
  }

  // Weekly frequency bar chart
  destroyChart('weekly');
  if (stats.weekly_frequency.length) {
    charts.weekly = new Chart($('#chart-weekly'), {
      type: 'bar',
      data: {
        labels: stats.weekly_frequency.map(r => r.week.replace(/^\d{4}-/, '')),
        datasets: [{ data: stats.weekly_frequency.map(r => r.count), backgroundColor: '#c8f135', borderRadius: 3 }]
      },
      options: { ...CHART_DEFAULTS, plugins: { legend: { display: false } } }
    });
  }

  // Category doughnut
  destroyChart('category');
  if (stats.category_distribution.length) {
    charts.category = new Chart($('#chart-category'), {
      type: 'doughnut',
      data: {
        labels: stats.category_distribution.map(r => r.category),
        datasets: [{
          data: stats.category_distribution.map(r => r.count),
          backgroundColor: ['#c8f135', '#4af0d4', '#ff4d6d', '#b0b0ff'],
          borderColor: '#111114', borderWidth: 2
        }]
      },
      options: {
        plugins: {
          legend: { display: true, labels: { color: '#e8e8ef', font: { family: 'Syne', size: 11 }, boxWidth: 10 } }
        }
      }
    });
  }

  // Volume line chart
  destroyChart('volume');
  if (stats.volume_over_time.length) {
    charts.volume = new Chart($('#chart-volume'), {
      type: 'line',
      data: {
        labels: stats.volume_over_time.map(r => r.date),
        datasets: [{
          data: stats.volume_over_time.map(r => r.volume),
          borderColor: '#4af0d4', backgroundColor: 'rgba(74,240,212,0.08)',
          fill: true, tension: 0.35, pointRadius: 3, pointBackgroundColor: '#4af0d4'
        }]
      },
      options: { ...CHART_DEFAULTS }
    });
  }

  // PRs
  const grid = $('#pr-grid');
  grid.innerHTML = '';
  stats.prs.forEach(pr => {
    const div = document.createElement('div');
    div.className = 'pr-item';
    div.innerHTML = `<div class="pr-exercise">${pr.exercise}</div><div class="pr-weight">${pr.max_weight_kg} kg</div>`;
    grid.appendChild(div);
  });
}

// ── Log Workout ──────────────────────────────────────────────────────────────

let setRows = [];

async function initLogPage() {
  await fetchExercises();
  $('#wk-date').value = today();
  if (setRows.length === 0) addSetRow();
}

function addSetRow(copyFrom = null) {
  const container = $('#sets-container');
  const idx = setRows.length;
  const row = document.createElement('div');
  row.className = 'set-row';
  row.innerHTML = `
    <span class="set-num">${idx + 1}</span>
    <select class="set-ex">${exercises.map(e => `<option value="${e.id}" data-cat="${e.category}">${e.name}</option>`).join('')}</select>
    <input type="number" class="set-reps" placeholder="Reps" min="1">
    <input type="number" class="set-weight" placeholder="kg" step="0.5" min="0">
    <input type="number" class="set-dist" placeholder="km" step="0.01" min="0">
    <input type="number" class="set-dur" placeholder="sec" min="1">
    <input type="text" class="set-notes" placeholder="Note">
    <button class="btn-dupe" title="Duplicate set">⧉</button>
    <button class="btn-danger" data-idx="${idx}">✕</button>
  `;
  if (copyFrom) {
    row.querySelector('.set-ex').value     = copyFrom.querySelector('.set-ex').value;
    row.querySelector('.set-reps').value   = copyFrom.querySelector('.set-reps').value;
    row.querySelector('.set-weight').value = copyFrom.querySelector('.set-weight').value;
    row.querySelector('.set-dist').value   = copyFrom.querySelector('.set-dist').value;
    row.querySelector('.set-dur').value    = copyFrom.querySelector('.set-dur').value;
    row.querySelector('.set-notes').value  = copyFrom.querySelector('.set-notes').value;
  }
  row.querySelector('.btn-dupe').addEventListener('click', () => addSetRow(row));
  row.querySelector('.btn-danger').addEventListener('click', () => {
    row.remove();
    setRows.splice(idx, 1);
    renumberSets();
  });
  container.appendChild(row);
  setRows.push(row);
}

function renumberSets() {
  $$('.set-row').forEach((row, i) => {
    row.querySelector('.set-num').textContent = i + 1;
    row.querySelector('.btn-danger').dataset.idx = i;
  });
  setRows = $$('.set-row');
}

$('#add-set-btn').addEventListener('click', () => addSetRow());

$('#save-workout-btn').addEventListener('click', async () => {
  const rows = $$('.set-row');
  if (!rows.length) { toast('Add at least one set!'); return; }
  const sets = rows.map((row, i) => ({
    exercise_id: parseInt(row.querySelector('.set-ex').value),
    set_number: i + 1,
    reps:         parseInt(row.querySelector('.set-reps').value)   || null,
    weight_kg:    parseFloat(row.querySelector('.set-weight').value) || null,
    distance_km:  parseFloat(row.querySelector('.set-dist').value)  || null,
    duration_sec: parseInt(row.querySelector('.set-dur').value)    || null,
    notes:        row.querySelector('.set-notes').value || null
  }));
  const payload = {
    name:         $('#wk-name').value || null,
    workout_date: $('#wk-date').value || today(),
    notes:        $('#wk-notes').value || null,
    duration_min: parseInt($('#wk-duration').value) || null,
    sets
  };
  try {
    await api('/workouts', { method: 'POST', body: JSON.stringify(payload) });
    toast('Workout saved! 💪');
    $('#wk-name').value = ''; $('#wk-notes').value = ''; $('#wk-duration').value = '';
    $('#sets-container').innerHTML = '';
    setRows = [];
    addSetRow();
  } catch (err) { toast('Error saving: ' + err.message); }
});

// ── History ──────────────────────────────────────────────────────────────────

async function loadHistory() {
  const workouts = await api('/workouts?limit=100');
  const list = $('#workout-list');
  list.innerHTML = '';
  if (!workouts.length) { list.innerHTML = '<p style="color:var(--muted)">No workouts logged yet.</p>'; return; }
  workouts.forEach(w => {
    const item = document.createElement('div');
    item.className = 'workout-item';
    item.innerHTML = `
      <div class="workout-date-col">${formatDate(w.workout_date)}</div>
      <div class="workout-name-col">${w.name || 'Workout'}</div>
      <div class="workout-meta">
        <span>${w.set_count} sets</span>
        ${w.duration_min ? `<span>${w.duration_min} min</span>` : ''}
      </div>
      <button class="btn-del-workout" data-id="${w.id}" title="Delete">🗑</button>
    `;
    item.addEventListener('click', e => {
      if (e.target.closest('.btn-del-workout')) return;
      openWorkoutModal(w.id);
    });
    item.querySelector('.btn-del-workout').addEventListener('click', async e => {
      e.stopPropagation();
      if (!confirm('Delete this workout?')) return;
      await api(`/workouts/${w.id}`, { method: 'DELETE' });
      toast('Workout deleted');
      loadHistory();
    });
    list.appendChild(item);
  });
}

async function openWorkoutModal(id) {
  const w = await api(`/workouts/${id}`);
  const content = $('#modal-content');
  const grouped = {};
  w.sets.forEach(s => {
    if (!grouped[s.exercise_name]) grouped[s.exercise_name] = [];
    grouped[s.exercise_name].push(s);
  });
  let html = `<div class="modal-title">${w.name || 'Workout'}</div>
    <div class="modal-date">${formatDate(w.workout_date)}${w.duration_min ? ` · ${w.duration_min} min` : ''}</div>`;
  if (w.notes) html += `<p style="color:var(--muted);font-size:.85rem;margin-bottom:16px">${w.notes}</p>`;
  Object.entries(grouped).forEach(([exName, sets]) => {
    html += `<div style="font-weight:700;font-size:.88rem;margin:14px 0 8px">${exName}</div>
    <table class="modal-sets-table"><thead><tr><th>#</th><th>Reps</th><th>Weight</th><th>Distance</th><th>Duration</th></tr></thead><tbody>`;
    sets.forEach(s => {
      html += `<tr>
        <td>${s.set_number}</td>
        <td>${s.reps ?? '—'}</td>
        <td>${s.weight_kg != null ? s.weight_kg + ' kg' : '—'}</td>
        <td>${s.distance_km != null ? s.distance_km + ' km' : '—'}</td>
        <td>${s.duration_sec != null ? s.duration_sec + 's' : '—'}</td>
      </tr>`;
    });
    html += '</tbody></table>';
  });
  content.innerHTML = html;
  $('#modal-overlay').classList.remove('hidden');
}

$('#modal-close').addEventListener('click', () => $('#modal-overlay').classList.add('hidden'));
$('#modal-overlay').addEventListener('click', e => { if (e.target === $('#modal-overlay')) $('#modal-overlay').classList.add('hidden'); });

// ── Progress ──────────────────────────────────────────────────────────────────

async function loadProgress() {
  await fetchExercises();
  const sel = $('#progress-exercise-select');
  sel.innerHTML = '<option value="">— pick an exercise —</option>';
  exercises.forEach(e => {
    const opt = document.createElement('option');
    opt.value = e.id; opt.textContent = e.name;
    sel.appendChild(opt);
  });
  sel.addEventListener('change', loadExerciseProgress);
}

async function loadExerciseProgress() {
  const id = $('#progress-exercise-select').value;
  if (!id) return;
  const data = await api(`/stats/exercise/${id}`);
  destroyChart('prog-weight'); destroyChart('prog-volume');
  if (!data.length) { toast('No data for this exercise yet'); return; }
  const labels = data.map(r => r.date);
  charts['prog-weight'] = new Chart($('#chart-progress-weight'), {
    type: 'line',
    data: {
      labels,
      datasets: [{ data: data.map(r => r.max_weight), borderColor: '#c8f135', backgroundColor: 'rgba(200,241,53,0.08)', fill: true, tension: 0.3, pointRadius: 4, pointBackgroundColor: '#c8f135' }]
    },
    options: { ...CHART_DEFAULTS }
  });
  charts['prog-volume'] = new Chart($('#chart-progress-volume'), {
    type: 'bar',
    data: {
      labels,
      datasets: [{ data: data.map(r => r.volume), backgroundColor: 'rgba(74,240,212,0.7)', borderRadius: 3 }]
    },
    options: { ...CHART_DEFAULTS }
  });
}

// ── Body Weight ──────────────────────────────────────────────────────────────

async function loadBodyWeight() {
  $('#bw-date').value = today();
  const entries = await api('/bodyweight');
  destroyChart('bw');
  if (entries.length) {
    const sorted = [...entries].reverse();
    charts.bw = new Chart($('#chart-bw'), {
      type: 'line',
      data: {
        labels: sorted.map(e => e.logged_date),
        datasets: [{ data: sorted.map(e => e.weight_kg), borderColor: '#c8f135', backgroundColor: 'rgba(200,241,53,0.08)', fill: true, tension: 0.3, pointRadius: 3, pointBackgroundColor: '#c8f135' }]
      },
      options: { ...CHART_DEFAULTS }
    });
  }
  const tbody = $('#bw-table tbody');
  tbody.innerHTML = '';
  entries.forEach(e => {
    const tr = document.createElement('tr');
    tr.innerHTML = `<td>${formatDate(e.logged_date)}</td><td>${e.weight_kg} kg</td>
      <td><button class="btn-danger" data-id="${e.id}">✕</button></td>`;
    tr.querySelector('.btn-danger').addEventListener('click', async () => {
      await api(`/bodyweight/${e.id}`, { method: 'DELETE' });
      toast('Entry removed');
      loadBodyWeight();
    });
    tbody.appendChild(tr);
  });
}

$('#bw-save-btn').addEventListener('click', async () => {
  const kg = parseFloat($('#bw-input').value);
  if (!kg) { toast('Enter a valid weight'); return; }
  await api('/bodyweight', { method: 'POST', body: JSON.stringify({ weight_kg: kg, logged_date: $('#bw-date').value }) });
  toast('Weight logged!');
  $('#bw-input').value = '';
  loadBodyWeight();
});

// ── Exercises ─────────────────────────────────────────────────────────────────

async function fetchExercises() {
  exercises = await api('/exercises');
}

async function loadExercises() {
  await fetchExercises();
  renderExercises('all');
  $$('.filter-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      $$('.filter-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      renderExercises(btn.dataset.cat);
    });
  });
}

function renderExercises(cat) {
  const grid = $('#exercise-grid');
  grid.innerHTML = '';
  const filtered = cat === 'all' ? exercises : exercises.filter(e => e.category === cat);
  filtered.forEach(e => {
    const card = document.createElement('div');
    card.className = 'exercise-card';
    card.innerHTML = `
      <div class="exercise-card-info">
        <div class="exercise-card-name">${e.name}</div>
        <div class="exercise-card-meta">${e.muscle_group || ''}</div>
      </div>
      <div style="display:flex;flex-direction:column;align-items:flex-end;gap:6px">
        <span class="cat-badge cat-${e.category}">${e.category}</span>
        <button class="btn-danger" data-id="${e.id}">✕</button>
      </div>
    `;
    card.querySelector('.btn-danger').addEventListener('click', async () => {
      if (!confirm(`Delete "${e.name}"?`)) return;
      await api(`/exercises/${e.id}`, { method: 'DELETE' });
      toast('Exercise deleted');
      loadExercises();
    });
    grid.appendChild(card);
  });
}

$('#ex-add-btn').addEventListener('click', async () => {
  const name = $('#ex-name').value.trim();
  if (!name) { toast('Enter an exercise name'); return; }
  await api('/exercises', {
    method: 'POST',
    body: JSON.stringify({ name, category: $('#ex-category').value, muscle_group: $('#ex-muscle').value })
  });
  toast('Exercise added!');
  $('#ex-name').value = ''; $('#ex-muscle').value = '';
  loadExercises();
});

// ── Boot ─────────────────────────────────────────────────────────────────────

(async function boot() {
  await fetchExercises();
  loadDashboard();
})();
