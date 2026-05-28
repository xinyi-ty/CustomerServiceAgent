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
    if (!str && str !== 0) return '--';
    const div = document.createElement('div');
    div.textContent = String(str);
    return div.innerHTML;
}

function removeThinkingTags(text) {
    if (!text) return '';
    return text.replace(/<\|im_message\|>[\s\S]*?<\/think>/g, '').trim();
}

function formatDateTime(isoStr) {
    if (!isoStr) return '--';
    try {
        const d = new Date(isoStr);
        return d.toLocaleString('zh-CN', {
            year: 'numeric', month: '2-digit', day: '2-digit',
            hour: '2-digit', minute: '2-digit', second: '2-digit'
        });
    } catch { return isoStr; }
}

function getUrgencyClass(level) {
    const map = { 'high_priority': 'high', 'medium_priority': 'medium', 'low_priority': 'low', 'high': 'high', 'medium': 'medium', 'low': 'low' };
    return map[(level || '').toLowerCase()] || 'low';
}

function formatWarranty(status) {
    if (!status) return '--';
    const map = { 'in_warranty': '保修期内', 'out_of_warranty': '已过保', 'unknown': '待核验' };
    return map[status.toLowerCase()] || status.replace(/_/g, ' ');
}

async function loadHistory() {
    try {
        let url = `${API_BASE}/history`;
        const params = new URLSearchParams();
        if (currentRole) params.set('role', currentRole);
        if (currentTicketId) params.set('ticket_id', currentTicketId);
        if (params.toString()) url += '?' + params.toString();

        const res = await fetch(url);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const result = await res.json();
        const data = Array.isArray(result) ? result : (result.tickets || []);

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
            const status = t.status || '未处理';
            const statusClass = (status === '已解决' || status === '已关闭') ? 'badge-resolved' : 'badge-pending';
            const urgencyRaw = assessment.urgency_level || 'LOW';
            const urgencyDisplay = urgencyRaw.replace(/_/g, ' ').replace('PRIORITY', '').trim() || 'LOW';
            const urgencyClass = getUrgencyClass(urgencyRaw);
            const warrantyDisplay = formatWarranty(assessment.warranty_status);
            const evidenceCount = Array.isArray(extracted.evidence_images) ? extracted.evidence_images.length : 0;
            const cardStatusClass = urgencyClass === 'high' ? 'pending' : (statusClass === 'badge-resolved' ? 'resolved' : 'medium');

            let replyRaw = t.auto_reply_sent || '';
            const replyClean = removeThinkingTags(replyRaw);

            html += `
                <div class="history-card ${cardStatusClass}" data-ticket-id="${ticketId}">
                    <div class="card-collapse-header">
                        <div class="collapse-left">
                            <span class="ticket-id">${ticketId}</span>
                            <div class="collapse-badges">
                                <span class="badge badge-${urgencyClass}">${escapeHtml(urgencyDisplay)}</span>
                                <span class="badge ${statusClass}">${escapeHtml(status)}</span>
                            </div>
                        </div>
                        <div class="collapse-arrow">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"></polyline></svg>
                        </div>
                    </div>
                    <div class="card-collapse-body">
                        <div class="card-body-inner">
                            <div class="data-section">
                                <div class="section-label">提取数据 / Extracted Data</div>
                                <div class="card-meta">
                                    <div class="meta-item"><span class="meta-label">订单号</span><span class="meta-value">${escapeHtml(extracted.order_id)}</span></div>
                                    <div class="meta-item"><span class="meta-label">产品型号</span><span class="meta-value">${escapeHtml(extracted.model_number)}</span></div>
                                    <div class="meta-item"><span class="meta-label">批次号</span><span class="meta-value">${escapeHtml(extracted.batch_code)}</span></div>
                                    <div class="meta-item"><span class="meta-label">设备SN码</span><span class="meta-value">${escapeHtml(extracted.sn_code)}</span></div>
                                    <div class="meta-item"><span class="meta-label">多模态证据</span><span class="meta-value">${evidenceCount} 个附件</span></div>
                                </div>
                            </div>
                            <div class="data-section">
                                <div class="section-label">Agent 业务评估 / Assessment</div>
                                <div class="card-meta">
                                    <div class="meta-item"><span class="meta-label">问题类别</span><span class="meta-value">${escapeHtml(assessment.issue_category)}</span></div>
                                    <div class="meta-item"><span class="meta-label">业务影响</span><span class="meta-value">${escapeHtml(assessment.business_impact)}</span></div>
                                    <div class="meta-item"><span class="meta-label">质保状态</span><span class="meta-value">${escapeHtml(warrantyDisplay)}</span></div>
                                    <div class="meta-item"><span class="meta-label">路由决策</span><span class="meta-value">${escapeHtml(t.routing_decision)}</span></div>
                                    <div class="meta-item"><span class="meta-label">创建时间</span><span class="meta-value">${formatDateTime(t.created_at)}</span></div>
                                </div>
                            </div>
                            ${replyClean ? `
                            <div class="data-section">
                                <div class="section-label">自动回复 / Auto Reply</div>
                                <div class="reply-preview">${escapeHtml(replyClean)}</div>
                            </div>` : ''}
                            <div class="card-footer">
                                ${status === '未处理' ? `<button class="process-btn" data-id="${ticketId}">标记已处理</button>` : ''}
                            </div>
                        </div>
                    </div>
                </div>`;
        }

        historyContainer.innerHTML = html;

        // 绑定折叠点击事件
        document.querySelectorAll('.card-collapse-header').forEach(header => {
            header.addEventListener('click', () => {
                header.closest('.history-card').classList.toggle('expanded');
            });
        });

        // 绑定处理按钮事件
        document.querySelectorAll('.process-btn').forEach(btn => {
            btn.addEventListener('click', async (e) => {
                e.stopPropagation();
                const id = btn.getAttribute('data-id');
                if (!id) return;
                btn.innerText = '处理中...';
                btn.disabled = true;
                try {
                    const res = await fetch(`${API_BASE}/ticket/${encodeURIComponent(id)}/process`, { method: 'POST' });
                    if (!res.ok) throw new Error(`HTTP ${res.status}`);
                    await loadHistory();
                } catch (err) {
                    alert('操作失败: ' + err.message);
                    btn.innerText = '标记已处理';
                    btn.disabled = false;
                }
            });
        });

    } catch (e) {
        console.error('加载历史记录失败:', e);
        historyContainer.innerHTML = `
            <div class="empty-state">
                <h3>数据加载失败</h3>
                <p>请检查后端服务是否正常运行于 ${API_BASE}</p>
            </div>`;
    }
}

function setActiveRole(role) {
    roleBtns.forEach(btn => btn.classList.toggle('active', btn.getAttribute('data-role') === role));
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

if (searchInput) {
    searchInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            currentTicketId = searchInput.value.trim();
            loadHistory();
        }
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
    backBtn.addEventListener('click', () => { window.location.href = 'welcome.html'; });
}

document.addEventListener('DOMContentLoaded', loadHistory);