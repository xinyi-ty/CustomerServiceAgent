// ======================== Configuration ========================
var API_BASE = 'http://localhost:8000';

// ======================== DOM ========================
var tabBtns = document.querySelectorAll('.tab-btn');
var tabSubmit = document.getElementById('tabSubmit');
var tabTrack = document.getElementById('tabTrack');
var complaintText = document.getElementById('complaintText');
var fileInput = document.getElementById('fileInput');
var fileUploadArea = document.getElementById('fileUploadArea');
var fileClearBtn = document.getElementById('fileClearBtn');
var submitBtn = document.getElementById('submitBtn');
var searchTicketInput = document.getElementById('searchTicketInput');
var searchTicketBtn = document.getElementById('searchTicketBtn');
var ticketList = document.getElementById('ticketList');
var ticketCount = document.getElementById('ticketCount');
var refreshTicketsBtn = document.getElementById('refreshTicketsBtn');
var toastEl = document.getElementById('toast');

// ======================== State ========================
var selectedFile = null;
var toastTimer = null;

// ======================== Toast ========================
function showToast(msg, duration) {
    if (!msg) return;
    var dur = duration || 2500;
    toastEl.textContent = msg;
    toastEl.classList.add('show');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { toastEl.classList.remove('show'); }, dur);
}

// ======================== Tabs ========================
for (var i = 0; i < tabBtns.length; i++) {
    tabBtns[i].addEventListener('click', function () {
        for (var j = 0; j < tabBtns.length; j++) {
            tabBtns[j].classList.remove('active');
        }
        this.classList.add('active');
        var tab = this.getAttribute('data-tab');
        tabSubmit.style.display = tab === 'submit' ? 'block' : 'none';
        tabTrack.style.display = tab === 'track' ? 'block' : 'none';
    });
}

// ======================== File Upload ========================
fileUploadArea.addEventListener('click', function () { fileInput.click(); });

fileInput.addEventListener('change', function () {
    var file = fileInput.files[0];
    if (!file) return;
    if (file.size > 50 * 1024 * 1024) {
        showToast('文件大小不能超过 50MB');
        fileInput.value = '';
        return;
    }
    selectedFile = file;
    fileUploadArea.classList.add('selected');
    var type = file.type.startsWith('video/') ? '视频' : '图片';
    fileUploadArea.querySelector('.primary').textContent = type + ' · ' + file.name;
    fileUploadArea.querySelector('.secondary').textContent = (file.size / 1024 / 1024).toFixed(1) + ' MB';
});

fileClearBtn.addEventListener('click', function (e) {
    e.stopPropagation();
    clearFileInput();
});

function clearFileInput() {
    selectedFile = null;
    fileInput.value = '';
    fileUploadArea.classList.remove('selected');
    fileUploadArea.querySelector('.primary').textContent = '点击选择文件';
    fileUploadArea.querySelector('.secondary').textContent = '支持 JPG / PNG / MP4，最大 50MB';
}

// ======================== Submit ========================
submitBtn.addEventListener('click', async function () {
    var text = complaintText.value.trim();
    if (!text) {
        showToast('请描述您遇到的问题');
        complaintText.focus();
        return;
    }

    submitBtn.disabled = true;
    submitBtn.innerHTML = '<span class="spinner"></span> 提交中...';

    try {
        var formData = new FormData();
        formData.append('message', text);
        formData.append('session_id', 'mobile_' + Date.now());
        formData.append('history', '[]');
        if (selectedFile) formData.append('image', selectedFile);

        var res = await fetch(API_BASE + '/chat', { method: 'POST', body: formData });
        if (!res.ok) throw new Error('HTTP ' + res.status);

        var data = await res.json();
        var urgencyLabels = { 'low': '普通', 'medium': '中等', 'high': '紧急' };
        var label = urgencyLabels[data.urgency_level] || data.urgency_level;
        var msg = '工单已创建 · ' + (data.ticket_id || '') + ' · ' + label;
        showToast(msg, 4000);

        complaintText.value = '';
        clearFileInput();
        loadTickets();

    } catch (err) {
        showToast('提交失败，请检查网络后重试');
    } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = '提交客诉';
    }
});

// ======================== Search ========================
searchTicketBtn.addEventListener('click', searchTicket);
searchTicketInput.addEventListener('keypress', function (e) {
    if (e.key === 'Enter') searchTicket();
});

