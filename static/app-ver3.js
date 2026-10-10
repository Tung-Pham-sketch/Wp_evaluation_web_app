const $ = selector => document.querySelector(selector);
const $$ = selector => [...document.querySelectorAll(selector)];

const state = {
  view: 'dashboard',
  dashboard: null,
  currentTally: null,
  workflow: null,
  workflowStep: 1,
  detail: null,
  reviewTab: 'detail',
  reviewPage: 1,
  reviewQuery: '',
  reviewStatus: 'all',
  sortBy: 'seq',
  sortDir: 'asc',
  visibleItems: [],
  editItem: null,
  dataTab: 'amos_vna',
  dataPage: 1,
  dataQuery: '',
  dataFilters: {aircraft_type: 'all', customer: 'all', classification: 'all', category: 'all', external_status: 'all'},
  dataResult: null,
};

const fmt = value => new Intl.NumberFormat('vi-VN', {maximumFractionDigits: 2}).format(value || 0);
const esc = value => String(value ?? '').replace(/[&<>"']/g, character => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[character]));
const badge = (text, color = 'blue') => `<span class="badge ${color}">${esc(text)}</span>`;

function toast(text) {
  const element = $('#toast');
  element.textContent = text;
  element.classList.add('show');
  setTimeout(() => element.classList.remove('show'), 2800);
}

async function api(url, options) {
  const response = await fetch(url, options);
  if (!response.ok) {
    let error;
    try { error = await response.json(); } catch {}
    throw new Error(error?.detail || 'Có lỗi xảy ra');
  }
  return response.json();
}

async function loadDashboard(render = true) {
  state.dashboard = await api('/api/dashboard');
  if (!render) return;
  if (state.view === 'dashboard') renderDashboard();
  if (state.view === 'workflow' && !state.currentTally) renderWorkflowHub();
}

function progressLabel(workflow) {
  const step = workflow.steps?.find(item => item.number === workflow.current_step);
  return step ? `Bước ${step.number}: ${step.label}` : 'Đã hoàn tất quy trình';
}

function workflowTable(rows) {
  return `<table class="workflow-list"><thead><tr><th>Khách hàng</th><th>Ngày bắt đầu</th><th>Mô tả</th><th>Check</th><th>Tiến độ</th><th>Trạng thái</th><th></th></tr></thead><tbody>${rows.map(item => `
    <tr>
      <td><b>${esc(item.customer || '—')}</b><br><small>${esc(item.aircraft_reg || item.aircraft_type || '—')}</small></td>
      <td>${new Date(item.uploaded_at).toLocaleDateString('vi-VN')}</td>
      <td><b>${esc(item.description || item.file_name)}</b><br><small>${esc(item.file_name)}</small></td>
      <td>${esc(item.check_type || '—')}</td>
      <td><b>${item.progress}%</b><small>${esc(progressLabel(item))}</small><div class="progress"><i style="width:${item.progress}%"></i></div></td>
      <td>${badge(item.status, item.status === 'Hoàn tất' ? 'green' : 'amber')}</td>
      <td><button class="link open-workflow" data-tally="${item.tally_id}">Tiếp tục</button></td>
    </tr>`).join('') || '<tr><td colspan="7" class="empty">Chưa có hồ sơ chào thầu</td></tr>'}</tbody></table>`;
}

function renderDashboard() {
  const data = state.dashboard;
  const rows = data.workflows || [];
  $('#dashboardView').innerHTML = `
    <div class="workbar"><h2>Danh sách chào thầu</h2><span class="badge blue">${rows.length} bộ hồ sơ</span><span class="spacer"></span><span>MiniDB: <b>${fmt(data.amp_count)}</b> task</span></div>
    <div class="cards" style="grid-template-columns:minmax(260px,360px)"><div class="card metric"><span>Số bộ hồ sơ chào thầu đã tiếp nhận</span><strong>${fmt(data.totals.tally_count)}</strong><small>Tiến độ tính theo quy trình 5 bước</small></div></div>
    <div class="panel"><div class="toolbar"><input id="workflowSearch" placeholder="Tìm khách hàng, mô tả, Check hoặc trạng thái"><select id="workflowStatus"><option value="all">Tất cả trạng thái</option>${[...new Set(rows.map(item => item.status))].map(status => `<option>${esc(status)}</option>`).join('')}</select><span class="spacer"></span><button class="ghost" id="dashboardRefresh">↻ Làm mới</button><button class="primary create-tally">＋ Tạo hồ sơ</button></div><div class="table-wrap">${workflowTable(rows)}</div></div>`;
  const applyFilters = () => {
    const query = $('#workflowSearch').value.trim().toLowerCase();
    const status = $('#workflowStatus').value;
    const filtered = rows.filter(item => (status === 'all' || item.status === status) && (!query || [item.customer, item.description, item.file_name, item.check_type, item.status, item.tally_id].some(value => String(value || '').toLowerCase().includes(query))));
    $('#dashboardView .table-wrap').innerHTML = workflowTable(filtered);
    bindWorkflowOpen();
  };
  $('#workflowSearch').oninput = applyFilters;
  $('#workflowStatus').onchange = applyFilters;
  $('#dashboardRefresh').onclick = () => loadDashboard();
  $$('.create-tally').forEach(button => button.onclick = () => $('#uploadDialog').showModal());
  bindWorkflowOpen();
}

function renderWorkflowHub() {
  const rows = state.dashboard?.workflows || [];
  $('#workflowView').innerHTML = `
    <div class="hero-strip"><div><h2>Quy trình đánh giá Workpack</h2><p>Thực hiện lần lượt từ tiếp nhận Tally Sheet đến review và xuất báo cáo</p></div><button class="primary create-tally">＋ Bắt đầu hồ sơ mới</button></div>
    <div class="workflow-guide"><div><b>1</b><span>Tiếp nhận</span></div><i></i><div><b>2</b><span>Đọc sơ bộ</span></div><i></i><div><b>3</b><span>Đánh giá</span></div><i></i><div><b>4</b><span>Review</span></div><i></i><div><b>5</b><span>Hoàn thiện</span></div></div>
    <div class="panel"><div class="panel-head"><div><h2>Hồ sơ đang xử lý</h2><p>Chọn một hồ sơ để tiếp tục từ bước gần nhất</p></div><b>${rows.length} hồ sơ</b></div><div class="table-wrap">${workflowTable(rows)}</div></div>`;
  $$('.create-tally').forEach(button => button.onclick = () => $('#uploadDialog').showModal());
  bindWorkflowOpen();
}

function bindWorkflowOpen() {
  $$('.open-workflow').forEach(button => button.onclick = () => openWorkflow(button.dataset.tally));
}

async function openWorkflow(tallyId, requestedStep = null) {
  state.currentTally = tallyId;
  state.workflowStep = requestedStep || 0;
  state.detail = null;
  state.reviewPage = 1;
  state.reviewQuery = '';
  state.reviewStatus = 'all';
  showView('workflow', false);
  await loadWorkflow(requestedStep);
}

async function loadWorkflow(requestedStep = null) {
  state.workflow = await api(`/api/workflows/${state.currentTally}`);
  if (requestedStep !== null) state.workflowStep = requestedStep;
  else if (!state.workflowStep) state.workflowStep = state.workflow.current_step;
  renderWorkflow();
}

function stepStatusText(status) {
  return status === 'completed' ? 'Hoàn thành' : status === 'in_progress' ? 'Đang thực hiện' : 'Chưa bắt đầu';
}

function renderWorkflow() {
  const workflow = state.workflow;
  const tally = workflow.tally;
  const earlierMissing = workflow.steps.filter(step => step.number < state.workflowStep && step.status !== 'completed');
  $('#workflowView').innerHTML = `
    <div class="eval-head workflow-head"><div><button class="link" id="backWorkflow">‹ Danh sách quy trình</button><h2>${esc(tally.description || tally.file_name)}</h2><p>${esc(tally.customer)} · ${esc(tally.aircraft_reg || tally.aircraft_type || '—')} · ${esc(tally.check_type || '—')}</p></div><div class="workflow-score"><strong>${workflow.progress}%</strong><span>${workflow.completed_steps}/5 bước hoàn thành</span></div></div>
    <div class="workflow-progress"><i style="width:${workflow.progress}%"></i></div>
    <div class="workflow-layout"><div class="step-rail">${workflow.steps.map(step => `<button class="workflow-step ${step.status} ${state.workflowStep === step.number ? 'active' : ''}" data-step="${step.number}"><b>${step.number}</b><span>${esc(step.label)}<small>${stepStatusText(step.status)}</small></span></button>`).join('')}</div><div class="workflow-main">${earlierMissing.length ? `<div class="notice">Bạn đang mở trước một bước chưa hoàn thành. Có thể tiếp tục xem, nhưng hệ thống sẽ cảnh báo các dữ liệu còn thiếu.</div>` : ''}<div id="workflowStepContent"></div></div></div>`;
  $('#backWorkflow').onclick = () => { state.currentTally = null; state.workflow = null; renderWorkflowHub(); };
  $$('.workflow-step').forEach(button => button.onclick = () => { state.workflowStep = Number(button.dataset.step); renderWorkflow(); });
  renderWorkflowStep().catch(error => { $('#workflowStepContent').innerHTML = `<div class="notice">${esc(error.message)}</div>`; });
}

function stepHeader(number, title, description) {
  return `<div class="step-heading"><div class="step-number">${number}</div><div><h2>${title}</h2><p>${description}</p></div></div>`;
}

async function renderWorkflowStep() {
  const host = $('#workflowStepContent');
  const workflow = state.workflow;
  const tally = workflow.tally;
  if (state.workflowStep === 1) {
    host.innerHTML = `${stepHeader(1, 'Tiếp nhận Tally Sheet', 'Thông tin và file gốc của hồ sơ chào thầu')}
      <div class="instruction">Hồ sơ đã được tiếp nhận. File được khóa sau khi chạy đánh giá sơ bộ để đảm bảo truy vết.</div>
      <div class="detail-grid intake-summary">${[['Khách hàng', tally.customer], ['Mô tả', tally.description || tally.file_name], ['Số đăng ký', tally.aircraft_reg], ['Loại tàu bay', tally.aircraft_type], ['Check Type', tally.check_type], ['Người nạp', tally.uploader], ['Thời điểm', new Date(tally.uploaded_at).toLocaleString('vi-VN')]].map(([label, value]) => `<div class="detail-field"><span>${label}</span><b>${esc(value || '—')}</b></div>`).join('')}<div class="detail-field wide"><span>File Tally Sheet</span><b>${esc(tally.file_name)}</b><a class="link" href="/api/tally/${tally.id}/download">Tải file gốc</a></div></div>
      <div class="step-actions"><button class="primary next-step">Tiếp tục đọc sơ bộ →</button></div>`;
    $('.next-step').onclick = () => { state.workflowStep = 2; renderWorkflow(); };
    return;
  }
  if (state.workflowStep === 2) return renderInspectionStep(host);
  if (state.workflowStep === 3) return renderEvaluationStep(host);
  if (state.workflowStep === 4) return renderReviewStep(host);
  return renderFinalizeStep(host);
}

function workflowStep(code) {
  return state.workflow.steps.find(step => step.code === code);
}

function setBusy(button, busyText) {
  const original = button.textContent;
  button.disabled = true;
  button.textContent = busyText;
  return () => { button.disabled = false; button.textContent = original; };
}

function renderInspectionStep(host) {
  const step = workflowStep('inspect');
  const result = step.details || {};
  const hasResult = Boolean(result.row_count);
  host.innerHTML = `${stepHeader(2, 'Đọc và kiểm tra sơ bộ', 'Nhận diện cấu trúc file trước khi matching với AMOS')}
    <div class="instruction"><b>Cần kiểm tra:</b> mẫu Tally, số dòng đọc được, các cột nhận diện và cảnh báo metadata. Bước này chưa tạo kết quả đánh giá.</div>
    ${hasResult ? `<div class="cards inspection-cards"><div class="card metric"><span>Mẫu nhận diện</span><strong>${esc(result.adapter)}</strong></div><div class="card metric"><span>Dòng nghiệp vụ</span><strong>${fmt(result.row_count)}</strong></div><div class="card metric"><span>Sheet</span><strong>${esc(result.active_sheet || '—')}</strong></div><div class="card metric"><span>Mã trùng</span><strong>${fmt(result.duplicate_count)}</strong></div></div>
      ${result.warnings?.length ? `<div class="notice"><b>Cảnh báo dữ liệu</b><ul>${result.warnings.map(item => `<li>${esc(item)}</li>`).join('')}</ul></div>` : '<div class="success-note">Không phát hiện cảnh báo dữ liệu đầu vào.</div>'}
      <div class="panel"><div class="panel-head"><div><h3>Dữ liệu mẫu đã đọc</h3><p>${esc((result.detected_columns || []).join(' · ') || 'Không có danh sách cột')}</p></div></div><div class="table-wrap"><table><thead><tr><th>STT</th><th>Task/CRI</th><th>Title</th><th>Section</th></tr></thead><tbody>${(result.sample_rows || []).map(row => `<tr><td>${esc(row.seq || '—')}</td><td><b>${esc(row.task_no)}</b></td><td>${esc(row.title || '—')}</td><td>${esc(row.section || '—')}</td></tr>`).join('')}</tbody></table></div></div>` : '<div class="empty-step">Chưa đọc file. Bấm “Đọc sơ bộ” để kiểm tra cấu trúc Tally Sheet.</div>'}
    <div class="step-actions"><button class="ghost" id="inspectTally">${hasResult ? '↻ Đọc lại' : 'Đọc sơ bộ'}</button>${hasResult && !result.confirmed ? '<button class="primary" id="confirmInspection">Xác nhận dữ liệu đầu vào</button>' : ''}${result.confirmed ? '<span class="success-text">✓ Đã xác nhận dữ liệu đầu vào</span><button class="primary next-step">Chuyển sang đánh giá →</button>' : ''}</div>`;
  $('#inspectTally').onclick = async event => {
    const restore = setBusy(event.currentTarget, 'Đang đọc file…');
    try { await api(`/api/tallies/${state.currentTally}/inspect`, {method: 'POST'}); toast('Đã đọc sơ bộ Tally Sheet'); await loadWorkflow(2); }
    catch (error) { toast(error.message); restore(); }
  };
  const confirm = $('#confirmInspection');
  if (confirm) confirm.onclick = async event => {
    const restore = setBusy(event.currentTarget, 'Đang xác nhận…');
    try { await api(`/api/tallies/${state.currentTally}/inspection/confirm`, {method: 'POST'}); toast('Đã xác nhận dữ liệu đầu vào'); await loadWorkflow(2); }
    catch (error) { toast(error.message); restore(); }
  };
  const next = $('.next-step');
  if (next) next.onclick = () => { state.workflowStep = 3; renderWorkflow(); };
}

function renderEvaluationStep(host) {
  const evaluation = state.workflow.evaluation;
  const summary = state.workflow.summary;
  const inspection = workflowStep('inspect');
  host.innerHTML = `${stepHeader(3, 'Chạy đánh giá sơ bộ', 'Đối chiếu chính xác Task/CRI với MiniDB AMOS')}
    <div class="instruction">Hệ thống chỉ matching mã chính xác, không phân biệt hoa thường. Task không match vẫn được giữ và không tự gán MHR.</div>
    ${inspection.status !== 'completed' ? '<div class="notice">Bước đọc sơ bộ chưa được xác nhận. Bạn vẫn có thể xem bước này, nhưng cần xác nhận dữ liệu trước khi đánh giá.</div>' : ''}
    ${evaluation ? `<div class="cards"><div class="card metric"><span>Tổng task</span><strong>${fmt(summary.total)}</strong></div><div class="card metric"><span>Khớp AMOS</span><strong>${fmt(summary.matched)}</strong><small>${summary.total ? Math.round(summary.matched * 100 / summary.total) : 0}% tổng task</small></div><div class="card metric"><span>Chưa có trong DB</span><strong>${fmt(summary.unmatched)}</strong></div><div class="card metric"><span>Important Job</span><strong>${fmt(summary.important)}</strong></div></div><div class="result-callout"><b>Đánh giá sơ bộ đã hoàn thành</b><span>Mã đánh giá: ${esc(evaluation.id)} · Tổng MHR hiện có: ${fmt(summary.total_mhr)}</span></div>` : '<div class="empty-step">Chưa có kết quả đánh giá sơ bộ. Thao tác này sẽ tạo Detailed Task List và các danh sách ngoại lệ.</div>'}
    <div class="step-actions">${evaluation ? '<button class="primary next-step">Mở bước Review →</button>' : '<button class="primary" id="runEvaluation">Chạy đánh giá sơ bộ</button>'}</div>`;
  const run = $('#runEvaluation');
  if (run) run.onclick = async event => {
    const restore = setBusy(event.currentTarget, 'Đang đối chiếu AMOS…');
    try { const result = await api(`/api/tallies/${state.currentTally}/evaluate`, {method: 'POST'}); toast(result.reused ? 'Đã sử dụng kết quả hiện có' : 'Đã hoàn thành đánh giá sơ bộ'); state.detail = null; await loadWorkflow(3); }
    catch (error) { toast(error.message); restore(); }
  };
  const next = $('.next-step');
  if (next) next.onclick = () => { state.workflowStep = 4; renderWorkflow(); };
}

async function ensureDetail() {
  const evaluationId = state.workflow.evaluation?.id;
  if (!evaluationId) return null;
  state.detail = await api(`/api/evaluations/${evaluationId}?q=${encodeURIComponent(state.reviewQuery)}&status=${state.reviewStatus}&page=${state.reviewPage}&sort_by=${state.sortBy}&sort_dir=${state.sortDir}`);
  return state.detail;
}

async function renderReviewStep(host) {
  const evaluation = state.workflow.evaluation;
  if (!evaluation) {
    host.innerHTML = `${stepHeader(4, 'Review kết quả', 'Kiểm tra dữ liệu chi tiết và các ngoại lệ')}<div class="notice">Chưa có kết quả đánh giá sơ bộ. Hãy hoàn thành bước 3 trước.</div>`;
    return;
  }
  const review = workflowStep('review');
  const checklist = review.details?.checklist || {detail: false, important: false, database: false};
  host.innerHTML = `${stepHeader(4, 'Review kết quả', 'Mở từng nhóm dữ liệu, xử lý ngoại lệ và xác nhận checklist')}
    <div class="review-checklist">
      ${reviewCheck('detail', 'Detailed Task List', 'Kiểm tra danh sách task, MHR và dữ liệu matching', checklist.detail)}
      ${reviewCheck('important', 'Important Jobs', 'Kiểm tra Watch Item và các đánh dấu thủ công', checklist.important)}
      ${reviewCheck('database', 'Database to be Updated', 'Kiểm tra task chưa có trong MiniDB', checklist.database)}
      <div class="review-card na"><div><b>Ngoài Check Scope</b><span>Chưa có dữ liệu Task–Check/Linked Check</span></div><em>Không áp dụng</em></div>
    </div>
    <div class="tabs review-tabs"><button class="tab ${state.reviewTab === 'detail' ? 'active' : ''}" data-review-tab="detail">Detailed Task List</button><button class="tab ${state.reviewTab === 'important' ? 'active' : ''}" data-review-tab="important">Important Jobs</button><button class="tab ${state.reviewTab === 'database' ? 'active' : ''}" data-review-tab="database">Database to be Updated</button><button class="tab ${state.reviewTab === 'scope' ? 'active' : ''}" data-review-tab="scope">Ngoài Check Scope</button><button class="tab ${state.reviewTab === 'history' ? 'active' : ''}" data-review-tab="history">Lịch sử</button></div>
    <div id="reviewPanel"><div class="empty">Đang tải dữ liệu review…</div></div>
    <div class="step-actions"><span class="${review.status === 'completed' ? 'success-text' : 'muted-text'}">${review.status === 'completed' ? '✓ Đã hoàn thành checklist Review' : 'Xác nhận đủ ba nhóm để hoàn thành bước Review'}</span><button class="primary next-step">Hoàn thiện & xuất báo cáo →</button></div>`;
  $$('.review-card[data-review-target]').forEach(card => card.onclick = event => {
    if (event.target.matches('input')) return;
    state.reviewTab = card.dataset.reviewTarget;
    renderWorkflow();
  });
  $$('.review-confirm').forEach(input => input.onchange = saveReviewChecklist);
  $$('[data-review-tab]').forEach(button => button.onclick = () => { state.reviewTab = button.dataset.reviewTab; renderWorkflow(); });
  $('.next-step').onclick = () => { state.workflowStep = 5; renderWorkflow(); };
  await renderReviewPanel();
}

function reviewCheck(key, title, description, checked) {
  return `<div class="review-card ${checked ? 'done' : ''}" data-review-target="${key}"><div><b>${title}</b><span>${description}</span></div><label class="check"><input class="review-confirm" data-key="${key}" type="checkbox" ${checked ? 'checked' : ''}> Đã review</label></div>`;
}

async function saveReviewChecklist() {
  const body = {};
  $$('.review-confirm').forEach(input => body[input.dataset.key] = input.checked);
  try {
    await api(`/api/workflows/${state.currentTally}/review-checklist`, {method: 'PATCH', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)});
    toast('Đã lưu checklist Review');
    await loadWorkflow(4);
  } catch (error) { toast(error.message); }
}

async function renderReviewPanel() {
  const host = $('#reviewPanel');
  const evaluationId = state.workflow.evaluation.id;
  if (state.reviewTab === 'detail') {
    const detail = await ensureDetail();
    host.innerHTML = `<div class="toolbar"><input id="reviewSearch" placeholder="Tìm theo mã task, title, mô tả" value="${esc(state.reviewQuery)}"><select id="reviewStatus"><option value="all">Tất cả trạng thái</option><option value="matched">Đã khớp</option><option value="unmatched">Chưa khớp</option><option value="important">Important Job</option></select><span class="spacer"></span><small>${fmt(detail.filtered_total)} kết quả</small>${gridControls()}</div><div class="panel table-wrap">${taskTable(detail.items)}<div class="pagination"><button class="ghost" id="reviewPrev" ${detail.page <= 1 ? 'disabled' : ''}>Trước</button><button class="ghost" id="reviewNext" ${detail.page * detail.page_size >= detail.filtered_total ? 'disabled' : ''}>Sau</button></div></div>`;
    state.visibleItems = detail.items;
    $('#reviewStatus').value = state.reviewStatus;
    let timer;
    $('#reviewSearch').oninput = event => { clearTimeout(timer); timer = setTimeout(() => { state.reviewQuery = event.target.value; state.reviewPage = 1; renderReviewPanel(); }, 350); };
    $('#reviewStatus').onchange = event => { state.reviewStatus = event.target.value; state.reviewPage = 1; renderReviewPanel(); };
    $('#reviewPrev').onclick = () => { state.reviewPage -= 1; renderReviewPanel(); };
    $('#reviewNext').onclick = () => { state.reviewPage += 1; renderReviewPanel(); };
    bindTaskGrid();
    bindEdit();
    return;
  }
  if (['important', 'database', 'scope'].includes(state.reviewTab)) {
    const result = await api(`/api/evaluations/${evaluationId}/report/${state.reviewTab}`);
    state.visibleItems = result.items || [];
    host.innerHTML = result.available ? `<div class="toolbar"><b>${reportTitle(state.reviewTab)}</b><span class="spacer"></span><small>${fmt(state.visibleItems.length)} kết quả</small>${gridControls()}</div><div class="panel table-wrap">${taskTable(state.visibleItems)}</div>` : `<div class="notice">${esc(result.message)}</div>`;
    bindTaskGrid();
    bindEdit();
    return;
  }
  const history = await api(`/api/evaluations/${evaluationId}/history`);
  host.innerHTML = `<div class="panel table-wrap"><table><thead><tr><th>Thời gian</th><th>Task</th><th>Trường</th><th>Thay đổi</th><th>Lý do</th><th>Người sửa</th></tr></thead><tbody>${history.items.map(item => `<tr><td>${esc(item.changed_at)}</td><td>#${item.item_id}</td><td>${esc(item.field_name)}</td><td>${esc(item.old_value || '—')} → ${esc(item.new_value || '—')}</td><td>${esc(item.reason)}</td><td>${esc(item.changed_by)}</td></tr>`).join('') || '<tr><td colspan="6" class="empty">Chưa có thay đổi thủ công</td></tr>'}</tbody></table></div>`;
}

async function renderFinalizeStep(host) {
  const evaluation = state.workflow.evaluation;
  if (!evaluation) {
    host.innerHTML = `${stepHeader(5, 'Hoàn thiện và xuất báo cáo', 'Lưu Final Evaluation và xuất Excel')}<div class="notice">Chưa có kết quả đánh giá. Hãy hoàn thành bước 3 trước.</div>`;
    return;
  }
  const detail = await ensureDetail();
  const header = detail.header;
  const summary = detail.summary;
  const reviewComplete = workflowStep('review').status === 'completed';
  const isDraft = !reviewComplete || !['Chờ phê duyệt', 'Hoàn tất'].includes(header.status);
  host.innerHTML = `${stepHeader(5, 'Hoàn thiện và xuất báo cáo', 'Hoàn chỉnh kết luận, trạng thái và thông tin phê duyệt')}
    ${reviewComplete ? '' : '<div class="notice">Checklist Review chưa hoàn thành. Bạn vẫn có thể lưu và xuất, nhưng báo cáo sẽ là bản nháp cho đến khi hoàn thành Review và chuyển trạng thái.</div>'}
    <div class="export-bar"><div><b>${isDraft ? 'BẢN NHÁP' : esc(header.status)}</b><span>${isDraft ? 'File xuất sẽ có tiền tố DRAFT và nhãn BẢN NHÁP.' : 'Hồ sơ đủ điều kiện xuất báo cáo chính thức.'}</span></div><a class="${isDraft ? 'ghost' : 'primary'}" href="/api/evaluations/${evaluation.id}/export">${isDraft ? 'Xuất Excel bản nháp' : 'Xuất Excel chính thức'}</a></div>
    <form class="final-sheet" id="finalForm"><section><h3>I. THÔNG TIN CHUNG</h3><div class="final-info"><label>Khách hàng<b>${esc(header.customer || '—')}</b></label><label>A/C<b>${esc(header.aircraft_reg || '—')}</b></label><label>Loại tàu bay<b>${esc(header.aircraft_type || '—')}</b></label><label>CHECK<b>${esc(header.check_type || '—')}</b></label><label>TAT (DAY)<input name="tat_review" value="${esc(header.tat_review || '')}" placeholder="Nhập TAT"></label><label>Revision<b>${esc(header.revision || '—')}</b></label><label>Ngày đánh giá<b>${new Date(header.created_at).toLocaleDateString('vi-VN')}</b></label><label>Trạng thái<select name="status"><option>Đang review</option><option>Chờ phê duyệt</option><option>Hoàn tất</option></select></label></div></section>
    <section><h3>II. KẾT QUẢ HIỆN CÓ</h3><div class="cards"><div class="card metric"><span>Tổng task</span><strong>${fmt(summary.total)}</strong></div><div class="card metric"><span>Khớp AMOS</span><strong>${fmt(summary.matched)}</strong></div><div class="card metric"><span>Important Job</span><strong>${fmt(summary.important)}</strong></div><div class="card metric"><span>Tổng MHR</span><strong>${fmt(summary.total_mhr)}</strong></div></div></section>
    <section><h3>III. GIẢ ĐỊNH & GHI CHÚ</h3><label>Giả định<textarea name="assumptions" rows="3">${esc(header.assumptions || '')}</textarea></label><label>Ghi chú<textarea name="notes" rows="3">${esc(header.notes || '')}</textarea></label></section>
    <div class="final-sign"><label>NGƯỜI ĐÁNH GIÁ<input name="prepared_by" value="${esc(header.prepared_by || '')}"></label><label>NGƯỜI PHÊ DUYỆT<input name="approved_by" value="${esc(header.approved_by || '')}"></label></div><div class="final-actions"><button class="primary">Lưu Final Evaluation</button></div></form>`;
  $('#finalForm [name=status]').value = header.status;
  $('#finalForm').onsubmit = async event => {
    event.preventDefault();
    const button = event.submitter;
    const restore = setBusy(button, 'Đang lưu…');
    try {
      const body = Object.fromEntries(new FormData(event.target));
      await api(`/api/evaluations/${evaluation.id}`, {method: 'PATCH', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)});
      toast('Đã lưu Final Evaluation');
      state.detail = null;
      await loadWorkflow(5);
      await loadDashboard(false);
    } catch (error) { toast(error.message); restore(); }
  };
}

