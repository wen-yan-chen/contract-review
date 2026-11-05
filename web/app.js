/* 贷款合同审查 —— 前端逻辑（无框架、无构建） */

const state = {
  cid: null,
  contracts: [],
  clauses: [],
  risks: [],
  credit: [],
  level: 'all',
  api: false,
  renaming: null,
};

const el = (id) => document.getElementById(id);

/* ---------------- 数据访问 ---------------- */

async function fetchJSON(url, opts) {
  const res = await fetch(url, opts);
  if (!res.ok) {
    let detail = '';
    try { detail = (await res.json()).detail || ''; } catch (_) { /* ignore */ }
    throw new Error(detail || `HTTP ${res.status}`);
  }
  return res.json();
}

async function detectApi() {
  try { await fetchJSON('/api/health'); state.api = true; }
  catch (_) { state.api = false; }
}

/* ---------------- 初始化 ---------------- */

async function init() {
  await detectApi();

  if (!state.api) {
    el('btn-upload').disabled = true;
    el('btn-upload').textContent = '上传（需启动后端）';
    el('btn-new').disabled = true;
  }

  await refreshContracts();
  if (state.contracts.length) await load(state.contracts[0].cid);
  else el('doc').innerHTML = '<p class="empty">暂无合同，请上传。</p>';
}

async function refreshContracts() {
  try {
    state.contracts = state.api
      ? (await fetchJSON('/api/contracts')).contracts
      : await staticContracts();
    renderContracts();
  } catch (err) {
    el('contract-list').innerHTML = `<p class="empty">列表加载失败：${err.message}</p>`;
  }
}

async function staticContracts() {
  const split = await fetchJSON('../data/labels/split.json');
  const ids = [...split.dev, ...split.holdout].sort();
  return ids.map((cid) => ({ cid, name: cid, clauses: 0, risks: 0, uploaded: false }));
}

async function load(cid) {
  state.cid = cid;
  state.level = 'all';
  el('doc').innerHTML = '<p class="empty">加载中…</p>';

  if (state.api) {
    const data = await fetchJSON(`/api/contracts/${cid}`);
    state.clauses = data.clauses || [];
    state.risks = ((data.prediction && data.prediction.risks) || [])
      .map((r, i) => ({ ...r, _id: `r${i}` }));
    renderCredit(data.prediction);
  } else {
    const [raw, pred] = await Promise.all([
      fetchJSON(`../data/clauses/${cid}.json`),
      fetchJSON(`../data/predictions/${cid}.json`).catch(() => ({ risks: [] })),
    ]);
    state.clauses = Array.isArray(raw) ? raw : raw.clauses || [];
    state.risks = (pred.risks || []).map((r, i) => ({ ...r, _id: `r${i}` }));
    renderCredit(pred);
  }

  document.querySelectorAll('.chip').forEach((c) => c.classList.toggle('is-on', c.dataset.level === 'all'));
  renderDoc();
  renderList();
  renderMeta();
  renderContracts();
}

/* ---------------- 侧栏：合同管理 ---------------- */

function renderContracts() {
  const list = state.contracts;
  el('contract-list').innerHTML = list.length
    ? list.map(contractItem).join('')
    : '<p class="empty">暂无合同</p>';

  el('side-foot').textContent = `共 ${list.length} 份合同`;

  el('contract-list').querySelectorAll('.c-item').forEach((node) => {
    node.addEventListener('click', (e) => {
      if (e.target.closest('.c-menu') || e.target.closest('.c-rename-input')) return;
      load(node.dataset.cid);
    });
  });

  el('contract-list').querySelectorAll('.c-menu').forEach((btn) => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      openMenu(btn.dataset.cid, btn);
    });
  });
}

/* 「⋯」菜单 */
let popupEl = null;

