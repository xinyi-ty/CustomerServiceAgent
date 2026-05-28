function escapeHtml(str) {
    if (!str) return '';
    return str.replace(/[&<>]/g, function(m) {
        if (m === '&') return '&amp;';
        if (m === '<') return '&lt;';
        if (m === '>') return '&gt;';
        return m;
    });
}

function removeThinkingTags(text) {
    if (!text) return '';
    return text.replace(/<think>[\s\S]*?<\/think>/g, '').trim();
}

const API_BASE = 'http://localhost:8000';
const historyContainer = document.getElementById('historyContainer');
const refreshBtn = document.getElementById('refreshBtn');
const backBtn = document.getElementById('backToWelcome');
const roleBtns = document.querySelectorAll('.role-btn');
const searchInput = document.getElementById('searchTicketId');
const searchBtn = document.getElementById('searchBtn');

let currentRole = 'frontline';
let currentTicketId = '';

async function loadHistory() {
    try {
        let url = `${API_BASE}/history`;
        const params = new URLSearchParams();
        if (currentRole) {
            params.append('role', currentRole);
        }
        if (currentTicketId) {
            params.append('ticket_id', currentTicketId);
        }
        const queryString = params.toString();
        if (queryString) url += '?' + queryString;

        const res = await fetch(url);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const result = await res.json();
        const data = result.tickets || [];

        if (!Array.isArray(data) || data.length === 0) {
            historyContainer.innerHTML = `
                <div class="empty-state">
                    <div style="font-size: 48px; margin-bottom: 12px;">📭</div>
                    <h3>暂无工单记录</h3>
                    <p style="color: #5c6f87;">当前角色暂无工单</p>
                </div>
            `;
            return;
        }

        let html = '';
        for (const t of data) {
            const ticketId = escapeHtml(t.ticket_id || '');
            const category = escapeHtml(t.extracted_data?.issue_category || t.agent_business_assessment?.issue_category || '无分类');
            const urgency = escapeHtml(t.agent_business_assessment?.urgency_level || '未知');
            const createdAt = escapeHtml(t.created_at || '未知时间');
            let replyRaw = t.auto_reply_sent || '';
            const replyClean = removeThinkingTags(replyRaw);
            const replyPreview = replyClean.length > 120 ? replyClean.substring(0, 120) + '...' : replyClean;
            const status = t.status || '未处理';

            let statusClass = (status === '已处理') ? 'status-已处理' : 'status-未处理';
            let processButtonHtml = '';
            if (status === '未处理') {
                processButtonHtml = `<button class="process-btn" data-id="${ticketId}">✓ 标记处理</button>`;
            }

            html += `
                <div class="history-card" data-ticket-id="${ticketId}">
                    <div class="card-header">
                        <div class="ticket-id">工单号: ${ticketId}</div>
                        <div class="status-badge ${statusClass}">${escapeHtml(status)}</div>
                    </div>
                    <div class="card-details">
                        <div>📂 类别: ${category}</div>
                        <div>⚡ 紧急度: ${urgency}</div>
                        <div>📅 创建: ${createdAt}</div>
                    </div>
                    <div class="reply-preview">
                        💬 回复摘要: ${escapeHtml(replyPreview)}
                    </div>
                    <div class="card-footer">
                        ${processButtonHtml}
                    </div>
                </div>
            `;
        }
        historyContainer.innerHTML = html;

        // 绑定处理按钮事件
        document.querySelectorAll('.process-btn').forEach(btn => {
            btn.addEventListener('click', async (e) => {
                e.stopPropagation();
                const ticketId = btn.getAttribute('data-id');
                if (!ticketId) return;
                const originalText = btn.innerText;
                btn.innerText = '处理中...';
                btn.disabled = true;
                try {
                    const res = await fetch(`${API_BASE}/ticket/${encodeURIComponent(ticketId)}/process`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' }
                    });
                    if (!res.ok) throw new Error(`HTTP ${res.status}`);
                    await res.json();
                    await loadHistory();
                } catch (err) {
                    console.error(err);
                    alert('处理失败：' + err.message);
                    btn.innerText = originalText;
                    btn.disabled = false;
                }
            });
        });
    } catch (e) {
        console.error(e);
        historyContainer.innerHTML = `
            <div class="empty-state">
                <div style="font-size: 48px; margin-bottom: 12px;">⚠️</div>
                <h3>加载失败</h3>
                <p>请检查后端服务是否运行在 ${API_BASE}</p>
            </div>
        `;
    }
}

function setActiveRole(role) {
    roleBtns.forEach(btn => {
        const btnRole = btn.getAttribute('data-role');
        if (btnRole === role) {
            btn.classList.add('active');
        } else {
            btn.classList.remove('active');
        }
    });
}

function handleRoleClick(role) {
    currentRole = role;
    currentTicketId = '';
    if (searchInput) searchInput.value = '';
    setActiveRole(role);
    loadHistory();
}

if (searchBtn) {
    searchBtn.addEventListener('click', () => {
        currentTicketId = searchInput.value.trim();
        loadHistory();
    });
}

roleBtns.forEach(btn => {
    btn.addEventListener('click', () => {
        const role = btn.getAttribute('data-role');
        handleRoleClick(role);
    });
});

if (refreshBtn) {
    refreshBtn.addEventListener('click', () => {
        currentTicketId = '';
        if (searchInput) searchInput.value = '';
        currentRole = 'frontline';
        setActiveRole('frontline');
        loadHistory();
    });
}
if (backBtn) {
    backBtn.addEventListener('click', () => {
        window.location.href = 'welcome.html';
    });
}

setActiveRole('frontline');
document.addEventListener('DOMContentLoaded', loadHistory);