const taskColumns = [
  ['task_no', 'Task No.', 145], ['title', 'Taskcard Title', 220], ['description', 'Description', 260],
  ['phase', 'Phase', 110], ['zone', 'Zone', 90], ['area', 'Area', 110], ['panel', 'Panel', 100],
  ['special_code', 'Special Code', 115], ['resource_type', 'Resource Type', 120],
  ['classification', 'Classification', 130], ['type_code', 'Type Code', 105],
  ['qualification', 'Qualification', 125], ['planning_mhr', 'Planning MHR', 110],
  ['information_skill', 'Information Skill', 130], ['requirement_link', 'Requirement Link', 190],
  ['linked_jobcards', 'Linked Jobcards', 150], ['jobcards_title', 'Jobcards Title', 190],
  ['important_job', 'Important Job', 105], ['not_in_database', 'Not included in Database', 145],
];

const gridPrefs = () => JSON.parse(localStorage.getItem('vae-task-grid-v3') || '{}');
const saveGridPrefs = preferences => localStorage.setItem('vae-task-grid-v3', JSON.stringify(preferences));

function gridControls() {
  const preferences = gridPrefs();
  const hidden = new Set(preferences.hidden || []);
  const pinned = new Set(preferences.pinned || ['task_no']);
  return `<details class="grid-menu"><summary>Cột hiển thị</summary><div>${taskColumns.map(([key, label]) => `<label><input type="checkbox" class="column-visible" data-col="${key}" ${hidden.has(key) ? '' : 'checked'}>${label}</label>`).join('')}<hr>${taskColumns.map(([key, label]) => `<label><input type="checkbox" class="column-pin" data-col="${key}" ${pinned.has(key) ? 'checked' : ''}>Ghim ${label}</label>`).join('')}<button class="ghost reset-columns" type="button">Mặc định</button></div></details>`;
}