function openMenu(cid, anchor) {
  closeMenu();
  const rect = anchor.getBoundingClientRect();
  const popup = document.createElement('div');
  popup.className = 'c-popup';
  popup.id = 'c-popup';
  popup.innerHTML = `
    <button data-act="rename">重命名</button>
    <button data-act="export">导出报告</button>
    <div class="sep"></div>
    <button data-act="delete" class="is-danger">删除</button>`;
  document.body.appendChild(popup);

  const w = 140;
  popup.style.top = `${rect.bottom + 4}px`;
  popup.style.left = `${Math.max(8, Math.min(rect.right - w, window.innerWidth - w - 8))}px`;

  anchor.classList.add('is-open');
  popupEl = { node: popup, anchor };

  popup.querySelectorAll('button').forEach((b) => {
    b.addEventListener('click', () => {
      const act = b.dataset.act;
      closeMenu();
      if (act === 'rename') startRename(cid);
      if (act === 'export') exportReport(cid);
      if (act === 'delete') removeContract(cid);
    });
  });
}

function closeMenu() {
  if (!popupEl) return;
  popupEl.node.remove();
  popupEl.anchor.classList.remove('is-open');
  popupEl = null;
}

document.addEventListener('click', () => closeMenu());
document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeMenu(); });
window.addEventListener('scroll', (e) => {
  if (popupEl && !popupEl.node.contains(e.target)) closeMenu();
}, true);

function contractItem(c) {
  const active = c.cid === state.cid ? ' is-on' : '';
  const sub = [c.cid];
  if (c.clauses) sub.push(`${c.clauses} 条`);
  if (c.risks) sub.push(`${c.risks} 处提示`);

  if (state.renaming === c.cid) {
    return `<div class="c-item${active}" data-cid="${c.cid}">
      <div class="c-main"><input class="c-rename-input" id="rename-input" value="${escapeAttr(c.name)}"></div>
    </div>`;
  }

  return `<div class="c-item${active}" data-cid="${c.cid}">
    <div class="c-main">
      <div class="c-item-name">${escapeHtml(c.name)}</div>
      <div class="c-item-sub">${escapeHtml(sub.join(' · '))}</div>
    </div>
    <button class="c-menu" data-cid="${c.cid}" title="更多操作" aria-label="更多操作">⋯</button>
  </div>`;
}

