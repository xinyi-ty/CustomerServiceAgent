// ======================== DOM 元素 ========================
const chatMessages = document.getElementById('chatMessages');
const chatInput = document.getElementById('chatInput');
const sendBtn = document.getElementById('sendBtn');
const chatFile = document.getElementById('chatFile');
const fileLabel = document.getElementById('fileLabel');
const filePreview = document.getElementById('filePreview');
const newChatBtn = document.getElementById('newChatBtn');
const backBtn = document.getElementById('backToWelcome');

const userSearchInput = document.getElementById('userSearchTicket');
const userSearchBtn = document.getElementById('userSearchBtn');
const searchResultDiv = document.getElementById('searchResult');

// ======================== 状态管理 ========================
const API_BASE = 'http://localhost:8000';
let sessionId = localStorage.getItem('chat_session_id');
if (!sessionId) {
    sessionId = 'session_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
    localStorage.setItem('chat_session_id', sessionId);
}
let conversationHistory = [];
let currentFile = null;
let isStreaming = false;

// ======================== 辅助函数 ========================
function escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

function parseThinkingReply(rawText) {
    const thinkRegex = /<think>([\s\S]*?)<\/think>/;
    const match = rawText.match(thinkRegex);
    if (match) {
        return { thinking: match[1].trim(), reply: rawText.replace(thinkRegex, '').trim() };
    }
    return { thinking: null, reply: rawText };
}