function displayValue(item, key) {
  if (key === 'important_job') return item[key] ? '<span class="flag yes">X</span>' : '—';
  if (key === 'not_in_database') return item[key] ? '<span class="flag alert">X</span>' : '—';
  if (key === 'planning_mhr') {
    if (!item.matched && item.reviewed_mhr == null) return '—';
    const value = item.reviewed_mhr ?? item.planning_mhr;
    return `${esc(fmt(value))}${item.reviewed_mhr != null ? '<small>Review</small>' : ''}`;
  }
  const value = key === 'title' ? (item.title || item.source_title) : item[key];
  return value == null || value === '' ? '—' : esc(value);
}

function taskTable(items) {
  const preferences = gridPrefs();
  const widths = preferences.widths || {};
  return `<div class="excel-grid" id="taskGrid"><table><colgroup>${taskColumns.map(([key,, width]) => `<col data-col="${key}" style="width:${widths[key] || width}px">`).join('')}<col data-col="actions" style="width:76px"></colgroup><thead><tr>${taskColumns.map(([key, label]) => `<th class="col-${key}" data-key="${key}"><button class="sort-head" data-sort="${key}">${label}<span>${state.sortBy === key ? (state.sortDir === 'asc' ? '▲' : '▼') : ''}</span></button><i class="col-resizer" data-col="${key}"></i></th>`).join('')}<th class="action-col">Thao tác</th></tr></thead><tbody>${items.map(item => `<tr>${taskColumns.map(([key]) => `<td class="col-${key}" title="${esc((key === 'title' ? (item.title || item.source_title) : item[key]) ?? '')}"><div class="cell-value">${displayValue(item, key)}</div></td>`).join('')}<td class="action-col"><button class="link edit-item" data-id="${item.id}">Review</button></td></tr>`).join('') || `<tr><td colspan="${taskColumns.length + 1}" class="empty">Không có dữ liệu</td></tr>`}</tbody></table></div>`;
}