function startRename(cid) {
  if (!state.api) return;
  state.renaming = cid;
  renderContracts();
  const input = el('rename-input');
  if (!input) return;
  input.focus();
  input.select();

  const commit = async () => {
    const name = input.value.trim();
    state.renaming = null;
    if (!name || name === (state.contracts.find((c) => c.cid === cid) || {}).name) {
      renderContracts();
      return;
    }
    try {
      await fetchJSON(`/api/contracts/${cid}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name }),
      });
      await refreshContracts();
      renderMeta();
      setStatus(`已重命名为「${name}」`, 'done');
    } catch (err) {
      setStatus(`重命名失败：${err.message}`, 'error');
      renderContracts();
    }
  };

  input.addEventListener('blur', commit);
  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') { e.preventDefault(); input.blur(); }
    if (e.key === 'Escape') { state.renaming = null; renderContracts(); }
  });
}

function exportReport(cid) {
  if (!state.api) { openPrintView(); return; }
  window.open(`/api/contracts/${cid}/export?format=docx`, '_blank');
}

/* 独立打印视图：新开窗口，只含报告内容，不受页面布局影响 */
function openPrintView() {
  if (!state.clauses.length) {
    setStatus('请先选择或上传一份合同', 'error');
    return;
  }

  const name = currentName();
  const now = new Date().toLocaleString('zh-CN', { hour12: false });
  const counts = { 高: 0, 中: 0, 低: 0 };
  state.risks.forEach((r) => { counts[r.risk_level] = (counts[r.risk_level] || 0) + 1; });

  const riskBlocks = state.risks.map((r, i) => {
    const basis = typeof r.legal_basis === 'string'
      ? r.legal_basis
      : (r.legal_basis && r.legal_basis.name) || '未检索到权威依据';
    return `<section class="item">
      <h3><span class="tag t-${r.risk_level}">${escapeHtml(r.risk_level || '')}</span>
        ${i + 1}. ${escapeHtml(r.risk_type || '')}</h3>
      <p class="meta">${escapeHtml(r.clause_no || '')}　规则 ${escapeHtml(r.rule_id || '')}</p>
      <p class="quote">${escapeHtml(r.quote || '')}</p>
      <p><span class="k">问题：</span>${escapeHtml(r.problem || '')}</p>
      <p><span class="k">建议：</span>${escapeHtml(r.suggestion || '')}</p>
      <p class="meta"><span class="k">依据：</span>${escapeHtml(basis)}</p>
    </section>`;
  }).join('') || '<p class="empty">未发现需要提示的条款。</p>';

  const creditRows = state.credit.map((c) => `<tr>
      <td>${escapeHtml(labelOf(c.field))}</td>
      <td>${escapeHtml(c.contract_value ?? '')}</td>
      <td>${escapeHtml(c.credit_report_value ?? '')}</td>
      <td>${escapeHtml(c.note || '')}</td>
    </tr>`).join('');

  const creditBlock = state.credit.length ? `
    <h2>授信批复比对</h2>
    <table><thead><tr><th>要素</th><th>合同</th><th>授信批复</th><th>说明</th></tr></thead>
    <tbody>${creditRows}</tbody></table>` : '';

  const doc = `<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>${escapeHtml(name)} - 审查报告</title>
<style>
  @page { size: A4; margin: 18mm 16mm; }
  * { box-sizing: border-box; }
  body { font-family: "Songti SC", SimSun, "Microsoft YaHei", serif;
         color: #111; font-size: 10.5pt; line-height: 1.75; margin: 0; }
  h1 { font-size: 16pt; text-align: center; margin: 0 0 4px; letter-spacing: 1px; }
  .sub { text-align: center; font-size: 9pt; color: #555; margin-bottom: 6px; }
  .rule { border: none; border-top: 1px solid #333; margin: 10px 0 14px; }
  .stat { display: flex; justify-content: center; gap: 18px; font-size: 9.5pt;
          color: #333; margin-bottom: 12px; }
  h2 { font-size: 11.5pt; margin: 18px 0 8px; padding-bottom: 3px;
       border-bottom: 1px solid #bbb; }
  .item { margin-bottom: 14px; page-break-inside: avoid; }
  .item h3 { font-size: 10.5pt; margin: 0 0 4px; }
  .item p { margin: 3px 0; text-align: justify; }
  .meta { font-size: 9pt; color: #555; }
  .quote { border-left: 3px solid #bbb; padding: 4px 8px; background: #f6f6f6;
           font-size: 9.5pt; color: #222; }
  .k { color: #555; }
  .tag { display: inline-block; font-size: 8.5pt; padding: 0 5px; border: 1px solid #999;
         border-radius: 2px; margin-right: 5px; }
  .t-高 { color: #a32020; border-color: #a32020; }
  .t-中 { color: #8a5a00; border-color: #8a5a00; }
  .t-低 { color: #444; }
  table { width: 100%; border-collapse: collapse; font-size: 9pt; margin-top: 6px; }
  th, td { border: 1px solid #999; padding: 4px 6px; text-align: left; vertical-align: top; }
  th { background: #f0f0f0; font-weight: 600; }
  .foot { margin-top: 18px; padding-top: 8px; border-top: 1px solid #ccc;
          font-size: 8.5pt; color: #666; }
  .empty { color: #666; }
</style></head>
<body>
  <h1>贷款合同审查报告</h1>
  <div class="sub">${escapeHtml(name)}（${escapeHtml(state.cid || '')}）</div>
  <hr class="rule">
  <div class="stat">
    <span>条款 ${state.clauses.length} 条</span>
    <span>风险 ${state.risks.length} 处</span>
    <span>高 ${counts.高} / 中 ${counts.中} / 低 ${counts.低}</span>
    <span>${escapeHtml(now)}</span>
  </div>

  <h2>审查意见</h2>
  ${riskBlocks}
  ${creditBlock}

  <div class="foot">
    本报告由系统自动生成，仅作为合同审查的辅助参考，不构成法律意见；
    最终以法务与审批人员的书面意见为准。未取得原文依据的条目显示为「未检索到权威依据」，需人工复核。
  </div>
</body></html>`;

  const win = window.open('', '_blank');
  if (!win) {
    setStatus('浏览器拦截了新窗口，请允许弹窗后重试', 'error');
    return;
  }
  win.document.open();
  win.document.write(doc);
  win.document.close();
  win.focus();
  setTimeout(() => win.print(), 350);
}

async function removeContract(cid) {
  if (!state.api) return;
  const item = state.contracts.find((c) => c.cid === cid);
  const name = item ? item.name : cid;
  if (!window.confirm(`确认删除「${name}」？\n该合同原文与审查结果将被移除，不可恢复。`)) return;

  try {
    await fetchJSON(`/api/contracts/${cid}`, { method: 'DELETE' });
    if (state.cid === cid) {
      state.cid = null;
      state.clauses = [];
      state.risks = [];
      el('doc').innerHTML = '<p class="empty">已删除，请选择其他合同。</p>';
      el('risk-list').innerHTML = '';
      el('summary').textContent = '';
      el('contract-meta').textContent = '';
      el('credit-block').hidden = true;
    }
    await refreshContracts();
    setStatus(`已删除「${name}」`, 'done');
  } catch (err) {
    setStatus(`删除失败：${err.message}`, 'error');
  }
}

/* ---------------- 上传 → 解析 → 审查 ---------------- */

async function handleUpload(file) {
  if (!state.api) return;

  const name = file.name || '';
  const ext = name.slice(name.lastIndexOf('.')).toLowerCase();
  if (!['.docx', '.pdf', '.txt', '.md'].includes(ext)) {
    setStatus('仅支持 docx / pdf / txt / md 文件', 'error');
    return;
  }

  setStatus(`正在解析 ${name} …`, 'loading');
  const form = new FormData();
  form.append('file', file);

  try {
    const up = await fetchJSON('/api/upload', { method: 'POST', body: form });
    setStatus(`已解析 ${up.clauses} 条条款（${up.chars} 字），正在调用审查智能体 …`, 'loading');

    await refreshContracts();
    await load(up.cid);

    const result = await fetchJSON(`/api/review/${up.cid}`, { method: 'POST' });
    const seconds = (result._meta && result._meta.elapsed_seconds) || '';

    state.risks = (result.risks || []).map((r, i) => ({ ...r, _id: `r${i}` }));
    renderDoc();
    renderList();
    renderCredit(result);
    renderMeta(seconds);
    await refreshContracts();

    setStatus(`审查完成：${state.risks.length} 处提示${seconds ? `，用时 ${seconds} 秒` : ''}`, 'done');
  } catch (err) {
    setStatus(`处理失败：${err.message}`, 'error');
  }
}

/* ---------------- 状态条 ---------------- */

let statusTimer = null;
function setStatus(text, kind = 'loading') {
  const bar = el('statusbar');
  bar.hidden = false;
  bar.className = 'statusbar' +
    (kind === 'error' ? ' is-error' : '') + (kind === 'done' ? ' is-done' : '');
  el('status-text').textContent = text;
  clearTimeout(statusTimer);
  if (kind === 'done' || kind === 'error') {
    statusTimer = setTimeout(() => { bar.hidden = true; }, 8000);
  }
}

/* ---------------- 原文渲染 ---------------- */

function clauseBody(c) {
  let t = (c.text || '').trim();
  const no = c.clause_no || '';
  if (no && t.startsWith(no)) t = t.slice(no.length).replace(/^[\s\u3000]+/, '');
  return t;
}

function renderDoc() {
  const html = state.clauses.map((c) => {
    const body = clauseBody(c);
    const mine = state.risks.filter((r) => r.clause_no === c.clause_no);

    const marks = [];
    mine.forEach((r) => {
      const q = (r.quote || '').trim();
      if (!q) return;
      const idx = body.indexOf(q);
      if (idx < 0) return;
      const start = idx;
      const end = idx + q.length;
      if (marks.some((m) => start < m.end && end > m.start)) return;
      marks.push({ start, end, level: r.risk_level || '低', rid: r._id });
    });
    marks.sort((a, b) => a.start - b.start);

    let out = '';
    let cursor = 0;
    marks.forEach((m) => {
      out += escapeHtml(body.slice(cursor, m.start));
      out += `<mark class="lv-${m.level}" data-rid="${m.rid}">${escapeHtml(body.slice(m.start, m.end))}</mark>`;
      cursor = m.end;
    });
    out += escapeHtml(body.slice(cursor));

    return `<p class="clause" data-clause="${escapeAttr(c.clause_no)}">
      <span class="clause-no">${escapeHtml(c.clause_no)}</span>${out}
    </p>`;
  }).join('');

  el('doc').innerHTML = `
    <h1>${escapeHtml(currentName())}</h1>
    <div class="doc-sub">${escapeHtml(state.cid || '')} · 共 ${state.clauses.length} 条</div>
    ${html}`;

  el('doc-meta').textContent = `${state.clauses.length} 条 · ${state.risks.length} 处提示`;

  el('doc').querySelectorAll('mark').forEach((mk) => {
    mk.addEventListener('click', (e) => {
      e.stopPropagation();
      focusRisk(mk.dataset.rid, false);
    });
  });
}

function currentName() {
  const item = state.contracts.find((c) => c.cid === state.cid);
  return item ? item.name : (state.cid || '贷款合同');
}

/* ---------------- 审查意见 ---------------- */

function filteredRisks() {
  return state.level === 'all'
    ? state.risks
    : state.risks.filter((r) => r.risk_level === state.level);
}

function renderList() {
  const list = filteredRisks();
  el('risk-list').innerHTML = list.length
    ? list.map(riskCard).join('')
    : `<p class="empty">${state.risks.length ? '当前筛选下没有条目。' : '未发现需要提示的条款。'}</p>`;

  el('risk-list').querySelectorAll('.risk').forEach((node) => {
    node.addEventListener('click', () => focusRisk(node.dataset.rid, true));
  });

  const counts = { 高: 0, 中: 0, 低: 0 };
  state.risks.forEach((r) => { counts[r.risk_level] = (counts[r.risk_level] || 0) + 1; });
  document.querySelectorAll('.chip-n').forEach((n) => {
    n.textContent = counts[n.dataset.n] ?? 0;
  });

  el('summary').textContent = state.risks.length
    ? `共 ${state.risks.length} 处：高 ${counts.高} / 中 ${counts.中} / 低 ${counts.低}`
    : '未提示风险';
}

function riskCard(r) {
  const level = r.risk_level || '低';
  const basis = typeof r.legal_basis === 'string'
    ? r.legal_basis
    : (r.legal_basis && r.legal_basis.name) || '';

  return `<article class="risk lv-${level}" data-rid="${r._id}">
    <div class="risk-head">
      <span class="lvl ${level}">${level}</span>
      <span class="risk-title">${escapeHtml(r.risk_type || '')}</span>
      <span class="risk-ref">${escapeHtml(r.clause_no || '')} · ${escapeHtml(r.rule_id || '')}</span>
    </div>
    <div class="risk-quote">${escapeHtml(r.quote || '')}</div>
    <div class="risk-field"><span class="k">问题</span>${escapeHtml(r.problem || '')}</div>
    <div class="risk-field"><span class="k">建议</span></div>
    <div class="risk-suggest">${escapeHtml(r.suggestion || '')}</div>
    ${basis ? `<div class="risk-field" style="margin-top:7px"><span class="k">依据</span><span class="basis-note">${escapeHtml(basis)}</span></div>` : ''}
  </article>`;
}

/* ---------------- 联动 ---------------- */

function focusRisk(rid, fromList) {
  const risk = state.risks.find((r) => r._id === rid);
  if (!risk) return;

  document.querySelectorAll('.risk').forEach((n) => n.classList.toggle('is-active', n.dataset.rid === rid));
  document.querySelectorAll('mark').forEach((n) => n.classList.toggle('is-active', n.dataset.rid === rid));
  document.querySelectorAll('.clause').forEach((n) => n.classList.remove('is-target'));

  const clause = document.querySelector(`.clause[data-clause="${cssEscape(risk.clause_no)}"]`);
  if (clause) {
    clause.classList.add('is-target');
    if (fromList) clause.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }
  if (!fromList) {
    const card = document.querySelector(`.risk[data-rid="${rid}"]`);
    if (card) card.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }
}

/* ---------------- 授信比对 ---------------- */

function renderCredit(pred) {
  const checks = (pred && pred.consistency_checks) || [];
  state.credit = checks;
  const block = el('credit-block');
  if (!checks.length) { block.hidden = true; return; }

  block.hidden = false;
  const rows = checks.map((c) => {
    const same = String(c.contract_value) === String(c.credit_report_value);
    return `<tr>
      <td>${escapeHtml(labelOf(c.field))}</td>
      <td class="${same ? '' : 'diff'}">${escapeHtml(c.contract_value ?? '')}</td>
      <td>${escapeHtml(c.credit_report_value ?? '')}</td>
      <td>${escapeHtml(c.note || '')}</td>
    </tr>`;
  }).join('');

  el('credit-table').innerHTML = `
    <thead><tr><th>要素</th><th>合同</th><th>授信批复</th><th>说明</th></tr></thead>
    <tbody>${rows}</tbody>`;
}

function labelOf(field) {
  const map = {
    loan_amount: '贷款金额', amount: '贷款金额',
    execution_rate: '执行利率', rate: '执行利率',
    guarantee: '担保方式', guarantee_type: '担保方式',
    term: '期限', term_months: '期限', conditions: '放款条件',
  };
  return map[field] || field;
}

function renderMeta(seconds) {
  el('contract-meta').textContent =
    `${currentName()} · ${state.clauses.length} 条条款` +
    (seconds ? ` · 用时 ${seconds}s` : '');
  el('foot-note').innerHTML =
    '依据规则库自动匹配，共比对 40 条审查规则。' +
    '未取得原文依据的条目显示为「未检索到权威依据」，需人工复核。';
}

/* ---------------- 工具 ---------------- */

function escapeHtml(s) {
  return String(s ?? '')
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
const escapeAttr = escapeHtml;
function cssEscape(s) { return String(s ?? '').replace(/"/g, '\\"'); }

/* ---------------- 事件 ---------------- */

el('filter-row').addEventListener('click', (e) => {
  const btn = e.target.closest('.chip');
  if (!btn) return;
  state.level = btn.dataset.level;
  document.querySelectorAll('.chip').forEach((c) => c.classList.toggle('is-on', c === btn));
  renderList();
});

el('btn-upload').addEventListener('click', () => el('file-input').click());

el('file-input').addEventListener('change', (e) => {
  const file = e.target.files && e.target.files[0];
  if (file) handleUpload(file);
  e.target.value = '';
});

el('btn-print').addEventListener('click', () => openPrintView());

document.addEventListener('dragover', (e) => { e.preventDefault(); });
document.addEventListener('drop', (e) => {
  e.preventDefault();
  const file = e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0];
  if (file) handleUpload(file);
});

/* ---------------- 侧栏折叠 ---------------- */

el('btn-side').addEventListener('click', () => {
  const collapsed = document.body.classList.toggle('side-collapsed');
  localStorage.setItem('sideCollapsed', collapsed ? '1' : '0');
  document.body.style.setProperty('--side-w', collapsed ? '0px' : '248px');
});

if (localStorage.getItem('sideCollapsed') === '1') {
  document.body.classList.add('side-collapsed');
}

/* ---------------- 拖拽调整左右宽度 ---------------- */

(function initResizer() {
  const layout = document.querySelector('.layout');
  const handle = el('resizer');
  let dragging = false;

  const saved = localStorage.getItem('reviewW');
  if (saved) document.documentElement.style.setProperty('--review-w', `${saved}%`);

  handle.addEventListener('pointerdown', (e) => {
    dragging = true;
    handle.classList.add('is-dragging');
    handle.setPointerCapture(e.pointerId);
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
  });

  window.addEventListener('pointermove', (e) => {
    if (!dragging) return;
    const rect = layout.getBoundingClientRect();
    const rightWidth = rect.right - e.clientX;
    const pct = Math.max(24, Math.min(58, (rightWidth / rect.width) * 100));
    document.documentElement.style.setProperty('--review-w', `${pct.toFixed(1)}%`);
    localStorage.setItem('reviewW', pct.toFixed(1));
  });

  const stop = () => {
    if (!dragging) return;
    dragging = false;
    handle.classList.remove('is-dragging');
    document.body.style.cursor = '';
    document.body.style.userSelect = '';
  };
  window.addEventListener('pointerup', stop);
  window.addEventListener('pointercancel', stop);
})();

init();
