var API_BASE = 'http://localhost:8000';

// ===== State =====
var currentRole = '';
var currentStatus = '';
var searchKeyword = '';
var ticketsCache = [];
var toastTimer = null;

// ===== DOM =====
var tableBody = document.getElementById('tableBody');
var statTotal = document.getElementById('statTotal');
var statPending = document.getElementById('statPending');
var statUrgent = document.getElementById('statUrgent');
var statResolved = document.getElementById('statResolved');
var statusFilter = document.getElementById('statusFilter');
var searchInput = document.getElementById('searchInput');
var searchBtn = document.getElementById('searchBtn');
var refreshBtn = document.getElementById('refreshBtn');
var toastEl = document.getElementById('toast');

// ===== Toast =====
function showToast(msg) {
    if (!msg) return;
    toastEl.textContent = msg;
    toastEl.classList.add('show');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { toastEl.classList.remove('show'); }, 2000);
}

// ===== Utils =====
function escapeHtml(str) {
    if (!str && str !== 0) return '--';
    var div = document.createElement('div');
    div.textContent = String(str);
    return div.innerHTML;
}

function fmtTime(iso) {
    if (!iso) return '--';
    try {
        var d = new Date(iso);
        var m = String(d.getMonth() + 1).padStart(2, '0');
        var day = String(d.getDate()).padStart(2, '0');
        var h = String(d.getHours()).padStart(2, '0');
        var min = String(d.getMinutes()).padStart(2, '0');
        return m + '-' + day + ' ' + h + ':' + min;
    } catch (_) { return iso; }
}

function urgencyText(level) {
    var l = (level || '').toLowerCase();
    if (l === 'high') return '紧急';
    if (l === 'medium') return '中等';
    if (l === 'low') return '普通';
    return l;
}

function urgencyClass(level) {
    var l = (level || '').toLowerCase();
    if (l === 'high' || l === 'high_priority') return 'high';
    if (l === 'medium' || l === 'medium_priority') return 'medium';
    return 'low';
}

function warrantyText(s) {
    if (!s) return '--';
    var l = s.toLowerCase();
    if (l === 'in_warranty') return '在保';
    if (l === 'out_of_warranty') return '过保';
    return '待核验';
}

function warrantyClass(s) {
    if (!s) return 'unknown';
    var l = s.toLowerCase();
    if (l === 'in_warranty') return 'in';
    if (l === 'out_of_warranty') return 'out';
    return 'unknown';
}

// ===== API =====
async function fetchTickets() {
    var url = API_BASE + '/history';
    var params = [];
    if (currentRole) params.push('role=' + encodeURIComponent(currentRole));
    if (searchKeyword) params.push('ticket_id=' + encodeURIComponent(searchKeyword));
    if (params.length) url += '?' + params.join('&');

    var res = await fetch(url);
    if (!res.ok) throw new Error('HTTP ' + res.status);
    var data = await res.json();
    var tickets = data.tickets || [];

    // 客户端过滤状态
    if (currentStatus) {
        tickets = tickets.filter(function (t) {
            return t.status === currentStatus;
        });
    }

    // 客户端搜索订单号 / SN（服务端只搜了 ticket_id）
    if (searchKeyword) {
        var kw = searchKeyword.toLowerCase();
        tickets = tickets.filter(function (t) {
            var ed = t.extracted_data || {};
            return (ed.order_id && ed.order_id.toLowerCase().indexOf(kw) >= 0) ||
                   (ed.sn_code && ed.sn_code.toLowerCase().indexOf(kw) >= 0) ||
                   (ed.model_number && ed.model_number.toLowerCase().indexOf(kw) >= 0) ||
                   (t.ticket_id && t.ticket_id.toLowerCase().indexOf(kw) >= 0);
        });
    }

    return tickets;
}

// ===== Render =====
function renderStats(tickets) {
    var total = tickets.length;
    var pending = 0;
    var urgent = 0;
    var resolved = 0;
    for (var i = 0; i < tickets.length; i++) {
        var t = tickets[i];
        if (t.status === '已处理' || t.status === '已解决') resolved++;
        else pending++;
        var a = t.agent_business_assessment || {};
        var u = (a.urgency_level || '').toLowerCase();
        if (u === 'high') urgent++;
    }
    statTotal.textContent = total;
    statPending.textContent = pending;
    statUrgent.textContent = urgent;
    statResolved.textContent = resolved;
}