function bindTaskGrid() {
  const grid = $('#taskGrid');
  if (!grid) return;
  const apply = () => {
    const preferences = gridPrefs();
    const hidden = new Set(preferences.hidden || []);
    const pinned = new Set(preferences.pinned || ['task_no']);
    let left = 0, total = 76;
    taskColumns.forEach(([key,, fallback]) => {
      const col = grid.querySelector(`col[data-col="${key}"]`);
      const width = parseFloat(col?.style.width) || fallback;
      grid.querySelectorAll(`.col-${key},col[data-col="${key}"]`).forEach(element => element.classList.toggle('col-hidden', hidden.has(key)));
      grid.querySelectorAll(`.col-${key}`).forEach(element => { element.classList.toggle('pinned-col', pinned.has(key)); element.style.left = pinned.has(key) ? `${left}px` : ''; });
      if (!hidden.has(key)) total += width;
      if (pinned.has(key) && !hidden.has(key)) left += width;
    });
    grid.querySelector('table').style.width = `${Math.max(grid.clientWidth, total)}px`;
  };
  apply();
  $$('.column-visible').forEach(input => input.onchange = () => { const preferences = gridPrefs(), values = new Set(preferences.hidden || []); input.checked ? values.delete(input.dataset.col) : values.add(input.dataset.col); preferences.hidden = [...values]; saveGridPrefs(preferences); apply(); });
  $$('.column-pin').forEach(input => input.onchange = () => { const preferences = gridPrefs(), values = new Set(preferences.pinned || ['task_no']); input.checked ? values.add(input.dataset.col) : values.delete(input.dataset.col); preferences.pinned = [...values]; saveGridPrefs(preferences); apply(); });
  const reset = $('.reset-columns');
  if (reset) reset.onclick = () => { localStorage.removeItem('vae-task-grid-v3'); renderReviewPanel(); };
  $$('.sort-head').forEach(button => button.onclick = () => { const key = button.dataset.sort; if (state.sortBy === key) state.sortDir = state.sortDir === 'asc' ? 'desc' : 'asc'; else { state.sortBy = key; state.sortDir = 'asc'; } state.reviewPage = 1; renderReviewPanel(); });
  $$('.col-resizer').forEach(handle => handle.onpointerdown = event => {
    event.preventDefault(); event.stopPropagation();
    const key = handle.dataset.col, col = grid.querySelector(`col[data-col="${key}"]`), start = event.clientX, startWidth = parseFloat(col.style.width) || 120;
    const move = pointer => { col.style.width = `${Math.max(70, startWidth + pointer.clientX - start)}px`; apply(); };
    const up = () => { document.removeEventListener('pointermove', move); document.removeEventListener('pointerup', up); const preferences = gridPrefs(); preferences.widths = preferences.widths || {}; preferences.widths[key] = parseFloat(col.style.width); saveGridPrefs(preferences); apply(); };
    document.addEventListener('pointermove', move); document.addEventListener('pointerup', up);
  });
}

