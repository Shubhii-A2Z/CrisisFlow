const $ = s => document.querySelector(s);
let state = null;
let isClosed = false;

const esc = s => String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

async function api(path, body) {
  const r = await fetch(path, body ? { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) } : {});
  if (!r.ok) throw new Error('Request failed');
  return r.json();
}

async function load() {
  state = await api('/api/state');
  render();
}

function timeCompare(m) {
  if (m.eta == null || m.baseline_eta == null) return '<div class="impact neutral">No route available in this scenario</div>';
  const d = m.delta_min || 0;
  let cls = d > .05 ? 'positive' : d < -.05 ? 'negative' : 'neutral';
  let label = d > .05 ? `Estimated ${d.toFixed(1)} min lower (${m.benefit_pct.toFixed(0)}%)` : d < -.05 ? `Estimated ${Math.abs(d).toFixed(1)} min higher` : 'No estimated time difference';
  return `<div class="impact ${cls}">${label}</div>`;
}

function render() {
  if (!state) return;
  $('#tick').textContent = `Traffic step ${state.tick}`;
  $('#scenario-title').textContent = state.scenario_title;
  $('#scenario-description').textContent = state.scenario_description;
  $('#disclosure').textContent = state.comparison + ' ' + state.disclosure;

  // Toggle closure button based on scenario
  const closedRoad = state.roads.find(r => r.closed);
  if (closedRoad) {
    isClosed = true;
    $('#closure').textContent = `Open road ${closedRoad.a}–${closedRoad.b}`;
    $('#closure').dataset.a = closedRoad.a;
    $('#closure').dataset.b = closedRoad.b;
  } else {
    isClosed = false;
    const sampleRoad = state.roads[0] || { a: 'A', b: 'B' };
    $('#closure').textContent = `Close road ${sampleRoad.a}–${sampleRoad.b}`;
    $('#closure').dataset.a = sampleRoad.a;
    $('#closure').dataset.b = sampleRoad.b;
  }

  const options = state.scenario_options.map(x => `<option value="${esc(x.id)}">${esc(x.title)}</option>`).join('');
  $('#scenario').innerHTML = options;
  $('#scenario').value = state.scenario_id;

  const colors = { Ambulance: '#ec625e', 'Fire engine': '#d3a43f', Police: '#3671b7' };
  const allRoutes = state.missions.map(m => ({ route: m.route, color: colors[m.vehicle] }));

  const edgeUse = new Map();
  for (const item of allRoutes) {
    for (let i = 0; i < item.route.length - 1; i++) {
      let k = [item.route[i], item.route[i + 1]].sort().join('-');
      if (!edgeUse.has(k)) edgeUse.set(k, []);
      edgeUse.get(k).push(item.color);
    }
  }
  for (let i = 0; i < (state.fleet.route || []).length - 1; i++) {
    let k = [state.fleet.route[i], state.fleet.route[i + 1]].sort().join('-');
    if (!edgeUse.has(k)) edgeUse.set(k, []);
    edgeUse.get(k).push('#4886c4');
  }

  // Determine dynamic SVG bounds to fit any graph
  const xs = Object.values(state.nodes).map(n => n.x);
  const ys = Object.values(state.nodes).map(n => n.y);
  const minX = Math.min(...xs, 0);
  const maxX = Math.max(...xs, 600);
  const minY = Math.min(...ys, 0);
  const maxY = Math.max(...ys, 580);
  const mapSvg = $('#map');
  mapSvg.setAttribute('viewBox', `${minX - 40} ${minY - 40} ${maxX - minX + 80} ${maxY - minY + 90}`);

  let svg = '';
  // Draw Roads
  for (const r of state.roads) {
    const a = state.nodes[r.a], b = state.nodes[r.b];
    if (!a || !b) continue;
    const key = [r.a, r.b].sort().join('-');
    const uses = edgeUse.get(key) || [];
    const col = r.closed ? '#bd642e' : uses[0] || '#d5dfe2';
    const width = uses.length ? 6 : Math.max(2.5, 2 + r.congestion * 1.2);
    svg += `<line x1="${a.x}" y1="${a.y}" x2="${b.x}" y2="${b.y}" stroke="#fff" stroke-width="${width + 5}" stroke-linecap="round"/>`;
    svg += `<line x1="${a.x}" y1="${a.y}" x2="${b.x}" y2="${b.y}" stroke="${col}" stroke-width="${width}" stroke-linecap="round" ${r.closed ? 'stroke-dasharray="9 7"' : ''}/>`;
    const mx = (a.x + b.x) / 2, my = (a.y + b.y) / 2;
    svg += `<text x="${mx}" y="${my - 6}" text-anchor="middle" class="edge-label" font-size="10" fill="#445">${r.closed ? 'CLOSED' : `${r.volume}/${r.capacity}`}</text>`;
  }

  // Draw Nodes
  for (const [id, n] of Object.entries(state.nodes)) {
    const isIncident = state.missions.some(m => m.destination === id);
    const r = state.is_real_data ? 14 : (isIncident ? 22 : 18);
    svg += `<circle cx="${n.x}" cy="${n.y}" r="${r}" fill="${isIncident ? '#fff1e7' : '#eaf3f1'}" stroke="${isIncident ? '#c87137' : '#7a9a98'}" stroke-width="2"/>`;
    svg += `<text x="${n.x}" y="${n.y + 4}" text-anchor="middle" class="node-id" font-size="${state.is_real_data ? '9' : '11'}" font-weight="bold">${esc(id)}</text>`;
    if (n.label) {
      svg += `<text x="${n.x}" y="${n.y + (state.is_real_data ? 22 : 36)}" text-anchor="middle" class="node-label" font-size="9" fill="#2d3748">${esc(n.label)}</text>`;
    }
  }

  // Draw Route Overlays
  for (const item of allRoutes) {
    if (item.route.length > 1) {
      const p = item.route.filter(id => state.nodes[id]).map((id, i) => `${i ? 'L' : 'M'} ${state.nodes[id].x} ${state.nodes[id].y}`).join(' ');
      if (p) {
        svg += `<path d="${p}" fill="none" stroke="${item.color}" stroke-width="3" stroke-dasharray="4 8" stroke-linecap="round" opacity=".85"/>`;
      }
    }
  }

  mapSvg.innerHTML = svg;

  // Missions panel
  $('#missions').innerHTML = state.missions.map(m => `
    <div class="mission">
      <div class="mission-top">
        <span class="vehicle" style="color:${colors[m.vehicle]}">${esc(m.vehicle)}</span>
        <span class="severity">Severity ${m.severity}/5</span>
      </div>
      <div class="route-label">Coordinated · ${esc(m.route.join(' → ') || 'No route')}</div>
      <div class="route-meta">Est. ${m.eta == null ? '—' : m.eta.toFixed(1) + ' min'} · ${state.is_real_data ? 'OSM real geometry' : 'synthetic'}</div>
      <div class="baseline-label">Baseline · ${esc(m.baseline_route.join(' → ') || 'No route')} · est. ${m.baseline_eta == null ? '—' : m.baseline_eta.toFixed(1) + ' min'}</div>
      ${timeCompare(m)}
      <div class="route-meta">${m.id} · ${m.origin} to ${m.destination} (${state.nodes[m.destination]?.label || 'Incident'})</div>
    </div>
  `).join('');

  // Signal plan
  const agentNodes = Object.entries(state.signal_plan).filter(([_, v]) => v.mission);
  $('#signals').innerHTML = (agentNodes.length ? agentNodes : [['—', { state: 'Adaptive' }]])
    .map(([node, x]) => `<div class="agent"><span>Intersection ${node} (${state.nodes[node]?.label || 'Signal'})${x.mission ? ' · ' + x.mission : ''}</span><span class="green">${x.state}</span></div>`).join('');

  // Fleet panel
  const f = state.fleet;
  let fd = f.delta_min > 0 ? `Estimated ${f.delta_min.toFixed(1)} min lower` : f.delta_min < 0 ? `Estimated ${Math.abs(f.delta_min).toFixed(1)} min higher` : 'No estimated time change';
  $('#fleet-result').innerHTML = `
    <div class="fleet-route">${esc((f.route || []).join(' → ') || 'No route available')}</div>
    <div class="baseline-label">Baseline ${esc((f.baseline_route || []).join(' → ') || 'No route')} · est. ${f.baseline_eta == null ? '—' : f.baseline_eta.toFixed(1) + ' min'}</div>
    <div class="route-meta">Coordinated est. ${f.eta == null ? '—' : f.eta.toFixed(1) + ' min'} · ${fd}</div>
  `;

  const nodeOptions = Object.keys(state.nodes).map(n => `<option value="${n}">${n} · ${esc(state.nodes[n].label || 'Node')}</option>`).join('');
  $('#fleet-start').innerHTML = nodeOptions;
  $('#fleet-end').innerHTML = nodeOptions;
  $('#fleet-start').value = f.origin;
  $('#fleet-end').value = f.destination;
}

