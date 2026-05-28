const API_BASE = 'http://localhost:8000';

const historyContainer = document.getElementById('historyContainer');
const refreshBtn = document.getElementById('refreshBtn');
const backBtn = document.getElementById('backToWelcome');
const roleBtns = document.querySelectorAll('.role-btn');
const searchInput = document.getElementById('searchTicketId');
const searchBtn = document.getElementById('searchBtn');

let currentRole = 'frontline';
let currentTicketId = '';

function escapeHtml(str) {
    if (!str) return '—';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

function removeThinkingTags(text) {
    if (!text) return '';
    return text.replace(/<think>[\s\S]*?<\/think>/g, '').trim();
}

function formatDateTime(isoStr) {
    if (!isoStr) return '—';
    try {
        const d = new Date(isoStr);
        return d.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' });
    } catch { return isoStr; }
}

async function loadHistory() {
    try {
        let url = `${API_BASE}/history`;
        const params = new URLSearchParams();
        if (currentRole) params.append('role', currentRole);
        if (currentTicketId) params.append('ticket_id', currentTicketId);
        const queryString = params.toString();
        if (queryString) url += '?' + queryString;

        const res = await fetch(url);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const result = await res.json();
        const data = result.tickets || [];

        if (!Array.isArray(data) || data.length === 0) {
            historyContainer.innerHTML = `
                <div class="empty-state">
                    <h3>暂无工单记录</h3>
                    <p>当前角色视图下暂无匹配的工单数据</p>
                </div>`;
            return;
        }

        let html = '';
        for (const t of data) {
            const ticketId = escapeHtml(t.ticket_id || '');
            const assessment = t.agent_business_assessment || {};
            const extracted = t.extracted_data || {};

            const category = escapeHtml(assessment.issue_category || '未分类');
            const urgency = assessment.urgency_level || 'Low';
            const warranty = assessment.warranty_status || 'Unknown';
            const routing = escapeHtml(t.routing_decision || '—');
            const createdAt = formatDateTime(t.created_at);
            const status = t.status || '未处理';

            const evidenceCount = Array.isArray(extracted.evidence_images) ? extracted.evidence_images.length : 0;
            const snCode = extracted.sn_code || '未提取';

            let replyRaw = t.auto_reply_sent || '';
            const replyClean = removeThinkingTags(replyRaw);
            const replyPreview = replyClean.length > 200 ? replyClean.substring(0, 200) + '...' : replyClean;

            const statusClass = (status === '已处理' || status === '已解决') ? 'badge-resolved' : 'badge-pending';
            const urgencyClass = `badge-${urgency.toLowerCase()}`;

            let processButtonHtml = '';
            if (status === '未处理') {
                processButtonHtml = `<button class="process-btn" data-id="${ticketId}">标记已处理</button>`;
            }

            html += `
                <div class="history-card">
                    <div class="card-header">
                        <div class="ticket-id">${ticketId}</div>
                        <div style="display: flex; gap: 8px;">
                            <span class="badge ${urgencyClass}">${escapeHtml(urgency)}</span>
                            <span class="badge ${statusClass}">${escapeHtml(status)}</span>
                        </div>
                    </div>
                    
                    <div class="card-meta">
                        <div class="meta-item">
                            <span class="meta-label">问题类别</span>
                            <span class="meta-value">${category}</span>
                        </div>
                        <div class="meta-item">
                            <span class="meta-label">设备 SN 码</span>
                            <span class="meta-value">${escapeHtml(snCode)}</span>
                        </div>
                        <div class="meta-item">
                            <span class="meta-label">质保状态</span>
                            <span class="meta-value">${escapeHtml(warranty.replace('_', ' '))}</span>
                        </div>
                        <div class="meta-item">
                            <span class="meta-label">路由决策</span>
                            <span class="meta-value">${routing}</span>
                        </div>
                        <div class="meta-item">
                            <span class="meta-label">多模态证据</span>
                            <span class="meta-value">${evidenceCount} 个附件</span>
                        </div>
                        <div class="meta-item">
                            <span class="meta-label">创建时间</span>
                            <span class="meta-value">${createdAt}</span>
                        </div>
                    </div>
                    
                    <div class="reply-preview">${escapeHtml(replyPreview)}</div>
                    
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

                btn.innerText = '处理中...';
                btn.disabled = true;
                try {
                    const res = await fetch(`${API_BASE}/ticket/${encodeURIComponent(ticketId)}/process`, { method: 'POST' });
                    if (!res.ok) throw new Error(`HTTP ${res.status}`);
                    await loadHistory();
                } catch (err) {
                    alert('操作失败：' + err.message);
                    btn.innerText = '标记已处理';
                    btn.disabled = false;
                }
            });
        });

    } catch (e) {
        historyContainer.innerHTML = `
            <div class="empty-state">
                <h3>数据加载失败</h3>
                <p>请检查后端服务是否正常运行于 ${API_BASE}</p>
            </div>`;
    }
}

function setActiveRole(role) {
    roleBtns.forEach(btn => {
        btn.classList.toggle('active', btn.getAttribute('data-role') === role);
    });
}

roleBtns.forEach(btn => {
    btn.addEventListener('click', () => {
        currentRole = btn.getAttribute('data-role');
        currentTicketId = '';
        if (searchInput) searchInput.value = '';
        setActiveRole(currentRole);
        loadHistory();
    });
});

if (searchBtn) {
    searchBtn.addEventListener('click', () => {
        currentTicketId = searchInput.value.trim();
        loadHistory();
    });
}

if (refreshBtn) {
    refreshBtn.addEventListener('click', () => {
        currentTicketId = '';
        if (searchInput) searchInput.value = '';
        loadHistory();
    });
}

if (backBtn) {
    backBtn.addEventListener('click', () => {
        window.location.href = 'welcome.html';
    });
}

document.addEventListener('DOMContentLoaded', loadHistory);