function bindEdit() {
  $$('.edit-item').forEach(button => button.onclick = () => {
    const item = state.visibleItems.find(row => row.id == button.dataset.id) || {id: button.dataset.id, task_no: 'Task'};
    state.editItem = item;
    $('#editTask').textContent = item.task_no || 'Task';
    const form = $('#editForm');
    form.reviewed_mhr.value = item.reviewed_mhr ?? item.planning_mhr ?? '';
    form.important_job.checked = Boolean(item.important_job);
    form.review_note.value = item.review_note || '';
    form.reason.value = '';
    $('#editDialog').showModal();
  });
}

function reportTitle(kind) {
  return ({important: 'Important Jobs', database: 'Database to be Updated', scope: 'Task out of Check Type Scope'})[kind];
}

async function renderDatabase() {
  $('#dashboardView').innerHTML = '<div class="panel empty">Đang tải dữ liệu…</div>';
  await loadDataBrowser();
}

async function loadDataBrowser() {
  const filters = state.dataFilters;
  let url;
  if (state.dataTab === 'amos_vna' || state.dataTab === 'amos_customer') {
    const source = state.dataTab === 'amos_vna' ? 'VNA' : 'CUSTOMER';
    url = `/api/data/amos?q=${encodeURIComponent(state.dataQuery)}&source=${source}&aircraft_type=${encodeURIComponent(filters.aircraft_type)}&customer=${encodeURIComponent(filters.customer)}&classification=${encodeURIComponent(filters.classification)}&page=${state.dataPage}`;
  } else if (state.dataTab === 'jobcards') {
    url = `/api/data/jobcards?q=${encodeURIComponent(state.dataQuery)}&aircraft_type=${encodeURIComponent(filters.aircraft_type)}&classification=${encodeURIComponent(filters.classification)}&page=${state.dataPage}`;
  } else {
    const category = state.dataTab === 'important_external' ? 'Công việc lưu ý' : filters.category;
    url = `/api/data/external?q=${encodeURIComponent(state.dataQuery)}&category=${encodeURIComponent(category)}&status=${encodeURIComponent(filters.external_status)}&page=${state.dataPage}`;
  }
  state.dataResult = await api(url);
  renderDataBrowser();
}

