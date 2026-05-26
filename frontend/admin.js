function escapeHtml(str) {
    if (!str) return '';
    return str.replace(/[&<>]/g, function(m) {
        if (m === '&') return '&amp;';
        if (m === '<') return '&lt;';
        if (m === '>') return '&gt;';
        return m;
    });
}

const API_BASE = 'http://localhost:8000';
const historyContainer = document.getElementById('historyContainer');
const refreshBtn = document.getElementById('refreshBtn');
const backBtn = document.getElementById('backToWelcome');

async function loadHistory() {
    try {
        const res = await fetch(`${API_BASE}/history`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const result = await res.json();
        const data = result.tickets || [];
        if (!Array.isArray(data) || data.length === 0) {
            historyContainer.innerHTML = `
                <div class="history-icon">📋</div>
                <h3>暂无历史工单记录</h3>
                <p>请等待用户提交工单</p>
            `;
            return;
        }
        let html = '';
        for (const t of data) {
            const ticketId = escapeHtml(t.ticket_id || '');
            const category = escapeHtml(t.extracted_data?.issue_category || t.agent_business_assessment?.issue_category || '无分类');
            const urgency = escapeHtml(t.agent_business_assessment?.urgency_level || '未知');
            const createdAt = escapeHtml(t.created_at || '未知时间');
            const reply = escapeHtml(t.auto_reply_sent || '');
            html += `
                <div class="history-card">
                    <h4>工单ID: ${ticketId}</h4>
                    <p><strong>问题类别:</strong> ${category} | <strong>紧急度:</strong> ${urgency}</p>
                    <p><strong>创建时间:</strong> ${createdAt}</p>
                    <p><strong>AI回复摘要:</strong> ${reply.substring(0, 100)}${reply.length > 100 ? '...' : ''}</p>
                </div>
            `;
        }
        historyContainer.innerHTML = html;
    } catch (e) {
        console.error(e);
        historyContainer.innerHTML = `
            <div class="history-icon">⚠️</div>
            <h3>加载失败</h3>
            <p>请检查后端服务是否运行在 ${API_BASE}</p>
        `;
    }
}

if (refreshBtn) {
    refreshBtn.addEventListener('click', loadHistory);
}
if (backBtn) {
    backBtn.addEventListener('click', () => {
        window.location.href = 'welcome.html';
    });
}

document.addEventListener('DOMContentLoaded', loadHistory);