function addMessage(role, content, extra = {}) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${role}`;

    let bubbleHtml = `<div class="bubble">${escapeHtml(content)}`;
    if (extra.ticket_id) {
        bubbleHtml += `<div class="ticket-badge"><span class="badge-dot"></span>工单已自动创建：${escapeHtml(extra.ticket_id)}</div>`;
    }
    bubbleHtml += `</div>`;

    messageDiv.innerHTML = bubbleHtml;
    chatMessages.appendChild(messageDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    return messageDiv;
}

function addAssistantMessageWithThinking(fullRawText, extra = {}) {
    const { thinking, reply } = parseThinkingReply(fullRawText);
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message assistant';

    let bubbleHtml = `<div class="bubble">`;
    if (thinking) {
        bubbleHtml += `
            <div class="think-container">
                <div class="think-summary">[ 展开 AI 推理分析过程 ]</div>
                <div class="think-content">${escapeHtml(thinking)}</div>
            </div>
        `;
    }
    bubbleHtml += `<div class="reply-content"></div>`;
    if (extra.ticket_id) {
        bubbleHtml += `<div class="ticket-badge"><span class="badge-dot"></span>工单已自动创建：${escapeHtml(extra.ticket_id)}</div>`;
    }
    bubbleHtml += `</div>`;

    messageDiv.innerHTML = bubbleHtml;
    chatMessages.appendChild(messageDiv);

    const thinkContainer = messageDiv.querySelector('.think-container');
    if (thinkContainer) {
        const summary = thinkContainer.querySelector('.think-summary');
        const contentDiv = thinkContainer.querySelector('.think-content');
        summary.addEventListener('click', () => {
            const isHidden = contentDiv.style.display === 'none';
            contentDiv.style.display = isHidden ? 'block' : 'none';
            summary.textContent = isHidden ? '[ 收起 AI 推理分析过程 ]' : '[ 展开 AI 推理分析过程 ]';
        });
    }

    chatMessages.scrollTop = chatMessages.scrollHeight;
    return { messageDiv, replyText: reply };
}

async function typeTextToReplyContainer(messageDiv, text, speed = 15) {
    const replyContainer = messageDiv.querySelector('.reply-content');
    if (!replyContainer) return;
    replyContainer.textContent = '';

    for (let i = 0; i < text.length; i++) {
        if (!isStreaming) break;
        replyContainer.textContent += text[i];
        chatMessages.scrollTop = chatMessages.scrollHeight;
        await new Promise(resolve => setTimeout(resolve, speed));
    }
}

function showThinkingIndicator() {
    const thinkingDiv = document.createElement('div');
    thinkingDiv.className = 'message assistant';
    thinkingDiv.id = 'thinkingIndicator';
    thinkingDiv.innerHTML = `<div class="bubble" style="color:#64748b;">正在进行多模态分析与 SOP 检索...</div>`;
    chatMessages.appendChild(thinkingDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    return thinkingDiv;
}

function hideThinkingIndicator() {
    const indicator = document.getElementById('thinkingIndicator');
    if (indicator) indicator.remove();
}

// ======================== 工单查询功能 ========================
async function searchUserTicket() {
    const ticketId = userSearchInput.value.trim();
    if (!ticketId) {
        searchResultDiv.innerHTML = '<span style="color: #dc2626;">请输入有效的工单号</span>';
        return;
    }
    searchResultDiv.innerHTML = '正在查询...';
    try {
        const res = await fetch(`${API_BASE}/history?ticket_id=${encodeURIComponent(ticketId)}`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        const tickets = data.tickets || [];

        if (tickets.length === 0) {
            searchResultDiv.innerHTML = '<span style="color: #d97706;">未找到匹配工单，请核对工单号</span>';
        } else {
            let html = '';
            for (const t of tickets) {
                const urgency = t.agent_business_assessment?.urgency_level || '未知';
                const status = t.status || '未处理';
                html += `
                    <div class="search-result-item">
                        <div style="display:flex; justify-content:space-between; margin-bottom:4px;">
                            <strong>${escapeHtml(t.ticket_id)}</strong>
                            <span style="color: ${status === '已处理' ? '#16a34a' : '#dc2626'};">${escapeHtml(status)}</span>
                        </div>
                        <div style="color:#64748b;">紧急度：${escapeHtml(urgency)} | ${escapeHtml(t.created_at || '')}</div>
                    </div>
                `;
            }
            searchResultDiv.innerHTML = html;
        }
    } catch (err) {
        searchResultDiv.innerHTML = '<span style="color: #dc2626;">查询失败，请检查网络连接</span>';
    }
}

// ======================== 发送按钮状态 ========================
function updateSendButton() {
    const hasText = chatInput.value.trim().length > 0;
    const hasFile = currentFile !== null;
    sendBtn.disabled = !(hasText || hasFile);
}

// ======================== 核心发送逻辑 ========================
async function sendMessage() {
    const userText = chatInput.value.trim();
    if (!userText && !currentFile) return;

    const fileToSend = currentFile;
    let displayText = userText;
    if (fileToSend) displayText += `\n[附件: ${fileToSend.name}]`;

    addMessage('user', displayText);
    conversationHistory.push({ role: 'user', content: userText });

    chatInput.value = '';
    if (fileToSend) {
        currentFile = null;
        chatFile.value = '';
        filePreview.innerHTML = '';
    }
    updateSendButton();
    showThinkingIndicator();

    try {
        const formData = new FormData();
        formData.append('session_id', sessionId);
        formData.append('message', userText);
        formData.append('history', JSON.stringify(conversationHistory.slice(-10)));
        if (fileToSend) formData.append('image', fileToSend);

        const res = await fetch(`${API_BASE}/chat`, { method: 'POST', body: formData });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);

        const data = await res.json();
        hideThinkingIndicator();

        const assistantFullReply = data.reply || '抱歉，未获得有效回复。';
        const extra = data.ticket_created ? { ticket_id: data.ticket_id } : {};

        const { messageDiv, replyText } = addAssistantMessageWithThinking(assistantFullReply, extra);
        isStreaming = true;
        await typeTextToReplyContainer(messageDiv, replyText, 15);
        isStreaming = false;

        conversationHistory.push({ role: 'assistant', content: assistantFullReply });
        chatMessages.scrollTop = chatMessages.scrollHeight;

    } catch (err) {
        hideThinkingIndicator();
        addMessage('assistant', '系统异常：服务暂时不可用，请稍后再试或联系人工客服。');
    } finally {
        updateSendButton();
        chatInput.focus();
    }
}

// ======================== 事件绑定 ========================
chatInput.addEventListener('input', updateSendButton);
updateSendButton();

fileLabel.addEventListener('click', () => chatFile.click());
chatFile.addEventListener('change', () => {
    const file = chatFile.files[0];
    if (!file) return;
    if (file.size > 50 * 1024 * 1024) {
        alert('文件大小不能超过 50MB');
        chatFile.value = '';
        return;
    }
    currentFile = file;
    const fileType = file.type.startsWith('video/') ? '[视频]' : '[图片]';
    filePreview.innerHTML = `${fileType} ${file.name}`;
    updateSendButton();
});

newChatBtn.addEventListener('click', () => {
    sessionId = 'session_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
    localStorage.setItem('chat_session_id', sessionId);
    conversationHistory = [];
    chatMessages.innerHTML = `
        <div class="message assistant">
            <div class="bubble">您好，新会话已建立。<br>请描述您的设备故障或上传相关凭证。</div>
        </div>`;
    updateSendButton();
});

backBtn.addEventListener('click', () => window.location.href = 'welcome.html');
userSearchBtn.addEventListener('click', searchUserTicket);
userSearchInput.addEventListener('keypress', (e) => { if (e.key === 'Enter') searchUserTicket(); });
sendBtn.addEventListener('click', sendMessage);
chatInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});
