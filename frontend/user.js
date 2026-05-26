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
const backBtn = document.getElementById('backToWelcome');

// 后端地址
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

// 返回欢迎页
if (backBtn) {
    backBtn.addEventListener('click', () => {
        window.location.href = 'welcome.html';
    });
}

submitBtn.addEventListener('click', submitComplaint);