function options(values, current, label = 'Tất cả') {
  return `<option value="all">${label}</option>${values.map(value => `<option value="${esc(value)}" ${value === current ? 'selected' : ''}>${esc(value)}</option>`).join('')}`;
}

function renderDataBrowser() {
  const result = state.dataResult, tab = state.dataTab;
  const isAmp = tab === 'amos_vna' || tab === 'amos_customer', isJobcard = tab === 'jobcards', isImportant = tab === 'important_external';
  const catalog = `<div class="data-source-tabs"><b style="min-width:150px;padding:8px 0;color:var(--navy)">Dữ liệu AMOS</b><button class="ghost ${tab === 'amos_vna' ? 'active' : ''}" data-data-tab="amos_vna">AMP VNA</button><button class="ghost ${tab === 'amos_customer' ? 'active' : ''}" data-data-tab="amos_customer">AMP khách hàng</button><button class="ghost ${isJobcard ? 'active' : ''}" data-data-tab="jobcards">Jobcard master</button></div><div class="data-source-tabs"><b style="min-width:150px;padding:8px 0;color:var(--navy)">Dữ liệu ngoài AMOS</b><button class="ghost ${isImportant ? 'active' : ''}" data-data-tab="important_external">Công việc lưu ý</button><button class="ghost ${tab === 'external_all' ? 'active' : ''}" data-data-tab="external_all">Danh mục / quy tắc</button></div>`;
  let summary, title, subtitle, filters, table;
  if (isAmp) {
    summary = `<div class="data-summary"><div class="card metric"><span>AMP VNA</span><strong>${fmt(result.stats.vna)}</strong></div><div class="card metric"><span>AMP khách hàng</span><strong>${fmt(result.stats.customer)}</strong></div><div class="card metric"><span>Tổng AMP Task</span><strong>${fmt(result.stats.total)}</strong></div><div class="card metric"><span>AMOS Watch Item</span><strong>${fmt(result.stats.watch_items)}</strong></div></div>`;
    title = tab === 'amos_vna' ? 'Bảng AMP VNA' : 'Bảng AMP khách hàng'; subtitle = 'Dữ liệu chỉ đọc được nhập từ AMOS vào MiniDB';
    filters = `<select id="aircraftFilter">${options(result.filters.aircraft_types, state.dataFilters.aircraft_type, 'Tất cả loại tàu bay')}</select><select id="customerFilter">${options(result.filters.customers, state.dataFilters.customer, 'Tất cả khách hàng')}</select><select id="classFilter">${options(result.filters.classifications, state.dataFilters.classification, 'Tất cả phân loại')}</select>`;
    table = amosDataTable(result.items);
  } else if (isJobcard) {
    summary = `<div class="data-summary"><div class="card metric"><span>Jobcard master</span><strong>${fmt(result.stats.total)}</strong></div><div class="card metric"><span>Watch Item</span><strong>${fmt(result.stats.watch_items)}</strong></div></div>`;
    title = 'Bảng Jobcard master'; subtitle = 'Dữ liệu Jobcard chỉ đọc từ AMOS';
    filters = `<select id="aircraftFilter">${options(result.filters.aircraft_types, state.dataFilters.aircraft_type, 'Tất cả loại tàu bay')}</select><select id="classFilter">${options(result.filters.classifications, state.dataFilters.classification, 'Tất cả phân loại')}</select>`;
    table = jobcardDataTable(result.items);
  } else {
    summary = isImportant ? `<div class="data-summary"><div class="card metric"><span>Công việc lưu ý</span><strong>${fmt(result.total)}</strong></div></div>` : `<div class="data-summary">${result.category_counts.map(item => `<div class="card metric"><span>${esc(item.category)}</span><strong>${fmt(item.record_count)}</strong></div>`).join('')}</div>`;
    title = isImportant ? 'Các công việc lưu ý' : 'Danh mục và quy tắc ngoài AMOS'; subtitle = isImportant ? 'Dữ liệu VAECO xây dựng ngoài AMOS' : 'Mapping và quy tắc do VAECO quản lý';
    filters = `${isImportant ? '' : `<select id="categoryFilter">${options(result.filters.categories, state.dataFilters.category, 'Tất cả danh mục')}</select>`}<select id="externalStatusFilter">${options(result.filters.statuses, state.dataFilters.external_status, 'Tất cả trạng thái')}</select>`;
    table = externalDataTable(result.items, isImportant ? 'Chưa có công việc lưu ý được xây dựng ngoài AMOS' : 'Chưa có dữ liệu trong danh mục này');
  }
  $('#dashboardView').innerHTML = `<div class="hero-strip"><div><h2>Kho dữ liệu</h2><p>Xem các bảng dữ liệu AMOS và dữ liệu xây dựng ngoài</p></div><div class="status-chip">${fmt(result.total)} kết quả</div></div>${catalog}${summary}<div class="panel data-shell"><div class="panel-head"><div><h2>${title}</h2><p>${subtitle}</p></div><b>${fmt(result.total)} kết quả</b></div><div class="toolbar"><input id="dataSearch" placeholder="Tìm mã, title hoặc mô tả" value="${esc(state.dataQuery)}">${filters}<button class="ghost" id="clearDataFilters">Xóa lọc</button></div><div class="table-wrap">${table}</div><div class="pagination"><span style="margin-right:auto">Trang ${result.page} / ${Math.max(1, Math.ceil(result.total / result.page_size))}</span><button class="ghost" id="dataPrev" ${result.page <= 1 ? 'disabled' : ''}>Trước</button><button class="ghost" id="dataNext" ${result.page * result.page_size >= result.total ? 'disabled' : ''}>Sau</button></div></div>`;
  bindDataBrowser();
}