$('#scenario').onchange = async e => {
  state = await api('/api/scenario', { scenario_id: e.target.value });
  render();
};

$('#step').onclick = async () => {
  state = await api('/api/step', {});
  render();
};

$('#reset').onclick = async () => {
  state = await api('/api/reset', {});
  render();
};

$('#closure').onclick = async () => {
  const btn = $('#closure');
  const a = btn.dataset.a, b = btn.dataset.b;
  state = await api('/api/closure', { a, b, closed: !isClosed });
  render();
};

$('#apply-fleet').onclick = async () => {
  state = await api('/api/fleet', { origin: $('#fleet-start').value, destination: $('#fleet-end').value });
  render();
};

load().catch(e => {
  $('#scenario-title').textContent = 'Could not load simulator';
  console.error(e);
});

$('#compare').onclick = async () => {
  const panel = $('#comparison');
  if (!panel.hidden) {
    panel.hidden = true;
    $('#compare').textContent = 'Compare all 5';
    return;
  }
  const rows = await api('/api/compare');
  panel.innerHTML = `
    <div class="compare-head">
      <div>
        <p class="eyebrow">REPEATABLE PRESET COMPARISON</p>
        <h2>All scenario routes and estimated times</h2>
      </div>
      <button id="close-comparison">Close</button>
    </div>
    <p class="subtle">Each case starts from its preset inputs. "Modeled difference" is baseline estimate minus coordinated estimate.</p>
    <div class="table-scroll">
      <table>
        <thead>
          <tr>
            <th>Scenario</th>
            <th>Mission</th>
            <th>Baseline route · estimated</th>
            <th>Coordinated route · estimated</th>
            <th>Modeled difference</th>
          </tr>
        </thead>
        <tbody>
          ${rows.flatMap(s => s.missions.map(m => {
            const d = m.delta_min ?? 0;
            const cls = d > .05 ? 'positive' : d < -.05 ? 'negative' : 'neutral';
            const delta = d > .05 ? `${d.toFixed(1)} min lower (${m.benefit_pct.toFixed(0)}%)` : d < -.05 ? `${Math.abs(d).toFixed(1)} min higher` : '0.0 min';
            return `<tr>
              <td><b>${esc(s.title)}</b><br><small>Closed: ${esc(s.closures.join(', ') || 'none')}</small></td>
              <td>${esc(m.vehicle)}</td>
              <td>${esc(m.baseline_route.join(' → '))}<br><small>${m.baseline_eta.toFixed(1)} min estimate</small></td>
              <td>${esc(m.route.join(' → '))}<br><small>${m.eta.toFixed(1)} min estimate</small></td>
              <td class="${cls}">${delta}</td>
            </tr>`;
          })).join('')}
        </tbody>
      </table>
    </div>
  `;
  panel.hidden = false;
  $('#compare').textContent = 'Hide comparison';
  $('#close-comparison').onclick = () => {
    panel.hidden = true;
    $('#compare').textContent = 'Compare all 5';
  };
};