function renderTable(tickets) {
    if (!tickets || tickets.length === 0) {
        tableBody.innerHTML =
            '<div class="empty-state">' +
            '  <div class="icon-box"><svg viewBox="0 0 24 24"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg></div>' +
            '  <div class="main-msg">暂无匹配工单</div>' +
            '  <div class="sub-msg">尝试调整筛选条件</div>' +
            '</div>';
        return;
    }

    var html = '';
    for (var i = 0; i < tickets.length; i++) {
        var t = tickets[i];
        var assessment = t.agent_business_assessment || {};
        var extracted = t.extracted_data || {};
        var urgency = assessment.urgency_level || 'low';
        var uClass = urgencyClass(urgency);
        var uText = urgencyText(urgency);
        var status = t.status || '未处理';
        var isDone = status === '已处理' || status === '已解决';
        var warranty = assessment.warranty_status || '';
        var replyPreview = t.auto_reply_sent || '';
        if (replyPreview.length > 100) replyPreview = replyPreview.slice(0, 100) + '...';

        html += '<div class="ticket-row" data-id="' + escapeHtml(t.ticket_id || '') + '" data-status="' + escapeHtml(status) + '">';
        html += '  <div class="row-main">';

        // Urgency
        html += '    <div class="row-cell">';
        html += '      <div class="urgency-cell">';
        html += '        <div class="urgency-bar ' + uClass + '"></div>';
        html += '        <span class="urgency-text ' + uClass + '">' + uText + '</span>';
        html += '      </div>';
        html += '    </div>';

        // Ticket info
        html += '    <div class="row-cell">';
        html += '      <div class="ticket-id">' + escapeHtml(t.ticket_id) + '</div>';
        html += '      <div style="font-size:12px;color:var(--sub);margin-top:2px;">' + escapeHtml(assessment.issue_category || '') + '</div>';
        html += '    </div>';

        // Model
        html += '    <div class="row-cell">';
        html += '      <div class="ticket-model">' + escapeHtml(extracted.model_number || '--') + '</div>';
        if (extracted.batch_code) html += '      <div class="batch">批号 ' + escapeHtml(extracted.batch_code) + '</div>';
        html += '    </div>';

        // Warranty
        html += '    <div class="row-cell">';
        html += '      <span class="warranty-badge ' + warrantyClass(warranty) + '">' + warrantyText(warranty) + '</span>';
        html += '    </div>';

        // Status
        html += '    <div class="row-cell">';
        html += '      <span class="status-badge ' + (isDone ? 'done' : 'pending') + '">' + escapeHtml(status) + '</span>';
        html += '    </div>';

        // Time + expand
        html += '    <div class="row-cell" style="display:flex;align-items:center;justify-content:space-between;">';
        html += '      <span style="color:var(--sub);font-size:12px;">' + fmtTime(t.created_at) + '</span>';
        html += '      <span class="expand-icon">&#9660;</span>';
        html += '    </div>';

        html += '  </div>';

        // ---- Detail (expandable) ----
        html += '  <div class="row-detail-wrapper">';
        html += '    <div class="row-detail">';

        html += '      <div class="detail-grid">';
        // Left: extracted data
        html += '        <div class="detail-section">';
        html += '          <h4>提取数据</h4>';
        html += '          <div class="detail-row"><span class="detail-label">订单号</span><span class="detail-value">' + escapeHtml(extracted.order_id) + '</span></div>';
        html += '          <div class="detail-row"><span class="detail-label">型号</span><span class="detail-value">' + escapeHtml(extracted.model_number) + '</span></div>';
        html += '          <div class="detail-row"><span class="detail-label">批次</span><span class="detail-value">' + escapeHtml(extracted.batch_code) + '</span></div>';
        html += '          <div class="detail-row"><span class="detail-label">SN</span><span class="detail-value">' + escapeHtml(extracted.sn_code) + '</span></div>';
        var evCount = Array.isArray(extracted.evidence_images) ? extracted.evidence_images.length : 0;
        html += '          <div class="detail-row"><span class="detail-label">附件</span><span class="detail-value">' + evCount + ' 个</span></div>';
        html += '        </div>';

        // Right: assessment
        html += '        <div class="detail-section">';
        html += '          <h4>Agent 评估</h4>';
        html += '          <div class="detail-row"><span class="detail-label">类别</span><span class="detail-value">' + escapeHtml(assessment.issue_category) + '</span></div>';
        html += '          <div class="detail-row"><span class="detail-label">影响</span><span class="detail-value">' + escapeHtml(assessment.business_impact) + '</span></div>';
        html += '          <div class="detail-row"><span class="detail-label">路由</span><span class="detail-value">' + escapeHtml(t.routing_decision) + '</span></div>';
        html += '          <div class="detail-row"><span class="detail-label">质保</span><span class="detail-value">' + warrantyText(warranty) + '</span></div>';
        html += '        </div>';
        html += '      </div>';

        // Reply
        if (t.auto_reply_sent) {
            html += '      <div class="detail-section" style="margin-top:12px;">';
            html += '        <h4>自动回复</h4>';
            html += '        <div class="detail-reply">' + escapeHtml(t.auto_reply_sent) + '</div>';
            html += '      </div>';
        }

        // Actions
        html += '      <div class="row-actions">';
        if (!isDone) {
            html += '        <button class="action-btn process" data-id="' + escapeHtml(t.ticket_id) + '">标记已处理</button>';
        } else {
            html += '        <button class="action-btn processed">已处理</button>';
        }
        html += '      </div>';

        html += '    </div>';
        html += '  </div>';
        html += '</div>';
    }

    tableBody.innerHTML = html;

    // ---- Bind events ----
    // Row click to toggle expand
    var rows = tableBody.querySelectorAll('.ticket-row');
    for (var i = 0; i < rows.length; i++) {
        rows[i].addEventListener('click', function (e) {
            // Don't toggle if click is on a button
            if (e.target.closest('.action-btn')) return;
            this.classList.toggle('expanded');
        });
    }

    // Process button
    var btns = tableBody.querySelectorAll('.action-btn.process');
    for (var i = 0; i < btns.length; i++) {
        btns[i].addEventListener('click', async function (e) {
            e.stopPropagation();
            var btn = this;
            var id = btn.getAttribute('data-id');
            if (!id) return;
            btn.disabled = true;
            btn.textContent = '处理中...';
            try {
                var res = await fetch(API_BASE + '/ticket/' + encodeURIComponent(id) + '/process', { method: 'POST' });
                if (!res.ok) throw new Error('HTTP ' + res.status);
                showToast('工单 ' + id + ' 已处理');
                // 局部更新：在 cache 中修改状态，重新渲染
                for (var j = 0; j < ticketsCache.length; j++) {
                    if (ticketsCache[j].ticket_id === id) {
                        ticketsCache[j].status = '已处理';
                        break;
                    }
                }
                renderTable(ticketsCache);
                renderStats(ticketsCache);
            } catch (err) {
                showToast('操作失败: ' + err.message);
                btn.disabled = false;
                btn.textContent = '标记已处理';
            }
        });
    }
}

