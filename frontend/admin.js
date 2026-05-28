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
    return text.replace(/<|im_message|>[\s\S]*?<\/think>/g, '').trim();
}

function formatDateTime(isoStr) {
    if (!isoStr) return '—';
    try {
        const d = new Date(isoStr);
        return d.toLocaleString('zh-CN', {
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit'
        });
    } catch {
        return isoStr;
    }
}

async function loadHistory() {
    try {
        let url = `${API_BASE}/history`;
        const params = new URLSearchParams();

        // 修正：这里之前拼接 URL 的方式有潜在 bug，改用更标准的方式
        if (currentRole) params.set('role', currentRole);
        if (currentTicketId) params.set('ticket_id', currentTicketId);

        if (params.toString()) {
            url += '?' + params.toString();
        }

        const res = await fetch(url);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const result = await res.json();

        // 修正：兼容直接返回数组或对象的情况
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

            // --- 修复点 1: 状态显示逻辑规范化 ---
            const status = t.status || '未处理';
            // 优化徽章颜色逻辑
            const statusClass = status === '已解决' || status === '已关闭' ? 'badge-resolved' : 'badge-pending';

            // --- 修复点 2: 紧急度获取 ---
            // 优先从 assessment 获取，否则尝试从路由决策或默认值推断
            const urgencyRaw = assessment.urgency_level || 'LOW';
            const urgency = urgencyRaw.charAt(0).toUpperCase() + urgencyRaw.slice(1).toLowerCase();
            const urgencyClass = `badge-${urgency.toLowerCase()}`;

            // --- 修复点 3: 质保状态显示 ---
            // 处理下划线，显示更友好的文本
            const warrantyRaw = assessment.warranty_status || 'UNKNOWN';
            const warrantyDisplay = warrantyRaw.replace('_', ' ');

            const routing = escapeHtml(t.routing_decision || '—');
            const createdAt = formatDateTime(t.created_at);

            const evidenceCount = Array.isArray(extracted.evidence_images) ? extracted.evidence_images.length : 0;
            const snCode = extracted.sn_code || '未提取';

            let replyRaw = t.auto_reply_sent || '';
            const replyClean = removeThinkingTags(replyRaw);
            const replyPreview = replyClean.length > 200 ? replyClean.substring(0, 200) + '...' : replyClean;

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
                            <span class="meta-value">${escapeHtml(assessment.issue_category || '未分类')}</span>
                        </div>
                        <div class="meta-item">
                            <span class="meta-label">设备 SN 码</span>
                            <span class="meta-value">${escapeHtml(snCode)}</span>
                        </div>
                        <div class="meta-item">
                            <span class="meta-label">质保状态</span>
                            <span class="meta-value">${escapeHtml(warrantyDisplay)}</span>
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
                        <!-- 仅当状态为“未处理”时显示按钮 -->
                        ${status === '未处理' ? `<button class="process-btn" data-id="${ticketId}">标记已处理</button>` : ''}
                    </div>
                </div> `;
        }

        historyContainer.innerHTML = html;

        // --- 修复点 4: 按钮事件绑定 ---
        // 移除了重复的 querySelectorAll，使用事件委托或确保只绑定一次
        document.querySelectorAll('.process-btn').forEach(btn => {
            btn.addEventListener('click', async (e) => {
                e.stopPropagation();
                const ticketId = btn.getAttribute('data-id');
                if (!ticketId) return;

                btn.innerText = '处理中...';
                btn.disabled = true;

                try {
                    const res = await fetch(`${API_BASE}/ticket/${encodeURIComponent(ticketId)}/process`, {
                        method: 'POST'
                    });
                    if (!res.ok) throw new Error(`HTTP ${res.status}`);

                    // 成功后重新加载列表
                    await loadHistory();
                } catch (err) {
                    alert('操作失败：' + err.message);
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