function amosDataTable(items) { return `<table><thead><tr><th>Task</th><th>Title</th><th>Nguồn</th><th>Loại tàu bay</th><th>Khách hàng</th><th>Phase / Zone</th><th>Special Code</th><th>MHR</th><th>Phân loại</th><th></th></tr></thead><tbody>${items.map(item => `<tr><td><b>${esc(item.task_no)}</b></td><td>${esc(item.title || '—')}<br><small>${esc((item.description || '').slice(0, 90))}</small></td><td>${badge(item.source, item.source === 'VNA' ? 'blue' : 'green')}</td><td>${esc(item.aircraft_type || '—')}</td><td>${esc(item.customer || '—')}</td><td>${esc(item.phase || '—')}<br><small>${esc(item.zone || '—')}</small></td><td>${esc(item.special_code || '—')}</td><td>${esc(item.planning_mhr || '—')}</td><td>${esc(item.classification || '—')}</td><td><button class="link view-data" data-id="${item.id}">Xem</button></td></tr>`).join('') || '<tr><td colspan="10" class="empty">Không tìm thấy dữ liệu phù hợp</td></tr>'}</tbody></table>`; }
function jobcardDataTable(items) { return `<table><thead><tr><th>Jobcard</th><th>Title</th><th>Loại tàu bay</th><th>Phase / Zone</th><th>Area</th><th>Special Code</th><th>MHR</th><th>Phân loại</th><th></th></tr></thead><tbody>${items.map(item => `<tr><td><b>${esc(item.task_no)}</b></td><td>${esc(item.title || '—')}<br><small>${esc((item.description || '').slice(0, 90))}</small></td><td>${esc(item.aircraft_type || '—')}</td><td>${esc(item.phase || '—')}<br><small>${esc(item.zone || '—')}</small></td><td>${esc(item.area || '—')}</td><td>${esc(item.special_code || '—')}</td><td>${esc(item.planning_mhr || '—')}</td><td>${esc(item.classification || '—')}</td><td><button class="link view-data" data-id="${item.id}">Xem</button></td></tr>`).join('') || '<tr><td colspan="9" class="empty">Không tìm thấy Jobcard phù hợp</td></tr>'}</tbody></table>`; }
function externalDataTable(items, message) { return `<table><thead><tr><th>Danh mục</th><th>Mã nguồn</th><th>Giá trị chuẩn</th><th>Loại tàu bay</th><th>Khách hàng</th><th>Mô tả</th><th>Trạng thái</th><th></th></tr></thead><tbody>${items.map(item => `<tr><td>${badge(item.category)}</td><td><b>${esc(item.code)}</b></td><td>${esc(item.canonical_value || '—')}</td><td>${esc(item.aircraft_type || '—')}</td><td>${esc(item.customer || '—')}</td><td>${esc(item.description || '—')}</td><td>${badge(item.status, item.status === 'Có hiệu lực' ? 'green' : 'amber')}</td><td><button class="link view-data" data-id="${item.id}">Xem</button></td></tr>`).join('') || `<tr><td colspan="8" class="empty">${esc(message)}</td></tr>`}</tbody></table>`; }