// ===== Load =====
async function loadData() {
    tableBody.innerHTML = '<div class="loading-state"><div class="spinner"></div><div style="color:var(--sub);font-size:13px;">加载中...</div></div>';

    try {
        var tickets = await fetchTickets();
        ticketsCache = tickets;
        renderStats(tickets);
        renderTable(tickets);
    } catch (e) {
        tableBody.innerHTML =
            '<div class="empty-state">' +
            '  <div class="icon-box"><svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg></div>' +
            '  <div class="main-msg">加载失败</div>' +
            '  <div class="sub-msg">请检查后端服务是否运行于 ' + API_BASE + '</div>' +
            '</div>';
    }
}

// ===== Event bindings =====
// Role tabs
var roleTabs = document.querySelectorAll('.role-tab');
for (var i = 0; i < roleTabs.length; i++) {
    roleTabs[i].addEventListener('click', function () {
        for (var j = 0; j < roleTabs.length; j++) roleTabs[j].classList.remove('active');
        this.classList.add('active');
        currentRole = this.getAttribute('data-role');
        loadData();
    });
}

// Status filter
statusFilter.addEventListener('change', function () {
    currentStatus = this.value;
    loadData();
});

// Search
function doSearch() {
    searchKeyword = searchInput.value.trim();
    loadData();
}
searchBtn.addEventListener('click', doSearch);
searchInput.addEventListener('keypress', function (e) { if (e.key === 'Enter') doSearch(); });

// Refresh
refreshBtn.addEventListener('click', function () {
    searchKeyword = '';
    searchInput.value = '';
    currentStatus = '';
    statusFilter.value = '';
    loadData();
});

// ===== Init =====
document.addEventListener('DOMContentLoaded', loadData);
