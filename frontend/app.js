// 防XSS函数
function escapeHtml(str) {
    if (!str) return '';
    return str.replace(/[&<>]/g, function(m) {
        if (m === '&') return '&amp;';
        if (m === '<') return '&lt;';
        if (m === '>') return '&gt;';
        return m;
    });
}

const userText = document.getElementById('userText');
const counter = document.querySelector('.counter');
const uploadBtn = document.getElementById('uploadBtn');
const uploadInput = document.getElementById('uploadInput');
const fileInfo = document.getElementById('fileInfo');
const submitBtn = document.getElementById('submitBtn');
const resultContent = document.getElementById('resultContent');
const historyContainer = document.getElementById('historyContainer');

// 后端地址（可根据部署环境修改）
const API_BASE = 'http://localhost:8000';

// 字数统计
if (userText && counter) {
    function updateCounter() {
        counter.textContent = userText.value.length + '/1000';
    }
    userText.addEventListener('input', updateCounter);
    updateCounter();
}

// 文件上传UI
if (uploadBtn && uploadInput) {
    uploadBtn.addEventListener('click', () => uploadInput.click());
    uploadInput.addEventListener('change', () => {
        const file = uploadInput.files[0];
        if (!file) {
            fileInfo.textContent = '未选择文件';
            return;
        }
        if (file.size > 50 * 1024 * 1024) {
            alert('文件不能超过50MB');
            uploadInput.value = '';
            fileInfo.textContent = '未选择文件';
            return;
        }
        let name = file.name;
        if (name.length > 30) name = name.slice(0, 27) + '...';
        fileInfo.textContent = name;
    });
}

// 提交工单
async function submitComplaint() {
    const content = userText.value.trim();
    if (!content) {
        alert('请输入问题描述');
        return;
    }
    const file = uploadInput.files[0];
    const formData = new FormData();
    formData.append('text', content);
    if (file) formData.append('image', file);
    submitBtn.disabled = true;
    const originalText = submitBtn.textContent;
    submitBtn.textContent = '⏳ 处理中...';
    try {
        const res = await fetch(`${API_BASE}/process`, {
            method: 'POST',
            body: formData
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        displayResult(data);
        loadHistory();      // 刷新历史
        // 清空文件选择
        uploadInput.value = '';
        fileInfo.textContent = '未选择文件';
    } catch (err) {
        alert('连接后端失败: ' + err.message);
    } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = originalText;
    }
}

function displayResult(data) {
    if (!resultContent) return;
    // 适配后端返回的数据结构
    const extracted = data.extracted_data || {};
    const assessment = data.agent_business_assessment || {};

    const category = escapeHtml(extracted.issue_category || assessment.issue_category || '未分类');
    const urgency = escapeHtml(assessment.urgency_level || '未知');
    const aiReply = escapeHtml(data.auto_reply_sent || '暂无回复');
    const sopGuide = escapeHtml(data.routing_decision || '请转人工');
    const warranty = escapeHtml(assessment.warranty_status || '未校验');
    const ticketId = escapeHtml(data.ticket_id || '生成中');

    resultContent.innerHTML = `
        <div class="robot-icon">🤖</div>
        <h3>分析完成</h3>
        <p>工单号：${ticketId}</p>
        <div class="feature-cards">
            <div class="feature-card">🏷 问题类别：${category}</div>
            <div class="feature-card">⚠️ 紧急程度：${urgency}</div>
            <div class="feature-card">💬 AI回复：${aiReply}</div>
            <div class="feature-card">📋 SOP建议：${sopGuide}</div>
            <div class="feature-card">🛡 保修状态：${warranty}</div>
        </div>
    `;
}

// 加载历史工单
async function loadHistory() {
    try {
        const res = await fetch(`${API_BASE}/history`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const result = await res.json();
        // 后端返回 { tickets: [...] }
        const data = result.tickets || [];
        if (!Array.isArray(data) || data.length === 0) {
            historyContainer.innerHTML = `
                <div class="history-icon">📋</div>
                <h3>暂无历史工单记录</h3>
                <p>您提交的工单记录将显示在这里</p>
            `;
            return;
        }
        let html = '';
        for (const t of data) {
            const ticketId = escapeHtml(t.ticket_id || '');
            const category = escapeHtml(t.extracted_data?.issue_category || t.agent_business_assessment?.issue_category || '无分类');
            const createdAt = escapeHtml(t.created_at || '');
            html += `
                <div class="history-card">
                    <h4>工单ID: ${ticketId}</h4>
                    <p>${category} · ${createdAt}</p>
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

// 绑定事件
submitBtn.addEventListener('click', submitComplaint);
document.addEventListener('DOMContentLoaded', loadHistory);