function bindDataBrowser() {
  $$('[data-data-tab]').forEach(button => button.onclick = () => { state.dataTab = button.dataset.dataTab; state.dataPage = 1; state.dataQuery = ''; loadDataBrowser(); });
  let timer;
  $('#dataSearch').oninput = event => { clearTimeout(timer); timer = setTimeout(() => { state.dataQuery = event.target.value; state.dataPage = 1; loadDataBrowser(); }, 350); };
  let bindings = [];
  if (state.dataTab === 'amos_vna' || state.dataTab === 'amos_customer') bindings = [['aircraftFilter', 'aircraft_type'], ['customerFilter', 'customer'], ['classFilter', 'classification']];
  else if (state.dataTab === 'jobcards') bindings = [['aircraftFilter', 'aircraft_type'], ['classFilter', 'classification']];
  else bindings = [['categoryFilter', 'category'], ['externalStatusFilter', 'external_status']];
  bindings.forEach(([id, key]) => { const element = $('#' + id); if (element) element.onchange = event => { state.dataFilters[key] = event.target.value; state.dataPage = 1; loadDataBrowser(); }; });
  $('#clearDataFilters').onclick = () => { state.dataQuery = ''; Object.keys(state.dataFilters).forEach(key => state.dataFilters[key] = 'all'); state.dataPage = 1; loadDataBrowser(); };
  $('#dataPrev').onclick = () => { state.dataPage -= 1; loadDataBrowser(); };
  $('#dataNext').onclick = () => { state.dataPage += 1; loadDataBrowser(); };
  $$('.view-data').forEach(button => button.onclick = () => showDataDetail(Number(button.dataset.id)));
}

function showDataDetail(id) {
  const item = state.dataResult.items.find(row => row.id === id); if (!item) return;
  const isAmos = ['amos_vna', 'amos_customer', 'jobcards'].includes(state.dataTab);
  const labels = isAmos ? {task_no: 'Mã task/Jobcard', title: 'Title', description: 'Description', source: 'Nguồn', aircraft_type: 'Loại tàu bay', customer: 'Khách hàng', phase: 'Phase', zone: 'Zone', area: 'Area', panel: 'Panel', special_code: 'Special Code', resource_type: 'Resource Type', classification: 'Classification', qualification: 'Qualification', planning_mhr: 'Planning MHR', information_skill: 'Information Skill', requirement_link: 'Requirement Link', linked_jobcards: 'Linked Jobcards'} : {category: 'Danh mục', code: 'Mã nguồn', canonical_value: 'Giá trị chuẩn', aircraft_type: 'Loại tàu bay', customer: 'Khách hàng', description: 'Mô tả', reason: 'Lý do', status: 'Trạng thái', updated_by: 'Người cập nhật', updated_at: 'Cập nhật lúc'};
  $('#dataDetailTitle').textContent = isAmos ? (item.task_no || 'Chi tiết dữ liệu AMOS') : (item.code || 'Chi tiết dữ liệu ngoài');
  $('#dataDetailSub').textContent = isAmos ? 'Bản ghi chỉ đọc từ MiniDB AMOS' : 'Bản ghi do VAECO quản lý ngoài AMOS';
  $('#dataDetailBody').innerHTML = `<div class="detail-grid">${Object.entries(labels).map(([key, label]) => `<div class="detail-field ${['description', 'linked_jobcards'].includes(key) ? 'wide' : ''}"><span>${label}</span><b>${esc(item[key] ?? '—')}</b></div>`).join('')}</div>`;
  $('#dataDialog').showModal();
}

function showView(name, render = true) {
  state.view = name;
  $$('.view').forEach(view => view.classList.add('hidden'));
  $$('nav button').forEach(button => button.classList.toggle('active', button.dataset.view === name));
  if (name === 'workflow') {
    $('#workflowView').classList.remove('hidden');
    $('#pageTitle').textContent = 'Quy trình đánh giá';
    if (render) state.currentTally && state.workflow ? renderWorkflow() : renderWorkflowHub();
  } else {
    $('#dashboardView').classList.remove('hidden');
    if (name === 'database') { $('#pageTitle').textContent = 'Kho dữ liệu'; if (render) renderDatabase(); }
    else { $('#pageTitle').textContent = 'Danh sách chào thầu'; if (render) renderDashboard(); }
  }
}

async function refreshCurrent() {
  if (state.view === 'workflow' && state.currentTally) return loadWorkflow(state.workflowStep);
  if (state.view === 'database') return loadDataBrowser();
  return loadDashboard();
}

$$('nav button').forEach(button => button.onclick = () => showView(button.dataset.view));
$('#openUpload').onclick = () => $('#uploadDialog').showModal();
$('#refreshBtn').onclick = () => refreshCurrent();
$$('[data-close]').forEach(button => button.onclick = () => button.closest('dialog').close());

$('#uploadForm').onsubmit = async event => {
  event.preventDefault();
  const button = event.submitter;
  const restore = setBusy(button, 'Đang lưu hồ sơ…');
  try {
    const result = await api('/api/tallies', {method: 'POST', body: new FormData(event.target)});
    $('#uploadDialog').close();
    event.target.reset();
    toast('Đã tiếp nhận Tally Sheet');
    await loadDashboard(false);
    await openWorkflow(result.tally_id, 2);
  } catch (error) { toast(error.message); restore(); }
};

$('#editForm').onsubmit = async event => {
  event.preventDefault();
  const formData = new FormData(event.target);
  const body = {reviewed_mhr: formData.get('reviewed_mhr') === '' ? null : Number(formData.get('reviewed_mhr')), important_job: formData.get('important_job') === 'on', review_note: formData.get('review_note'), reason: formData.get('reason')};
  try {
    await api(`/api/items/${state.editItem.id}`, {method: 'PATCH', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)});
    $('#editDialog').close(); toast('Đã lưu thay đổi và lịch sử'); state.detail = null; await renderReviewPanel();
  } catch (error) { toast(error.message); }
};

loadDashboard().catch(error => { $('#dashboardView').innerHTML = `<div class="notice">${esc(error.message)}</div>`; });