async function searchTicket() {
    var ticketId = searchTicketInput.value.trim();
    if (!ticketId) {
        showToast('请输入工单号');
        return;
    }

    try {
        var res = await fetch(API_BASE + '/history?ticket_id=' + encodeURIComponent(ticketId));
        if (!res.ok) throw new Error('HTTP ' + res.status);
        var result = await res.json();
        var tickets = result.tickets || [];

        if (tickets.length === 0) {
            showToast('未找到工单：' + ticketId);
            return;
        }

        renderTickets(tickets);

        // Highlight the matched ticket
        var els = document.querySelectorAll('.ticket-id');
        for (var k = 0; k < els.length; k++) {
            if (els[k].textContent.indexOf(ticketId) !== -1) {
                els[k].style.color = '#2563eb';
                els[k].style.fontWeight = '800';
            }
        }

    } catch (err) {
        showToast('查询失败，请检查网络');
    }
}

// ======================== Load Tickets ========================
refreshTicketsBtn.addEventListener('click', loadTickets);

async function loadTickets() {
    try {
        var res = await fetch(API_BASE + '/history');
        if (!res.ok) throw new Error('HTTP ' + res.status);
        var result = await res.json();
        var tickets = result.tickets || [];
        renderTickets(tickets);
    } catch (err) {
        ticketList.innerHTML =
            '<div class="empty-state">' +
            '  <div class="icon-placeholder">' +
            '    <svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>' +
            '  </div>' +
            '  <div class="main-msg">加载失败</div>' +
            '  <div class="sub-msg">请确保后端服务运行中</div>' +
            '</div>';
    }
}

// ======================== Render Tickets ========================
function renderTickets(tickets) {
    if (!tickets || tickets.length === 0) {
        ticketList.innerHTML =
            '<div class="empty-state">' +
            '  <div class="icon-placeholder">' +
            '    <svg viewBox="0 0 24 24"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>' +
            '  </div>' +
            '  <div class="main-msg">暂无工单记录</div>' +
            '  <div class="sub-msg">提交客诉后，工单将显示在这里</div>' +
            '</div>';
        ticketCount.textContent = '';
        return;
    }

    ticketCount.textContent = '共 ' + tickets.length + ' 条';

    var html = '';
    for (var i = 0; i < tickets.length; i++) {
        var t = tickets[i];
        var assessment = t.agent_business_assessment || {};
        var urgency = (assessment.urgency_level || 'low').toLowerCase();
        var status = t.status || '未处理';
        var isDone = status === '已处理' || status === '已解决';

        // Urgency dot + label
        var urgencyLabel = urgency === 'high' ? '紧急' : (urgency === 'medium' ? '中等' : '普通');
        var statusLabel = isDone ? '已处理' : status;

        var created = t.created_at || '';
        var createdShort = created.length > 10 ? created.slice(0, 10) : created;

        html += '<div class="ticket-item">';
        html += '  <div class="ticket-header">';
        html += '    <span class="ticket-id">' + escapeHtml(t.ticket_id || '--') + '</span>';
        html += '    <span><span class="urgency-dot ' + urgency + '"></span><span class="urgency-label" style="font-size:12px;font-weight:600;color:' + (urgency==='high'?'#dc2626':'#475569') + ';">' + urgencyLabel + '</span>';
        html += ' <span class="badge-status ' + (isDone?'done':'pending') + '">' + escapeHtml(statusLabel) + '</span></span>';
        html += '  </div>';
        html += '  <div class="ticket-meta">' + createdShort + ' · ' + (assessment.issue_category || '其他') + '</div>';
        if (t.auto_reply_sent) {
            var reply = t.auto_reply_sent;
            if (reply.length > 120) reply = reply.slice(0, 120) + '...';
            html += '  <div class="ticket-reply">' + escapeHtml(reply) + '</div>';
        }
        html += '</div>';
    }

    ticketList.innerHTML = html;
}

// ======================== Utils ========================
function escapeHtml(str) {
    if (!str && str !== 0) return '';
    var div = document.createElement('div');
    div.textContent = String(str);
    return div.innerHTML;
}

// ======================== Init ========================
document.addEventListener('DOMContentLoaded', loadTickets);
