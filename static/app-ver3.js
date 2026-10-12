/* =========================================================================
   VAECO Workpack Review Ver3 – front-end
   -------------------------------------------------------------------------
   Fork base (5-step workflow, Lufthansa block reader, Jobcard master, draft export)
   + merged features (MPD-key matching columns, AMOS popup, wrap text,
   "Thêm vào Database" / "Sửa bản ghi", delete, origin filter, required upload form).

    1. Helpers & state
    2. Dashboard / workflow list (+ delete)
    3. Workflow steps 1–3
    4. Step 4 · Review
    5. Step 5 · Final evaluation
    6. Task grid (columns, status labels, wrap text)
    7. AMOS popup
    8. Review dialog + MiniDB actions
    9. Data store ("Kho dữ liệu")
   10. Upload (step 1 form)
   11. MiniDB records (add / edit)
   12. Navigation & start-up
   ========================================================================= */

/* =========================================================================
   1. HELPERS & STATE
   ========================================================================= */
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
  dataFilters: {aircraft_type: 'all', customer: 'all', classification: 'all', origin: 'all', category: 'all', external_status: 'all'},
  dataResult: null,
};

const fmt = value => new Intl.NumberFormat('vi-VN', {maximumFractionDigits: 2}).format(value || 0);
const esc = value => String(value ?? '').replace(/[&<>"']/g, character => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[character]));
const badge = (text, color = 'blue') => `<span class="badge ${color}">${esc(text)}</span>`;

// Status codes stored in the database -> text shown on screen
const STATUS_LABELS = {AUTO_MATCH: 'Đã khớp', REVIEW_REQUIRED: 'Cần review', NOT_FOUND: 'Chưa khớp', NOT_APPLICABLE: 'Không áp dụng'};
const STATUS_COLORS = {AUTO_MATCH: 'green', REVIEW_REQUIRED: 'amber', NOT_FOUND: 'red', NOT_APPLICABLE: 'blue'};
const statusBadge = code => STATUS_LABELS[code] ? badge(STATUS_LABELS[code], STATUS_COLORS[code]) : '—';

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

function setBusy(button, busyText) {
  const original = button.textContent;
  button.disabled = true;
  button.textContent = busyText;
  return () => { button.disabled = false; button.textContent = original; };
}

/* =========================================================================
   2. DASHBOARD / WORKFLOW LIST
   ========================================================================= */
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
  return `<table class="workflow-list"><thead><tr><th>Khách hàng</th><th>Ngày bắt đầu</th><th>Mô tả</th><th>Check</th><th>Khớp AMOS</th><th>Tiến độ</th><th>Trạng thái</th><th></th></tr></thead><tbody>${rows.map(item => `
    <tr>
      <td><b>${esc(item.customer || '—')}</b><br><small>${esc(item.aircraft_reg || '—')} · ${esc(item.aircraft_type || '—')}</small></td>
      <td>${new Date(item.uploaded_at).toLocaleDateString('vi-VN')}</td>
      <td><b>${esc(item.description || item.file_name)}</b><br><small>${esc(item.file_name)} · ${esc(item.adapter || '')}</small></td>
      <td>${esc(item.check_type || '—')}</td>
      <td>${item.evaluation_id ? `${fmt(item.matched_count)}/${fmt(item.row_count)}` : '—'}</td>
      <td><b>${item.progress}%</b><small>${esc(progressLabel(item))}</small><div class="progress"><i style="width:${item.progress}%"></i></div></td>
      <td>${badge(item.status, item.status === 'Hoàn tất' ? 'green' : 'amber')}</td>
      <td style="white-space:nowrap"><button class="link open-workflow" data-tally="${item.tally_id}">Tiếp tục</button> · <button class="link danger delete-tally" data-tally="${item.tally_id}" data-name="${esc(item.description || item.file_name)}">Xóa</button></td>
    </tr>`).join('') || '<tr><td colspan="8" class="empty">Chưa có hồ sơ chào thầu</td></tr>'}</tbody></table>`;
}

function renderDashboard() {
  const data = state.dashboard;
  const rows = data.workflows || [];
  const totals = data.totals;
  const rate = totals.item_count ? Math.round(100 * totals.matched_count / totals.item_count) : 0;
  $('#dashboardView').innerHTML = `
    <div class="workbar"><h2>Danh sách chào thầu</h2><span class="badge blue">${rows.length} bộ hồ sơ</span><span class="spacer"></span><span>MiniDB: <b>${fmt(data.amp_count)}</b> task</span></div>
    <div class="cards"><div class="card metric"><span>Số bộ hồ sơ chào thầu đã tiếp nhận</span><strong>${fmt(totals.tally_count)}</strong><small>Tiến độ tính theo quy trình 5 bước</small></div><div class="card metric"><span>Task đã đọc</span><strong>${fmt(totals.item_count)}</strong></div><div class="card metric"><span>Đã khớp AMOS</span><strong>${fmt(totals.matched_count)}</strong><small>${rate}% tổng số task</small></div><div class="card metric"><span>Chờ bổ sung / review</span><strong>${fmt(totals.item_count - totals.matched_count)}</strong></div></div>
    <div class="panel"><div class="toolbar"><input id="workflowSearch" placeholder="Tìm khách hàng, mô tả, số đăng ký, Check hoặc trạng thái"><select id="workflowStatus"><option value="all">Tất cả trạng thái</option>${[...new Set(rows.map(item => item.status))].map(status => `<option>${esc(status)}</option>`).join('')}</select><span class="spacer"></span><button class="ghost" id="dashboardRefresh">↻ Làm mới</button><button class="primary create-tally">＋ Tạo hồ sơ</button></div><div class="table-wrap">${workflowTable(rows)}</div></div>`;
  const applyFilters = () => {
    const query = $('#workflowSearch').value.trim().toLowerCase();
    const status = $('#workflowStatus').value;
    const filtered = rows.filter(item => (status === 'all' || item.status === status) && (!query || [item.customer, item.description, item.file_name, item.aircraft_reg, item.aircraft_type, item.check_type, item.status, item.tally_id].some(value => String(value || '').toLowerCase().includes(query))));
    $('#dashboardView .table-wrap').innerHTML = workflowTable(filtered);
    bindWorkflowOpen();
  };
  $('#workflowSearch').oninput = applyFilters;
  $('#workflowStatus').onchange = applyFilters;
  $('#dashboardRefresh').onclick = () => loadDashboard();
  $$('.create-tally').forEach(button => button.onclick = () => openUploadDialog());
  bindWorkflowOpen();
}

function renderWorkflowHub() {
  const rows = state.dashboard?.workflows || [];
  $('#workflowView').innerHTML = `
    <div class="hero-strip"><div><h2>Quy trình đánh giá Workpack</h2><p>Thực hiện lần lượt từ tiếp nhận Tally Sheet đến review và xuất báo cáo</p></div><button class="primary create-tally">＋ Bắt đầu hồ sơ mới</button></div>
    <div class="workflow-guide"><div><b>1</b><span>Tiếp nhận</span></div><i></i><div><b>2</b><span>Đọc sơ bộ</span></div><i></i><div><b>3</b><span>Đánh giá</span></div><i></i><div><b>4</b><span>Review</span></div><i></i><div><b>5</b><span>Hoàn thiện</span></div></div>
    <div class="panel"><div class="panel-head"><div><h2>Hồ sơ đang xử lý</h2><p>Chọn một hồ sơ để tiếp tục từ bước gần nhất</p></div><b>${rows.length} hồ sơ</b></div><div class="table-wrap">${workflowTable(rows)}</div></div>`;
  $$('.create-tally').forEach(button => button.onclick = () => openUploadDialog());
  bindWorkflowOpen();
}

function bindWorkflowOpen() {
  $$('.open-workflow').forEach(button => button.onclick = () => openWorkflow(button.dataset.tally));
  $$('.delete-tally').forEach(button => button.onclick = () => deleteTally(button.dataset.tally, button.dataset.name));
}

// Delete a Tally Sheet (evaluation, review history, workflow, uploaded file). MiniDB changes are kept.
async function deleteTally(tallyId, name) {
  const ok = window.confirm(`Xóa hồ sơ ${name || tallyId}?\n\nSẽ xóa Tally Sheet, kết quả đánh giá, lịch sử review, tiến độ quy trình và file đã nạp.` +
    `\nCác thay đổi đã ghi vào MiniDB (Thêm vào Database / Sửa bản ghi) vẫn được giữ.\n\nKhông thể hoàn tác.`);
  if (!ok) return;
  try {
    await api(`/api/tallies/${tallyId}`, {method: 'DELETE'});
    if (state.currentTally === tallyId) { state.currentTally = null; state.workflow = null; state.detail = null; }
    toast('Đã xóa hồ sơ');
    await loadDashboard();
  } catch (error) { toast(error.message); }
}

/* =========================================================================
   3. WORKFLOW STEPS 1–3
   ========================================================================= */
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
    <div class="eval-head workflow-head"><div><button class="link" id="backWorkflow">‹ Danh sách quy trình</button><h2>${esc(tally.description || tally.file_name)}</h2><p>${esc(tally.customer)} · ${esc(tally.aircraft_reg || '—')} · ${esc(tally.aircraft_type || '—')} · ${esc(tally.check_type || '—')}</p></div><div class="workflow-score"><strong>${workflow.progress}%</strong><span>${workflow.completed_steps}/5 bước hoàn thành</span></div></div>
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
      <div class="detail-grid intake-summary">${[['Khách hàng', tally.customer], ['Mô tả', tally.description || tally.file_name], ['Số đăng ký', tally.aircraft_reg], ['Loại tàu bay', tally.aircraft_type], ['Check Type', tally.check_type], ['Mẫu Tally Sheet', tally.adapter], ['Người nạp', tally.uploader], ['Thời điểm', new Date(tally.uploaded_at).toLocaleString('vi-VN')]].map(([label, value]) => `<div class="detail-field"><span>${label}</span><b>${esc(value || '—')}</b></div>`).join('')}<div class="detail-field wide"><span>File Tally Sheet</span><b>${esc(tally.file_name)}</b><a class="link" href="/api/tally/${tally.id}/download">Tải file gốc</a></div></div>
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

function isLufthansaWorkflow() {
  const tally = state.workflow?.tally || {};
  return tally.adapter === 'Lufthansa';
}

function lufthansaStructure() {
  return workflowStep('inspect')?.details?.structure || state.workflow?.lufthansa_structure || null;
}

function structureTable(structure) {
  const blocks = structure?.blocks || [];
  return `<div class="panel structure-panel"><div class="panel-head"><div><h3>1. Cấu trúc Tally Sheet</h3><p>${esc(structure.form_type || 'Báo cáo nhiều khối')} · ${esc(structure.active_sheet || '—')} · ${esc(structure.dimension || '—')}</p></div><b>${fmt(structure.block_count)} khối</b></div>
    <div class="table-wrap"><table class="structure-table"><thead><tr><th>STT</th><th>Khối dữ liệu</th><th>Vị trí</th><th>Số bản ghi</th><th>Các trường</th><th>Phạm vi hiện tại</th></tr></thead><tbody>${blocks.map(block => `<tr><td>${block.order}</td><td><b>${esc(block.title)}</b><br><small>${esc(block.category)}</small></td><td>${esc(block.row_span || '—')}<br><small>${esc(block.data_range || '—')}</small></td><td><b>${fmt(block.record_count)}</b></td><td><div class="field-list">${(block.fields || []).map(field => `<span>${esc(field)}</span>`).join('') || '—'}</div></td><td>${block.is_taskcard_scope ? badge('So Taskcard', 'green') : (block.fields || []).includes('CRI') ? badge('So theo CRI', 'green') : badge('Đọc & lưu', 'blue')}</td></tr>`).join('')}</tbody></table></div>
    <div class="structure-note">${esc(structure.metadata_note || '')}</div></div>`;
}

function blockEvaluationTable(blocks) {
  const color = status => status === 'Hoàn thành' ? 'green' : status === 'Cần review' ? 'amber' : 'blue';
  return `<div class="panel block-result-panel"><div class="panel-head"><div><h3>Các khối công việc lớn</h3><p>Mọi dòng có CRI được đối chiếu theo MPD key; khối không có CRI được thống kê và chờ quy tắc riêng</p></div><b>${fmt(blocks.length)} khối</b></div><div class="table-wrap"><table><thead><tr><th>STT</th><th>Khối công việc</th><th>Nhóm</th><th>Số bản ghi</th><th>Trạng thái</th><th>Kết quả sơ bộ</th></tr></thead><tbody>${blocks.map(block => `<tr class="${block.is_taskcard_scope ? 'taskcard-scope-row' : ''}"><td>${block.order}</td><td><b>${esc(block.title)}</b></td><td>${esc(block.category)}</td><td><b>${fmt(block.record_count)}</b></td><td>${badge(block.status, color(block.status))}</td><td>${esc(block.result)}</td></tr>`).join('')}</tbody></table></div></div>`;
}

function renderInspectionStep(host) {
  const step = workflowStep('inspect');
  const result = step.details || {};
  const hasResult = Boolean(result.row_count);
  const isDLH = isLufthansaWorkflow();
  const structure = lufthansaStructure();
  const overview = isDLH && structure
    ? `<div class="cards inspection-cards"><div class="card metric"><span>Mẫu nhận diện</span><strong>Lufthansa / DLH</strong></div><div class="card metric"><span>Khối dữ liệu</span><strong>${fmt(structure.block_count)}</strong></div><div class="card metric"><span>Tổng bản ghi</span><strong>${fmt(structure.total_record_count)}</strong></div><div class="card metric"><span>Dòng có CRI</span><strong>${fmt(result.row_count)}</strong><small>MS ITEMS: ${fmt(structure.ms_item_count)}</small></div></div>`
    : `<div class="cards inspection-cards"><div class="card metric"><span>Mẫu nhận diện</span><strong>${esc(result.adapter)}</strong></div><div class="card metric"><span>Dòng nghiệp vụ</span><strong>${fmt(result.row_count)}</strong></div><div class="card metric"><span>Sheet</span><strong>${esc(result.active_sheet || '—')}</strong></div><div class="card metric"><span>Mã trùng</span><strong>${fmt(result.duplicate_count)}</strong></div></div>`;
  const detail = isDLH && structure
    ? structureTable(structure)
    : `<div class="panel"><div class="panel-head"><div><h3>Dữ liệu mẫu đã đọc</h3><p>${esc((result.detected_columns || []).join(' · ') || 'Không có danh sách cột')}</p></div></div><div class="table-wrap"><table><thead><tr><th>STT</th><th>Task/CRI</th><th>Title</th><th>Section</th></tr></thead><tbody>${(result.sample_rows || []).map(row => `<tr><td>${esc(row.seq || '—')}</td><td><b>${esc(row.task_no)}</b></td><td>${esc(row.title || '—')}</td><td>${esc(row.section || '—')}</td></tr>`).join('')}</tbody></table></div></div>`;
  host.innerHTML = `${stepHeader(2, 'Đọc và kiểm tra sơ bộ', isDLH ? 'Nhận diện đầy đủ cấu trúc Workpackage Summary của Lufthansa / DLH' : 'Nhận diện cấu trúc file trước khi matching với AMOS')}
    <div class="instruction">${isDLH ? '<b>Kết quả đọc:</b> toàn bộ các khối, vị trí, số bản ghi và danh sách trường trong Tally Sheet. Bước này chưa chạy matching.' : '<b>Cần kiểm tra:</b> mẫu Tally, số dòng đọc được, các cột nhận diện và cảnh báo metadata. Bước này chưa tạo kết quả đánh giá.'}</div>
    ${hasResult ? `${overview}
      ${result.warnings?.length ? `<div class="notice"><b>Cảnh báo dữ liệu</b><ul>${result.warnings.map(item => `<li>${esc(item)}</li>`).join('')}</ul></div>` : '<div class="success-note">Không phát hiện cảnh báo dữ liệu đầu vào.</div>'}
      ${detail}` : `${result.error ? `<div class="notice">${esc(result.error)}</div>` : ''}<div class="empty-step">Chưa đọc file. Bấm “Đọc sơ bộ” để kiểm tra cấu trúc Tally Sheet.</div>`}
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

function matchingCards(summary) {
  const total = summary?.total || 0;
  return `<div class="cards evaluation-cards">
    <div class="card metric"><span>Tổng task</span><strong>${fmt(total)}</strong></div>
    <div class="card metric"><span>Lớp 1 · Khớp theo MPD key</span><strong>${fmt(summary?.matched)}</strong><small>${total ? Math.round((summary.matched || 0) * 100 / total) : 0}% tổng task · ${fmt(summary?.layer_1_review || 0)} cần review</small></div>
    <div class="card metric"><span>Lớp 2 · Tiền tố mã</span><strong>${fmt(summary?.layer_2 || 0)}</strong><small>Gợi ý, chưa tính MHR</small></div>
    <div class="card metric"><span>Lớp 3 · Nội dung Title</span><strong>${fmt(summary?.layer_3 || 0)}</strong><small>Gợi ý, chưa tính MHR</small></div>
    <div class="card metric"><span>Chưa khớp (thiếu trong DB)</span><strong>${fmt(summary?.unmatched)}</strong></div>
    <div class="card metric"><span>Không áp dụng</span><strong>${fmt(summary?.not_applicable || 0)}</strong><small>Không có mã task</small></div></div>`;
}

async function renderEvaluationStep(host) {
  const evaluation = state.workflow.evaluation;
  const summary = state.workflow.summary;
  const inspection = workflowStep('inspect');
  const isDLH = isLufthansaWorkflow();
  const blocks = state.workflow.block_summary || [];
  const tally = state.workflow.tally;
  let plan = [];
  try { plan = (await api(`/api/matching-plan?${new URLSearchParams({customer: tally.customer, aircraft_type: tally.aircraft_type || ''})}`)).steps; } catch {}
  host.innerHTML = `${stepHeader(3, 'Chạy và đánh giá sơ bộ', 'Đối chiếu task của Tally Sheet với AMOS theo MPD key')}
    <div class="instruction"><b>Lớp 1 – MPD key</b>, thứ tự nguồn: ${plan.map((step, index) => `<b>${index + 1}.</b> ${esc(step)}`).join(' ')}.
      Các dòng cùng MPD key được chia item theo LH/RH (ENG #1/#2) và thứ tự ITEM; dòng có ghi chú ghép là <b>Cần review</b>.
      <br><b>Lớp 2–3</b> (tiền tố mã ≥ 60% và ≥ 4 ký tự; Title ≥ 65%) chỉ chạy khi lớp 1 không tìm thấy, là gợi ý cần review và <b>không gán MHR</b>.</div>
    ${inspection.status !== 'completed' ? '<div class="notice">Bước đọc sơ bộ chưa được xác nhận. Bạn vẫn có thể xem bước này, nhưng cần xác nhận dữ liệu trước khi đánh giá.</div>' : ''}
    ${evaluation ? `${matchingCards(summary)}${isDLH && blocks.length ? blockEvaluationTable(blocks) : ''}<div class="result-callout"><b>Đánh giá sơ bộ đã hoàn thành</b><span>Mã đánh giá: ${esc(evaluation.id)} · Tổng MHR đã khớp: ${fmt(summary.total_mhr)}</span></div>` : `${isDLH && blocks.length ? blockEvaluationTable(blocks) : ''}<div class="empty-step">Chưa có kết quả đánh giá sơ bộ. Thao tác này sẽ tạo Detailed Task List và các danh sách ngoại lệ.</div>`}
    <div class="step-actions">${evaluation ? '<button class="primary next-step">Mở bước Review →</button>' : '<button class="primary" id="runEvaluation">Chạy đánh giá sơ bộ</button>'}</div>`;
  const run = $('#runEvaluation');
  if (run) run.onclick = async event => {
    const restore = setBusy(event.currentTarget, 'Đang đối chiếu AMOS…');
    try { const result = await api(`/api/tallies/${state.currentTally}/evaluate`, {method: 'POST'}); toast(result.reused ? 'Đã sử dụng kết quả hiện có' : 'Đã hoàn thành đánh giá sơ bộ'); state.detail = null; await loadWorkflow(3); await loadDashboard(false); }
    catch (error) { toast(error.message); restore(); }
  };
  const next = $('.next-step');
  if (next) next.onclick = () => { state.workflowStep = 4; renderWorkflow(); };
}

/* =========================================================================
   4. STEP 4 · REVIEW
   ========================================================================= */
async function ensureDetail() {
  const evaluationId = state.workflow.evaluation?.id;
  if (!evaluationId) return null;
  const params = new URLSearchParams({q: state.reviewQuery, status: state.reviewStatus, page: state.reviewPage, sort_by: state.sortBy, sort_dir: state.sortDir});
  state.detail = await api(`/api/evaluations/${evaluationId}?${params}`);
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
      ${reviewCheck('detail', 'Detailed Task List', 'Kiểm tra danh sách task, MHR, AMOS Reference và các dòng Cần review', checklist.detail)}
      ${reviewCheck('important', 'Important Jobs', 'Kiểm tra Watch Item và các đánh dấu thủ công', checklist.important)}
      ${reviewCheck('database', 'Database to be Updated', 'Kiểm tra task chưa có trong MiniDB, dùng “Thêm vào Database” nếu cần', checklist.database)}
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

const REVIEW_FILTERS = [
  ['all', 'Tất cả trạng thái'],
  ['auto_match', 'Đã khớp'],
  ['review_required', 'Cần review (tất cả)'],
  ['layer_1_review', 'Lớp 1 · Khớp nhưng cần review'],
  ['layer_2', 'Lớp 2 · Gợi ý tiền tố mã'],
  ['layer_3', 'Lớp 3 · Gợi ý Title'],
  ['not_found', 'Chưa khớp'],
  ['not_applicable', 'Không áp dụng'],
  ['important', 'Important Job'],
  ['added_to_db', 'Đã thêm vào Database'],
];

async function renderReviewPanel() {
  const host = $('#reviewPanel');
  if (!host) return;
  const evaluationId = state.workflow.evaluation.id;
  if (state.reviewTab === 'detail') {
    const detail = await ensureDetail();
    host.innerHTML = `<div class="toolbar"><input id="reviewSearch" placeholder="Tìm theo mã task, title, mô tả, AMOS Reference" value="${esc(state.reviewQuery)}"><select id="reviewStatus">${REVIEW_FILTERS.map(([value, label]) => `<option value="${value}">${label}</option>`).join('')}</select><span class="spacer"></span><small>${fmt(detail.filtered_total)} kết quả</small>${gridControls()}</div><div class="panel table-wrap">${taskTable(detail.items)}<div class="pagination"><button class="ghost" id="reviewPrev" ${detail.page <= 1 ? 'disabled' : ''}>Trước</button><button class="ghost" id="reviewNext" ${detail.page * detail.page_size >= detail.filtered_total ? 'disabled' : ''}>Sau</button></div></div>`;
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

function reportTitle(kind) {
  return ({important: 'Important Jobs', database: 'Database to be Updated', scope: 'Task out of Check Type Scope'})[kind];
}

// Reload whatever the review screen shows after a change
async function refreshReview() {
  state.detail = null;
  if (state.view === 'workflow' && state.currentTally) await loadWorkflow(state.workflowStep);
}

/* =========================================================================
   5. STEP 5 · FINAL EVALUATION
   ========================================================================= */
const tableRows = rows => rows.map(row => `<tr>${row.map(value => `<td>${value}</td>`).join('')}</tr>`).join('');

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
  const total = summary.total || 0;
  const pct = value => total ? `${(100 * value / total).toFixed(1)}%` : '—';
  const manHours = [
    ['1', 'Task + Access', fmt(summary.total_mhr), '100%', 'Detailed Task List (chỉ dòng đã khớp hoặc MHR review)'],
    ['2', 'Preparation (Pre)', '—', '—', 'Chờ dữ liệu ngoài AMOS theo Check Type'],
    ['3', 'WO (EO, AD, ETC, ...)', '—', '—', 'Chờ phân loại WO trong Detailed Task List'],
    ['4', 'ERU', '—', '—', 'Chờ dữ liệu ngoài AMOS'],
    ['5', 'TOW', '—', '—', 'Chờ dữ liệu ngoài AMOS'],
    ['6', 'NRC (tạm tính)', '—', '—', 'Chờ tỷ lệ được phê duyệt'],
  ];
  const statistics = [
    ['1', 'Tổng số STD Task', fmt(total), '100%', 'Detailed Task List'],
    ['2', 'Số task đã khớp AMOS', fmt(summary.matched), pct(summary.matched), `Trong đó cần review: ${fmt(summary.layer_1_review || 0)}`],
    ['3', 'Số task gợi ý lớp 2–3', fmt((summary.layer_2 || 0) + (summary.layer_3 || 0)), pct((summary.layer_2 || 0) + (summary.layer_3 || 0)), 'Chưa tính MHR'],
    ['4', 'Số Important Jobs', fmt(summary.important), pct(summary.important), 'Important Jobs'],
    ['5', 'Số Task chưa có trong Database', fmt(summary.unmatched), pct(summary.unmatched), 'Database to be Updated'],
    ['6', 'Số Task không áp dụng', fmt(summary.not_applicable || 0), pct(summary.not_applicable || 0), 'Không có mã task'],
    ['7', 'Số Task ngoài phạm vi Check Type', '—', '—', 'Chờ dữ liệu Task–Check/Linked Check'],
  ];
  host.innerHTML = `${stepHeader(5, 'Hoàn thiện và xuất báo cáo', 'Hoàn chỉnh kết luận, trạng thái và thông tin phê duyệt')}
    ${reviewComplete ? '' : '<div class="notice">Checklist Review chưa hoàn thành. Bạn vẫn có thể lưu và xuất, nhưng báo cáo sẽ là bản nháp cho đến khi hoàn thành Review và chuyển trạng thái.</div>'}
    <div class="export-bar"><div><b>${isDraft ? 'BẢN NHÁP' : esc(header.status)}</b><span>${isDraft ? 'File xuất sẽ có tiền tố DRAFT và nhãn BẢN NHÁP.' : 'Hồ sơ đủ điều kiện xuất báo cáo chính thức.'}</span></div><a class="${isDraft ? 'ghost' : 'primary'}" href="/api/evaluations/${evaluation.id}/export">${isDraft ? 'Xuất Excel bản nháp' : 'Xuất Excel chính thức'}</a></div>
    <form class="final-sheet" id="finalForm"><div class="final-title">${isDraft ? 'BẢN NHÁP · ' : ''}FINAL EVALUATION</div>
    <section><h3>I. THÔNG TIN CHUNG (GENERAL INFORMATION)</h3><div class="final-info"><label>Khách hàng (Customer)<b>${esc(header.customer || '—')}</b></label><label>A/C (Số đăng ký)<b>${esc(header.aircraft_reg || '—')}</b></label><label>Loại tàu bay (A/C Type)<b>${esc(header.aircraft_type || '—')}</b></label><label>CHECK (Check Type)<b>${esc(header.check_type || '—')}</b></label><label>TAT (DAY)<input name="tat_review" value="${esc(header.tat_review || '')}" placeholder="Nhập TAT"></label><label>Workpack Ref. / Revision<b>${esc(header.file_name)} / ${esc(header.revision || '—')}</b></label><label>Ngày đánh giá (Evaluation date)<b>${new Date(header.created_at).toLocaleDateString('vi-VN')}</b></label><label>Trạng thái<select name="status"><option>Đang review</option><option>Chờ phê duyệt</option><option>Hoàn tất</option></select></label></div></section>
    <section><h3>II. TỔNG HỢP GIỜ CÔNG (MAN-HOUR SUMMARY)</h3><div class="table-wrap"><table class="final-table"><thead><tr><th>No.</th><th>Hạng mục (Item)</th><th>Giờ công (MHs)</th><th>% Tổng</th><th>Ghi chú / Remarks</th></tr></thead><tbody>${tableRows(manHours)}<tr class="total-row"><td colspan="2">TOTAL (TỔNG GIỜ CÔNG HIỆN CÓ)</td><td>${fmt(summary.total_mhr)}</td><td>100%</td><td>Chưa gồm các hạng mục chưa có quy tắc</td></tr></tbody></table></div></section>
    <section><h3>III. THỐNG KÊ GÓI CÔNG VIỆC (WORKPACK STATISTICS)</h3><div class="table-wrap"><table class="final-table"><thead><tr><th>No.</th><th>Chỉ tiêu</th><th>Giá trị</th><th>%</th><th>Nguồn số liệu / Cách tính</th></tr></thead><tbody>${tableRows(statistics)}</tbody></table></div></section>
    <section><h3>IV. GIẢ ĐỊNH & GHI CHÚ CỦA NGƯỜI ĐÁNH GIÁ</h3><label>Giả định<textarea name="assumptions" rows="3">${esc(header.assumptions || '')}</textarea></label><label>Ghi chú<textarea name="notes" rows="3">${esc(header.notes || '')}</textarea></label></section>
    <div class="final-sign"><label>NGƯỜI ĐÁNH GIÁ (Prepared by)<input name="prepared_by" value="${esc(header.prepared_by || '')}"></label><label>PHÊ DUYỆT (Approved by)<input name="approved_by" value="${esc(header.approved_by || '')}"></label></div><div class="final-actions"><button class="primary">Lưu Final Evaluation</button></div></form>`;
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

/* =========================================================================
   6. TASK GRID
   ========================================================================= */
// [field, header, default width in px]
const taskColumns = [
  ['task_no', 'Event Number', 145], ['source_title', 'Tally Title', 240],
  ['match_status', 'Kết quả khớp', 125], ['amos_reference', 'AMOS Reference', 300],
  ['match_note', 'Match Note', 260],
  ['match_layer', 'Lớp khớp', 125], ['match_score', 'Tỷ lệ khớp', 105], ['match_method', 'Nguồn/luồng khớp', 160],
  ['match_candidate_count', 'Candidate', 90], ['suggested_task_no', 'Taskcard đề xuất', 165],
  ['suggested_title', 'Database Title đề xuất', 240], ['suggested_mhr', 'MHR đề xuất', 105],
  ['title', 'Taskcard Title', 220], ['description', 'Description', 260],
  ['phase', 'Phase', 110], ['zone', 'Zone', 90], ['area', 'Area', 110], ['panel', 'Panel', 100],
  ['special_code', 'Special Code', 115], ['resource_type', 'Resource Type', 120],
  ['classification', 'Classification', 130], ['type_code', 'Type Code', 105],
  ['qualification', 'Qualification', 125], ['planning_mhr', 'Planning MHR', 110],
  ['information_skill', 'Information Skill', 130], ['requirement_link', 'Requirement Link', 190],
  ['linked_jobcards', 'Linked Jobcards', 150], ['jobcards_title', 'Jobcards Title', 190],
  ['important_job', 'Important Job', 105], ['not_in_database', 'Not included in Database', 165],
];
const ACTION_COL_WIDTH = 76;
const GRID_PREFS_KEY = 'vae-task-grid-v3';

const METHOD_LABELS = {
  MPD_CUSTOMER_FIRST: 'MPD key · Customer AMP (ưu tiên)', MPD_VNA: 'MPD key · ALL AMP Task',
  CR_SAME_CUSTOMER: 'Customer AMP cùng khách hàng', CR_OTHER_CUSTOMER: 'Customer AMP khách hàng khác',
  VNA_TASKCARD: 'AMP VNA', CR_FALLBACK: 'CR fallback', CR_DLH_A350: 'CR DLH A350',
  PREFIX_VNA: 'Tiền tố AMP VNA', PREFIX_CR: 'Tiền tố CR', PREFIX_CR_DLH_A350: 'Tiền tố CR DLH A350',
  TITLE_VNA: 'Title AMP VNA', TITLE_CR: 'Title CR', TITLE_CR_DLH_A350: 'Title CR DLH A350',
  EVENT_TYPE_FILTER: 'Không có mã task', NO_CANDIDATE: 'Không có candidate', NO_CANDIDATE_DLH_A350: 'Không có CR DLH A350',
};

function gridPrefs() {
  try { return JSON.parse(localStorage.getItem(GRID_PREFS_KEY) || '{}'); } catch { return {}; }
}
function saveGridPrefs(preferences) {
  try { localStorage.setItem(GRID_PREFS_KEY, JSON.stringify(preferences)); } catch {}
}

function gridControls() {
  const preferences = gridPrefs();
  const hidden = new Set(preferences.hidden || []);
  const pinned = new Set(preferences.pinned || ['task_no']);
  return `<button type="button" class="ghost wrap-toggle ${preferences.wrap ? 'active' : ''}" title="Tự xuống dòng để xem hết nội dung trong ô">↵ Xuống dòng: ${preferences.wrap ? 'Bật' : 'Tắt'}</button><details class="column-menu"><summary class="ghost">Cột</summary><div class="column-pop"><div class="column-pop-head"><b>Hiển thị và ghim cột</b><button type="button" class="link reset-columns">Mặc định</button></div>${taskColumns.map(([key, label]) => `<label><input type="checkbox" class="column-visible" data-col="${key}" ${hidden.has(key) ? '' : 'checked'}><span>${label}</span><input type="checkbox" class="column-pin" data-col="${key}" ${pinned.has(key) ? 'checked' : ''}><em>Ghim</em></label>`).join('')}</div></details>`;
}

function displayValue(item, key) {
  if (key === 'match_layer') {
    const labels = {1: '1 · MPD key', 2: '2 · Tiền tố mã', 3: '3 · Nội dung Title'};
    return labels[item[key]] || '—';
  }
  if (key === 'match_score') return item[key] == null ? '—' : `${Number(item[key]).toFixed(1)}%`;
  if (key === 'suggested_mhr') return item[key] == null ? '—' : esc(fmt(item[key]));
  if (key === 'match_status') return statusBadge(item[key]) + (item.added_to_db ? '<small>Thêm vào Database</small>' : '');
  if (key === 'match_method') return METHOD_LABELS[item[key]] || (item[key] ? esc(item[key]) : '—');
  if (key === 'amos_reference') {
    if (item.matched && item.amos_reference) return `<button class="link amos-ref" data-id="${item.id}" title="Xem bản ghi AMOS">${esc(item.amos_reference)}</button>`;
    if ([2, 3].includes(item.match_layer) && item.suggested_task_no) return `<button class="link amos-ref" data-id="${item.id}" title="Xem gợi ý">Gợi ý: ${esc(item.suggested_task_no)}</button>`;
    return '—';
  }
  if (key === 'important_job') return item[key] ? '<span class="flag yes">X</span>' : '—';
  if (key === 'not_in_database') return item[key] ? `<span class="flag alert">X</span>${item.added_to_db ? '<small>Đã thêm vào Database</small>' : ''}` : '—';
  if (key === 'planning_mhr') {
    if (!item.matched && item.reviewed_mhr == null) return '—';
    const value = item.reviewed_mhr ?? item.planning_mhr;
    return `${esc(fmt(value))}${item.reviewed_mhr != null ? '<small>Review</small>' : ''}`;
  }
  const value = key === 'title' ? (item.title || item.source_title) : item[key];
  return value == null || value === '' ? '—' : esc(value);
}

function cellTooltip(item, key) {
  if (key === 'match_status') return esc(STATUS_LABELS[item[key]] || '');
  return esc((key === 'title' ? (item.title || item.source_title) : item[key]) ?? '');
}

function taskTable(items) {
  const preferences = gridPrefs();
  const widths = preferences.widths || {};
  return `<div class="excel-grid ${preferences.wrap ? 'wrap-text' : ''}" id="taskGrid"><table><colgroup>${taskColumns.map(([key,, width]) => `<col data-col="${key}" style="width:${widths[key] || width}px">`).join('')}<col data-col="actions" style="width:${ACTION_COL_WIDTH}px"></colgroup><thead><tr>${taskColumns.map(([key, label]) => `<th class="col-${key}" data-key="${key}"><button class="sort-head" data-sort="${key}">${label}<span>${state.sortBy === key ? (state.sortDir === 'asc' ? '▲' : '▼') : ''}</span></button><i class="col-resizer" data-col="${key}"></i></th>`).join('')}<th class="action-col">Thao tác</th></tr></thead><tbody>${items.map(item => `<tr>${taskColumns.map(([key]) => `<td class="col-${key}" title="${cellTooltip(item, key)}"><div class="cell-value">${displayValue(item, key)}</div></td>`).join('')}<td class="action-col"><button class="link edit-item" data-id="${item.id}">Review</button></td></tr>`).join('') || `<tr><td colspan="${taskColumns.length + 1}" class="empty">Không có dữ liệu</td></tr>`}</tbody></table></div>`;
}

function bindTaskGrid() {
  const grid = $('#taskGrid');
  if (!grid) return;
  const apply = () => {
    const preferences = gridPrefs();
    const hidden = new Set(preferences.hidden || []);
    const pinned = new Set(preferences.pinned || ['task_no']);
    let left = 0, total = ACTION_COL_WIDTH;
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
  // Wrap long text inside cells (row height grows instead of cutting text)
  $$('.wrap-toggle').forEach(button => button.onclick = () => {
    const preferences = gridPrefs();
    preferences.wrap = !preferences.wrap;
    saveGridPrefs(preferences);
    grid.classList.toggle('wrap-text', preferences.wrap);
    button.classList.toggle('active', preferences.wrap);
    button.textContent = `↵ Xuống dòng: ${preferences.wrap ? 'Bật' : 'Tắt'}`;
    apply();
  });
  const reset = $('.reset-columns');
  if (reset) reset.onclick = () => { try { localStorage.removeItem(GRID_PREFS_KEY); } catch {} renderReviewPanel(); };
  $$('.sort-head').forEach(button => button.onclick = () => {
    const key = button.dataset.sort;
    if (state.sortBy === key) state.sortDir = state.sortDir === 'asc' ? 'desc' : 'asc'; else { state.sortBy = key; state.sortDir = 'asc'; }
    state.reviewPage = 1;
    if (state.reviewTab === 'detail') { renderReviewPanel(); return; }
    // report tabs are sorted in the browser
    const direction = state.sortDir === 'asc' ? 1 : -1;
    state.visibleItems.sort((a, b) => String(a[key] ?? '').localeCompare(String(b[key] ?? ''), undefined, {numeric: true}) * direction);
    $('#reviewPanel .table-wrap').innerHTML = taskTable(state.visibleItems);
    bindTaskGrid();
    bindEdit();
  });
  // Click on an AMOS Reference (or a layer 2/3 suggestion) opens the comparison popup
  $$('.amos-ref').forEach(button => button.onclick = event => { event.stopPropagation(); openAmosRef(button.dataset.id); });
  $$('.col-resizer').forEach(handle => handle.onpointerdown = event => {
    event.preventDefault(); event.stopPropagation();
    const key = handle.dataset.col, col = grid.querySelector(`col[data-col="${key}"]`), start = event.clientX, startWidth = parseFloat(col.style.width) || 120;
    const move = pointer => { col.style.width = `${Math.max(70, startWidth + pointer.clientX - start)}px`; apply(); };
    const up = () => { document.removeEventListener('pointermove', move); document.removeEventListener('pointerup', up); const preferences = gridPrefs(); preferences.widths = preferences.widths || {}; preferences.widths[key] = parseFloat(col.style.width); saveGridPrefs(preferences); apply(); };
    document.addEventListener('pointermove', move); document.addEventListener('pointerup', up);
  });
}

/* =========================================================================
   7. AMOS POPUP – Tally row vs its AMOS record(s), other candidates
   ========================================================================= */
const AMOS_LABELS = {
  source_label: 'Nguồn', amp_name: 'AMP Name / Rev', amp_date: 'AMP Date', mp_name: 'MP Name / Issue / Rev',
  taskcard_no: 'Taskcard No. / Rev', taskcard_ident: 'Taskcard Ident.', task_no: 'Task No. / Rev',
  mpd_key: 'MPD key', task_type: 'Type', aircraft_type: 'A/C Type', customer: 'Customer',
  effectivity: 'Effectivity', title: 'Taskcard Title', phase: 'Phase', zone: 'Zone', area: 'Area',
  panel: 'Panel', special_code: 'Special Code', resource_type: 'Resource Type',
  classification: 'Classification', type_code: 'Type Code', qualification: 'Qualification',
  planning_mhr: 'Planning MHR', information_skill: 'Information Skill', information_mhr: 'Information MHR',
  linked_jobcards: 'Linked Jobcards', jobcards_title: 'Jobcards Title', description: 'Description',
  requirement_link: 'Requirement Link',
};
const AMOS_WIDE_FIELDS = ['description', 'requirement_link', 'panel', 'title'];

async function openAmosRef(itemId) {
  let result;
  try { result = await api(`/api/items/${itemId}/amos`); } catch (error) { toast(error.message); return; }
  const item = result.item;
  const dialog = $('#dataDialog');
  dialog.classList.add('wide');
  $('#dataDetailTitle').textContent = `${result.is_suggestion ? 'Gợi ý AMOS' : 'Đối chiếu AMOS'} · ${item.task_no}`;
  $('#dataDetailSub').textContent = `${item.source_title || ''}${item.event_type ? ` · ${item.event_type}` : ''}`;
  $('#dataDetailBody').innerHTML = `<div class="amos-scroll">
      ${amosComparison(result)}
      ${amosMissing(result.missing)}
      <h3>${result.is_suggestion ? 'Bản ghi gợi ý (chưa gán, cần review)' : `Bản ghi đã chọn (${result.selected.length})`}</h3>
      ${result.selected.map((record, index) => amosRecordBlock(record, index, result.selected.length)).join('') || '<div class="notice">Không tìm thấy bản ghi.</div>'}
      <h3>Ứng viên khác không được chọn (${result.others.length})</h3>
      ${amosOthers(result.others)}
    </div>`;
  $$('#dataDetailBody .edit-record').forEach(button => button.onclick = () => {
    dialog.close();
    openRecordForm({mode: 'edit', ampId: Number(button.dataset.amp), itemId: item.matched ? item.id : null});
  });
  dialog.showModal();
}

function amosCheckBadge(ok) {
  if (ok === true) return badge('Khớp', 'green');
  if (ok === false) return badge('Khác', 'red');
  return badge('Không có dữ liệu', 'blue');
}

function amosComparison(result) {
  const item = result.item;
  const rows = result.checks.map(check => `<tr><td><b>${esc(check.field)}</b>${check.hint ? `<br><small>${esc(check.hint)}</small>` : ''}</td><td>${esc(check.tally ?? '—')}</td><td>${esc(check.amos ?? '—')}</td><td>${amosCheckBadge(check.ok)}</td></tr>`).join('');
  return `<div class="panel"><div class="panel-head"><div><h3>So sánh Tally Sheet và AMOS</h3><p>${esc(result.rule)}</p></div>${statusBadge(item.match_status)}</div>
    <div class="table-wrap"><table><thead><tr><th>Trường</th><th>Tally Sheet</th><th>AMOS</th><th>Kết quả</th></tr></thead><tbody>${rows}</tbody></table></div>
    ${item.match_note ? `<div class="notice">${esc(item.match_note)}</div>` : ''}
    ${item.reviewed_mhr != null ? `<div class="notice">MHR đã được review thủ công: ${esc(fmt(item.reviewed_mhr))} giờ</div>` : ''}</div>`;
}

function amosMissing(missing) {
  if (!missing.length) return '';
  const names = missing.map(entry => esc([entry.amp_name || entry.customer, entry.taskcard_no || entry.task_no, entry.taskcard_ident].filter(Boolean).join(' | ')));
  return `<div class="notice">${missing.length} bản ghi đã dùng khi đánh giá không còn trong MiniDB hiện tại (MiniDB đã được nạp lại từ dữ liệu AMOS mới): ${names.join('; ')}</div>`;
}

function amosRecordBlock(record, index, count) {
  const fields = Object.entries(AMOS_LABELS).filter(([key]) => record[key] != null && record[key] !== '');
  return `<div class="panel"><div class="panel-head"><div><h3>${count > 1 ? `Bản ghi ${index + 1}/${count} · ` : ''}${esc(record.source_label)} · ${esc(record.taskcard_no || record.task_no)} ${esc(record.taskcard_ident || '')}</h3><p>${esc(record.amp_name || record.customer || '')}${record.amp_date ? ` · ${esc(record.amp_date)}` : ''}</p></div>
    <div class="record-actions">${record.origin === 'MANUAL' ? badge('Thêm thủ công', 'amber') : ''}${record.edited ? badge('Đã sửa', 'amber') : ''}${badge(`MHR ${record.planning_mhr || '—'}`, 'blue')}<button type="button" class="ghost edit-record" data-amp="${record.id}">✎ Sửa bản ghi</button></div></div>
    <div class="panel-body"><div class="detail-grid">${fields.map(([key, label]) => `<div class="detail-field ${AMOS_WIDE_FIELDS.includes(key) ? 'wide' : ''}"><span>${label}</span><b>${esc(record[key])}</b></div>`).join('')}</div></div></div>`;
}

function amosOthers(others) {
  if (!others.length) return '<div class="notice">Không có ứng viên nào khác.</div>';
  const rows = others.map(other => `<tr><td>${esc(other.source_label)}<br><small>${esc(other.amp_name || other.customer || '—')}</small></td><td>${esc(other.amp_date || '—')}</td><td>${esc(other.taskcard_no || '—')}</td><td>${esc(other.taskcard_ident || '—')}</td><td>${esc(other.task_no)}</td><td>${esc(other.zone || '—')}</td><td>${esc(other.area || '—')}</td><td>${esc(other.planning_mhr || '—')}</td><td>${other.same_amp ? badge('Cùng AMP', 'amber') : badge('Không chọn', 'blue')}</td></tr>`).join('');
  return `<div class="panel table-wrap"><table><thead><tr><th>Nguồn / AMP</th><th>AMP Date</th><th>Taskcard</th><th>Ident.</th><th>Task No.</th><th>Zone</th><th>Area</th><th>Planning MHR</th><th>Trạng thái</th></tr></thead><tbody>${rows}</tbody></table></div>`;
}

/* =========================================================================
   8. REVIEW DIALOG + MiniDB ACTIONS
   ========================================================================= */
function bindEdit() {
  $$('.edit-item').forEach(button => button.onclick = () => {
    const item = state.visibleItems.find(row => row.id == button.dataset.id) || {id: button.dataset.id, task_no: 'Task'};
    state.editItem = item;
    $('#editTask').textContent = `${item.task_no || 'Task'}${item.match_status ? ` · ${STATUS_LABELS[item.match_status] || item.match_status}` : ''}`;
    const form = $('#editForm');
    form.reviewed_mhr.value = item.reviewed_mhr ?? item.planning_mhr ?? '';
    form.important_job.checked = Boolean(item.important_job);
    form.review_note.value = item.review_note || '';
    form.reason.value = '';
    renderReviewDbActions(item);
    $('#editDialog').showModal();
  });
}

// Under the review form: edit the matched AMOS record(s), or add an unmatched task to the MiniDB
function renderReviewDbActions(item) {
  const host = $('#reviewDbActions');
  if (item.match_status === 'NOT_APPLICABLE') { host.innerHTML = ''; return; }
  if (item.matched) {
    host.innerHTML = `<b>Dữ liệu AMOS (MiniDB)</b><p>Sửa giá trị của bản ghi đã khớp. Giá trị mới ghi đè giá trị cũ trong MiniDB.</p><button type="button" class="ghost" id="reviewEditAmos">✎ Sửa dữ liệu AMOS</button>`;
    $('#reviewEditAmos').onclick = () => { $('#editDialog').close(); openAmosRef(item.id); };
    return;
  }
  const suggestion = [2, 3].includes(item.match_layer)
    ? `<button type="button" class="ghost" id="reviewSeeSuggestion">Xem gợi ý ${esc(item.suggested_task_no || '')}</button>` : '';
  host.innerHTML = `<b>Task chưa có trong Database</b><p>${item.added_to_db ? 'Task đã được thêm vào Database nhưng chưa khớp. Kiểm tra lại số Task.' : 'Nếu task hợp lệ, thêm vào MiniDB (ALL AMP Task hoặc Customer AMP).'}</p><div class="record-actions"><button type="button" class="primary" id="reviewAddDb">＋ Thêm vào Database</button>${suggestion}</div>`;
  $('#reviewAddDb').onclick = () => { $('#editDialog').close(); openRecordForm({mode: 'add', itemId: item.id}); };
  const see = $('#reviewSeeSuggestion');
  if (see) see.onclick = () => { $('#editDialog').close(); openAmosRef(item.id); };
}

async function submitEdit(event) {
  event.preventDefault();
  const formData = new FormData(event.target);
  const body = {reviewed_mhr: formData.get('reviewed_mhr') === '' ? null : Number(formData.get('reviewed_mhr')), important_job: formData.get('important_job') === 'on', review_note: formData.get('review_note'), reason: formData.get('reason')};
  try {
    await api(`/api/items/${state.editItem.id}`, {method: 'PATCH', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)});
    $('#editDialog').close(); toast('Đã lưu thay đổi và lịch sử'); state.detail = null; await renderReviewPanel();
  } catch (error) { toast(error.message); }
}

/* =========================================================================
   9. DATA STORE ("Kho dữ liệu")
   ========================================================================= */
async function renderDatabase() {
  $('#dashboardView').innerHTML = '<div class="panel empty">Đang tải dữ liệu…</div>';
  await loadDataBrowser();
}

async function loadDataBrowser() {
  const filters = state.dataFilters;
  let url;
  if (state.dataTab === 'amos_vna' || state.dataTab === 'amos_customer') {
    const source = state.dataTab === 'amos_vna' ? 'VNA' : 'CUSTOMER';
    url = `/api/data/amos?${new URLSearchParams({q: state.dataQuery, source, aircraft_type: filters.aircraft_type, customer: filters.customer, classification: filters.classification, origin: filters.origin, page: state.dataPage})}`;
  } else if (state.dataTab === 'jobcards') {
    url = `/api/data/jobcards?${new URLSearchParams({q: state.dataQuery, aircraft_type: filters.aircraft_type, classification: filters.classification, page: state.dataPage})}`;
  } else {
    const category = state.dataTab === 'important_external' ? 'Công việc lưu ý' : filters.category;
    url = `/api/data/external?${new URLSearchParams({q: state.dataQuery, category, status: filters.external_status, page: state.dataPage})}`;
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
  let summary, title, subtitle, filters, table, extra = '';
  if (isAmp) {
    summary = `<div class="data-summary"><div class="card metric"><span>AMP VNA</span><strong>${fmt(result.stats.vna)}</strong></div><div class="card metric"><span>AMP khách hàng</span><strong>${fmt(result.stats.customer)}</strong></div><div class="card metric"><span>Tổng AMP Task</span><strong>${fmt(result.stats.total)}</strong><small>Thêm thủ công: ${fmt(result.stats.manual)} · Đã sửa: ${fmt(result.stats.edited)}</small></div><div class="card metric"><span>AMOS Watch Item</span><strong>${fmt(result.stats.watch_items)}</strong></div></div>`;
    title = tab === 'amos_vna' ? 'Bảng AMP VNA (ALL AMP Task)' : 'Bảng AMP khách hàng (Customer AMP)'; subtitle = 'Dữ liệu nhập từ AMOS vào MiniDB; thay đổi thủ công chỉ ghi vào MiniDB';
    filters = `<select id="aircraftFilter">${options(result.filters.aircraft_types, state.dataFilters.aircraft_type, 'Tất cả loại tàu bay')}</select><select id="customerFilter">${options(result.filters.customers, state.dataFilters.customer, 'Tất cả khách hàng')}</select><select id="classFilter">${options(result.filters.classifications, state.dataFilters.classification, 'Tất cả phân loại')}</select><select id="originFilter"><option value="all">Tất cả nguồn gốc</option><option value="amos" ${state.dataFilters.origin === 'amos' ? 'selected' : ''}>Từ AMOS (chưa sửa)</option><option value="manual" ${state.dataFilters.origin === 'manual' ? 'selected' : ''}>Thêm thủ công</option><option value="edited" ${state.dataFilters.origin === 'edited' ? 'selected' : ''}>Đã sửa</option></select>`;
    extra = '<a class="ghost" href="/api/amp-changes/export" style="display:inline-flex;align-items:center;text-decoration:none">⤓ Xuất thay đổi MiniDB</a>';
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
  $('#dashboardView').innerHTML = `<div class="hero-strip"><div><h2>Kho dữ liệu</h2><p>Xem các bảng dữ liệu AMOS và dữ liệu xây dựng ngoài</p></div><div class="status-chip">${fmt(result.total)} kết quả</div></div>${catalog}${summary}<div class="panel data-shell"><div class="panel-head"><div><h2>${title}</h2><p>${subtitle}</p></div><b>${fmt(result.total)} kết quả</b></div><div class="toolbar"><input id="dataSearch" placeholder="Tìm mã, taskcard, title hoặc mô tả" value="${esc(state.dataQuery)}">${filters}<button class="ghost" id="clearDataFilters">Xóa lọc</button>${extra}</div><div class="table-wrap">${table}</div><div class="pagination"><span style="margin-right:auto">Trang ${result.page} / ${Math.max(1, Math.ceil(result.total / result.page_size))}</span><button class="ghost" id="dataPrev" ${result.page <= 1 ? 'disabled' : ''}>Trước</button><button class="ghost" id="dataNext" ${result.page * result.page_size >= result.total ? 'disabled' : ''}>Sau</button></div></div>`;
  bindDataBrowser();
}

function amosDataTable(items) { return `<table><thead><tr><th>Task</th><th>Title</th><th>Nguồn / AMP</th><th>Loại tàu bay</th><th>Khách hàng</th><th>Phase / Zone</th><th>Special Code</th><th>MHR</th><th>Phân loại</th><th></th></tr></thead><tbody>${items.map(item => `<tr><td><b>${esc(item.task_no)}</b><br><small>${esc(item.taskcard_no ? `${item.taskcard_no} ${item.taskcard_ident || ''}` : '')}</small></td><td>${esc(item.title || '—')}<br><small>${esc((item.description || '').slice(0, 90))}</small></td><td>${badge(item.source, item.source === 'VNA' ? 'blue' : 'green')}${item.origin === 'MANUAL' ? badge('Thủ công', 'amber') : ''}${item.edited ? badge('Đã sửa', 'amber') : ''}<br><small>${esc(item.amp_name || '')}</small></td><td>${esc(item.aircraft_type || '—')}</td><td>${esc(item.customer || '—')}</td><td>${esc(item.phase || '—')}<br><small>${esc(item.zone || '—')}</small></td><td>${esc(item.special_code || '—')}</td><td>${esc(item.planning_mhr || '—')}</td><td>${esc(item.classification || '—')}</td><td style="white-space:nowrap"><button class="link view-data" data-id="${item.id}">Xem</button> · <button class="link edit-data" data-id="${item.id}">Sửa</button></td></tr>`).join('') || '<tr><td colspan="10" class="empty">Không tìm thấy dữ liệu phù hợp</td></tr>'}</tbody></table>`; }
function jobcardDataTable(items) { return `<table><thead><tr><th>Jobcard</th><th>Title</th><th>Loại tàu bay</th><th>Phase / Zone</th><th>Area</th><th>Special Code</th><th>MHR</th><th>Phân loại</th><th></th></tr></thead><tbody>${items.map(item => `<tr><td><b>${esc(item.task_no)}</b></td><td>${esc(item.title || '—')}<br><small>${esc((item.description || '').slice(0, 90))}</small></td><td>${esc(item.aircraft_type || '—')}</td><td>${esc(item.phase || '—')}<br><small>${esc(item.zone || '—')}</small></td><td>${esc(item.area || '—')}</td><td>${esc(item.special_code || '—')}</td><td>${esc(item.planning_mhr || '—')}</td><td>${esc(item.classification || '—')}</td><td><button class="link view-data" data-id="${item.id}">Xem</button></td></tr>`).join('') || '<tr><td colspan="9" class="empty">Không tìm thấy Jobcard phù hợp</td></tr>'}</tbody></table>`; }
function externalDataTable(items, message) { return `<table><thead><tr><th>Danh mục</th><th>Mã nguồn</th><th>Giá trị chuẩn</th><th>Loại tàu bay</th><th>Khách hàng</th><th>Mô tả</th><th>Trạng thái</th><th></th></tr></thead><tbody>${items.map(item => `<tr><td>${badge(item.category)}</td><td><b>${esc(item.code)}</b></td><td>${esc(item.canonical_value || '—')}</td><td>${esc(item.aircraft_type || '—')}</td><td>${esc(item.customer || '—')}</td><td>${esc(item.description || '—')}</td><td>${badge(item.status, item.status === 'Có hiệu lực' ? 'green' : 'amber')}</td><td><button class="link view-data" data-id="${item.id}">Xem</button></td></tr>`).join('') || `<tr><td colspan="8" class="empty">${esc(message)}</td></tr>`}</tbody></table>`; }

function bindDataBrowser() {
  $$('[data-data-tab]').forEach(button => button.onclick = () => { state.dataTab = button.dataset.dataTab; state.dataPage = 1; state.dataQuery = ''; loadDataBrowser(); });
  let timer;
  $('#dataSearch').oninput = event => { clearTimeout(timer); timer = setTimeout(() => { state.dataQuery = event.target.value; state.dataPage = 1; loadDataBrowser(); }, 350); };
  let bindings = [];
  if (state.dataTab === 'amos_vna' || state.dataTab === 'amos_customer') bindings = [['aircraftFilter', 'aircraft_type'], ['customerFilter', 'customer'], ['classFilter', 'classification'], ['originFilter', 'origin']];
  else if (state.dataTab === 'jobcards') bindings = [['aircraftFilter', 'aircraft_type'], ['classFilter', 'classification']];
  else bindings = [['categoryFilter', 'category'], ['externalStatusFilter', 'external_status']];
  bindings.forEach(([id, key]) => { const element = $('#' + id); if (element) element.onchange = event => { state.dataFilters[key] = event.target.value; state.dataPage = 1; loadDataBrowser(); }; });
  $('#clearDataFilters').onclick = () => { state.dataQuery = ''; Object.keys(state.dataFilters).forEach(key => state.dataFilters[key] = 'all'); state.dataPage = 1; loadDataBrowser(); };
  $('#dataPrev').onclick = () => { state.dataPage -= 1; loadDataBrowser(); };
  $('#dataNext').onclick = () => { state.dataPage += 1; loadDataBrowser(); };
  $$('.view-data').forEach(button => button.onclick = () => showDataDetail(Number(button.dataset.id)));
  $$('.edit-data').forEach(button => button.onclick = () => openRecordForm({mode: 'edit', ampId: Number(button.dataset.id), itemId: null}));
}

const AMOS_DETAIL_LABELS = {task_no: 'Mã task/Jobcard', mpd_key: 'MPD key', taskcard_no: 'Taskcard No.', taskcard_ident: 'Taskcard Ident.', amp_name: 'AMP Name', amp_date: 'AMP Date', task_type: 'Type', title: 'Title', description: 'Description', source: 'Nguồn', aircraft_type: 'Loại tàu bay', customer: 'Khách hàng', effectivity: 'Effectivity', phase: 'Phase', zone: 'Zone', area: 'Area', panel: 'Panel', special_code: 'Special Code', resource_type: 'Resource Type', classification: 'Classification', type_code: 'Type Code', qualification: 'Qualification', planning_mhr: 'Planning MHR', information_skill: 'Information Skill', information_mhr: 'Information MHR', requirement_link: 'Requirement Link', linked_jobcards: 'Linked Jobcards', jobcards_title: 'Jobcards Title', origin: 'Nguồn gốc', updated_by: 'Người cập nhật', updated_at: 'Cập nhật lúc'};
const EXTERNAL_DETAIL_LABELS = {category: 'Danh mục', code: 'Mã nguồn', canonical_value: 'Giá trị chuẩn', aircraft_type: 'Loại tàu bay', customer: 'Khách hàng', description: 'Mô tả', reason: 'Lý do', status: 'Trạng thái', updated_by: 'Người cập nhật', updated_at: 'Cập nhật lúc'};

function showDataDetail(id) {
  const item = state.dataResult.items.find(row => row.id === id); if (!item) return;
  const isAmos = ['amos_vna', 'amos_customer', 'jobcards'].includes(state.dataTab);
  const labels = isAmos ? AMOS_DETAIL_LABELS : EXTERNAL_DETAIL_LABELS;
  $('#dataDialog').classList.remove('wide');
  $('#dataDetailTitle').textContent = isAmos ? (item.task_no || 'Chi tiết dữ liệu AMOS') : (item.code || 'Chi tiết dữ liệu ngoài');
  $('#dataDetailSub').textContent = isAmos ? 'Bản ghi MiniDB nhập từ AMOS' : 'Bản ghi do VAECO quản lý ngoài AMOS';
  $('#dataDetailBody').innerHTML = `<div class="detail-grid">${Object.entries(labels).filter(([key]) => key in item).map(([key, label]) => `<div class="detail-field ${['description', 'linked_jobcards', 'requirement_link'].includes(key) ? 'wide' : ''}"><span>${label}</span><b>${esc(item[key] ?? '—')}</b></div>`).join('')}</div>`;
  $('#dataDialog').showModal();
}

/* =========================================================================
   10. UPLOAD (step 1 form – all fields mandatory)
   ========================================================================= */
let uploadOptions = null;   // dropdown values, loaded from the MiniDB

function fillSelect(select, values, placeholder) {
  const current = select.value;
  select.innerHTML = (placeholder ? `<option value="">${placeholder}</option>` : '') + values.map(value => `<option value="${esc(value)}">${esc(value)}</option>`).join('');
  if (values.includes(current)) select.value = current;
}

async function openUploadDialog() {
  const form = $('#uploadForm');
  try { uploadOptions = uploadOptions || await api('/api/upload-options'); } catch (error) { toast(error.message); return; }
  fillSelect(form.customer, uploadOptions.customers, '— Chọn khách hàng —');
  fillSelect(form.aircraft_type, uploadOptions.aircraft_types, '— Chọn loại tàu bay —');
  fillSelect(form.tally_format, uploadOptions.tally_formats);
  if (!form.tally_format.value) form.tally_format.value = uploadOptions.default_tally_format;
  updateUploadPlan();
  $('#uploadDialog').showModal();
}

// Customer chosen -> propose its Tally Sheet layout (the user can still change it)
function onUploadCustomerChange() {
  const form = $('#uploadForm');
  const key = form.customer.value.trim().toUpperCase();
  form.tally_format.value = uploadOptions?.tally_format_by_customer?.[key] || uploadOptions?.default_tally_format || 'VietJet';
  updateUploadPlan();
}

// Show which sources will be searched, in which order
async function updateUploadPlan() {
  const form = $('#uploadForm');
  const hint = $('#uploadPlan');
  if (!form.customer.value || !form.aircraft_type.value) { hint.textContent = 'Chọn khách hàng và loại tàu bay để xem thứ tự tìm dữ liệu.'; return; }
  try {
    const plan = await api(`/api/matching-plan?${new URLSearchParams({customer: form.customer.value, aircraft_type: form.aircraft_type.value})}`);
    hint.innerHTML = 'Thứ tự tìm dữ liệu: ' + plan.steps.map((step, index) => `<b>${index + 1}.</b> ${esc(step)}`).join(' &nbsp; ');
  } catch (error) { hint.textContent = error.message; }
}

async function submitUpload(event) {
  event.preventDefault();
  const button = event.submitter;
  const restore = setBusy(button, 'Đang lưu hồ sơ…');
  try {
    const result = await api('/api/tallies', {method: 'POST', body: new FormData(event.target)});
    $('#uploadDialog').close();
    event.target.reset();
    restore();
    toast('Đã tiếp nhận Tally Sheet');
    await loadDashboard(false);
    await openWorkflow(result.tally_id, 2);
  } catch (error) { toast(error.message); restore(); }
}

/* =========================================================================
   11. MiniDB RECORDS ("Thêm vào Database" / "Sửa bản ghi")
   Only the MiniDB changes; every change is logged and exportable.
   ========================================================================= */
let ampFieldDefs = null;            // field list from /api/amp-fields
let recordContext = null;           // {mode: 'add'|'edit', itemId, ampId, record}

async function openRecordForm(context) {
  try {
    ampFieldDefs = ampFieldDefs || await api('/api/amp-fields');
    recordContext = {...context};
    const form = $('#recordForm');
    form.reason.value = '';
    $('#recordFields').innerHTML = '';   // start clean (typed values are only kept when switching VNA/Customer)
    if (context.mode === 'add') {
      const defaults = await api(`/api/items/${context.itemId}/add-form`);
      recordContext.record = defaults.values;
      $('#recordTitle').textContent = 'Thêm vào Database';
      $('#recordSub').textContent = 'Chọn nơi thêm và nhập thông tin task. Trường có * là bắt buộc.';
      $('#recordTarget').innerHTML = `<label>Thêm vào <span class="required">*</span><select name="target"><option value="VNA">ALL AMP Task (VNA)</option><option value="CUSTOMER">Customer AMP</option></select></label>`;
      form.target.value = defaults.target;
      form.target.onchange = () => renderRecordFields(form.target.value);
      renderRecordFields(defaults.target);
      $('#recordSubmit').textContent = 'Thêm vào Database';
    } else {
      recordContext.record = await api(`/api/amp/${context.ampId}`);
      const record = recordContext.record;
      $('#recordTitle').textContent = 'Sửa bản ghi MiniDB';
      $('#recordSub').textContent = `${record.source === 'VNA' ? 'ALL AMP Task' : 'Customer AMP'} · ${record.task_no}${record.amp_name ? ` · ${record.amp_name}` : ''}${record.taskcard_ident ? ` · ${record.taskcard_ident}` : ''}`;
      $('#recordTarget').innerHTML = '<p class="form-hint" style="margin:0 0 8px">Các trường nhận diện bản ghi (khóa) không sửa được để giữ liên kết với các hồ sơ khác.</p>';
      renderRecordFields(record.source);
      $('#recordSubmit').textContent = 'Lưu thay đổi';
    }
    $('#recordDialog').showModal();
  } catch (error) { toast(error.message); }
}

// Draw the inputs for VNA or Customer, keeping what the user already typed
function renderRecordFields(target) {
  const host = $('#recordFields');
  const typed = Object.fromEntries([...host.querySelectorAll('[data-field]')].map(element => [element.dataset.field, element.value]));
  const values = {...(recordContext.record || {}), ...typed};
  const required = new Set(recordContext.mode === 'add' ? ampFieldDefs.required[target] : []);
  const locked = new Set(recordContext.mode === 'edit' ? ampFieldDefs.locked : []);
  const fields = ampFieldDefs.fields.filter(field => target === 'VNA' ? field.vna : field.customer);
  host.innerHTML = fields.map(field => {
    const value = esc(values[field.name] ?? '');
    const attrs = `data-field="${field.name}" ${required.has(field.name) ? 'required' : ''} ${locked.has(field.name) ? 'disabled' : ''}`;
    const input = field.multiline ? `<textarea rows="3" ${attrs}>${value}</textarea>` : `<input ${field.name === 'amp_date' ? 'type="date"' : ''} value="${value}" ${attrs}>`;
    return `<label style="${field.multiline ? 'grid-column:1 / -1' : ''}">${esc(field.label)} ${required.has(field.name) ? '<span class="required">*</span>' : ''}${locked.has(field.name) ? ' <small>(khóa)</small>' : ''}${input}</label>`;
  }).join('');
}

async function submitRecord(event) {
  event.preventDefault();
  const form = $('#recordForm');
  const values = Object.fromEntries([...$('#recordFields').querySelectorAll('[data-field]:not([disabled])')].map(element => [element.dataset.field, element.value]));
  const reason = form.reason.value;
  try {
    if (recordContext.mode === 'add') {
      const result = await api(`/api/items/${recordContext.itemId}/add-to-database`, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({target: form.target.value, values, reason})});
      toast(result.rematched ? `Đã thêm vào Database · ${result.rematched} dòng đã khớp lại` : 'Đã thêm vào Database nhưng dòng chưa khớp – kiểm tra lại số Task');
    } else {
      const result = await api(`/api/amp/${recordContext.ampId}`, {method: 'PATCH', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({values, reason, item_id: recordContext.itemId})});
      toast(result.changed ? `Đã lưu ${result.changed} thay đổi vào MiniDB` : 'Không có giá trị nào thay đổi');
    }
    $('#recordDialog').close();
    uploadOptions = null;   // customer / aircraft lists may have new values
    if (state.view === 'database') await loadDataBrowser();
    else await refreshReview();
  } catch (error) { toast(error.message); }
}

/* =========================================================================
   12. NAVIGATION & START-UP
   ========================================================================= */
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
$('#openUpload').onclick = () => openUploadDialog();
$('#refreshBtn').onclick = () => refreshCurrent();
$$('[data-close]').forEach(button => button.onclick = () => button.closest('dialog').close());
$('#uploadForm').onsubmit = submitUpload;
$('#uploadForm').customer.onchange = onUploadCustomerChange;
$('#uploadForm').aircraft_type.onchange = updateUploadPlan;
$('#editForm').onsubmit = submitEdit;
$('#recordForm').onsubmit = submitRecord;

loadDashboard().catch(error => { $('#dashboardView').innerHTML = `<div class="notice">${esc(error.message)}</div>`; });
