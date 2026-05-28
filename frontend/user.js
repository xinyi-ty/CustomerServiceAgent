// ======================== DOM 元素 ========================
const chatMessages = document.getElementById('chatMessages');
const chatInput = document.getElementById('chatInput');
const sendBtn = document.getElementById('sendBtn');
const chatImage = document.getElementById('chatImage');
const fileLabel = document.getElementById('fileLabel');
const filePreview = document.getElementById('filePreview');
const newChatBtn = document.getElementById('newChatBtn');
const backBtn = document.getElementById('backToWelcome');

// 工单查询相关元素
const userSearchInput = document.getElementById('userSearchTicket');
const userSearchBtn = document.getElementById('userSearchBtn');
const searchResultDiv = document.getElementById('searchResult');

// 折叠相关元素
const collapseHeader = document.getElementById('collapseHeader');
const collapseContent = document.getElementById('collapseContent');
const collapseIcon = document.getElementById('collapseIcon');

// ======================== 状态管理 ========================
let sessionId = localStorage.getItem('chat_session_id');
if (!sessionId) {
    sessionId = generateSessionId();
    localStorage.setItem('chat_session_id', sessionId);
}
let conversationHistory = [];
let currentFile = null;
let isStreaming = false;

// ======================== 辅助函数 ========================
function generateSessionId() {
    return 'session_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
}

function escapeHtml(str) {
    if (!str) return '';
    return str.replace(/[&<>]/g, function(m) {
        if (m === '&') return '&amp;';
        if (m === '<') return '&lt;';
        if (m === '>') return '&gt;';
        return m;
    });
}

function parseThinkingReply(rawText) {
    const thinkRegex = /<think>([\s\S]*?)<\/think>/;
    const match = rawText.match(thinkRegex);
    if (match) {
        const thinking = match[1].trim();
        const reply = rawText.replace(thinkRegex, '').trim();
        return { thinking, reply };
    }
    return { thinking: null, reply: rawText };
}

function addMessage(role, content, extra = {}) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${role}`;
    let bubbleContent = `<div class="bubble">${escapeHtml(content)}`;
    if (extra.ticket_id) {
        bubbleContent += `<span class="ticket-badge">工单: ${extra.ticket_id}</span>`;
    }
    bubbleContent += `</div>`;
    messageDiv.innerHTML = bubbleContent;
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
                <div class="think-summary">🤔 思考过程</div>
                <div class="think-content" style="display: none;">${escapeHtml(thinking)}</div>
            </div>
        `;
    }
    bubbleHtml += `<div class="reply-content">${escapeHtml(reply)}</div>`;
    if (extra.ticket_id) {
        bubbleHtml += `<span class="ticket-badge">工单: ${extra.ticket_id}</span>`;
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
            summary.innerHTML = isHidden ? '🤔 思考过程 ▼' : '🤔 思考过程 ▶';
        });
        summary.innerHTML = '🤔 思考过程 ▶';
    }

    chatMessages.scrollTop = chatMessages.scrollHeight;
    return { messageDiv, replyText: reply };
}

async function typeTextToReplyContainer(messageDiv, text, speed = 20) {
    const replyContainer = messageDiv.querySelector('.reply-content');
    if (!replyContainer) return;
    replyContainer.innerHTML = '';
    for (let i = 0; i < text.length; i++) {
        if (!isStreaming) break;
        replyContainer.innerHTML += escapeHtml(text[i]);
        chatMessages.scrollTop = chatMessages.scrollHeight;
        await new Promise(resolve => setTimeout(resolve, speed));
    }
}

function showThinkingIndicator() {
    const thinkingDiv = document.createElement('div');
    thinkingDiv.className = 'message assistant';
    thinkingDiv.id = 'thinkingIndicator';
    thinkingDiv.innerHTML = `<div class="bubble" style="color:#6b7280;"><span>🤔 思考中</span><span style="margin-left:4px;">.</span><span>.</span><span>.</span></div>`;
    chatMessages.appendChild(thinkingDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    return thinkingDiv;
}
function hideThinkingIndicator() {
    const indicator = document.getElementById('thinkingIndicator');
    if (indicator) indicator.remove();
}

function attachTicketPreviewCard(messageDiv, previewData, previewId) {
    const bubble = messageDiv.querySelector('.bubble');
    if (!bubble) return;
    if (bubble.querySelector('.ticket-preview-card')) return;
    const card = document.createElement('div');
    card.className = 'ticket-preview-card';
    card.innerHTML = `
        <h4>📋 工单预览</h4>
        <div class="field"><strong>紧急度</strong> ${escapeHtml(previewData.urgency_level || '未知')}</div>
        <div class="field"><strong>问题类别</strong> ${escapeHtml(previewData.category || '未分类')}</div>
        <div class="field"><strong>提取信息</strong> <pre style="display:inline; font-size:12px;">${escapeHtml(JSON.stringify(previewData.extracted_data || {}, null, 2))}</pre></div>
        <div class="preview-buttons">
            <button class="cancel-create">取消</button>
            <button class="confirm-create">✅ 创建工单</button>
        </div>
    `;
    bubble.appendChild(card);

    card.querySelector('.cancel-create').addEventListener('click', () => {
        card.remove();
    });
    card.querySelector('.confirm-create').addEventListener('click', async () => {
        const confirmBtn = card.querySelector('.confirm-create');
        confirmBtn.disabled = true;
        confirmBtn.textContent = '创建中...';
        try {
            const formData = new FormData();
            formData.append('preview_id', previewId);
            formData.append('session_id', sessionId);
            const res = await fetch('http://localhost:8000/chat/create_ticket', {
                method: 'POST',
                body: formData
            });
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data = await res.json();
            addMessage('assistant', `✅ 工单已创建，编号：${data.ticket_id}`, { ticket_id: data.ticket_id });
            card.remove();
        } catch (err) {
            console.error(err);
            addMessage('assistant', '❌ 创建工单失败，请稍后重试');
            confirmBtn.disabled = false;
            confirmBtn.textContent = '✅ 创建工单';
        }
    });
}

// 工单查询功能
async function searchUserTicket() {
    const ticketId = userSearchInput.value.trim();
    if (!ticketId) {
        searchResultDiv.innerHTML = '<span style="color: #ef4444;">请输入工单号</span>';
        return;
    }
    searchResultDiv.innerHTML = '查询中...';
    try {
        const res = await fetch(`http://localhost:8000/history?ticket_id=${encodeURIComponent(ticketId)}`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        const tickets = data.tickets || [];
        if (tickets.length === 0) {
            searchResultDiv.innerHTML = '<span style="color: #f97316;">未找到工单，请核对工单号</span>';
        } else {
            let html = '';
            for (const t of tickets) {
                const urgency = t.agent_business_assessment?.urgency_level || '未知';
                const status = t.status || '未处理';
                const category = t.agent_business_assessment?.issue_category || '无分类';
                const createdAt = t.created_at || '未知时间';
                const replyPreview = (t.auto_reply_sent || '').substring(0, 150);
                html += `
                    <div style="background: #f1f5f9; border-radius: 16px; padding: 12px; margin-top: 12px; border-left: 4px solid #2563eb;">
                        <p><strong>工单号：</strong>${escapeHtml(t.ticket_id)}</p>
                        <p><strong>紧急度：</strong>${escapeHtml(urgency)} &nbsp;|&nbsp; <strong>类别：</strong>${escapeHtml(category)}</p>
                        <p><strong>状态：</strong>${escapeHtml(status)}</p>
                        <p><strong>创建时间：</strong>${escapeHtml(createdAt)}</p>
                        <details><summary style="cursor: pointer; color: #2563eb;">查看AI回复</summary><p style="white-space: pre-wrap; margin-top: 8px;">${escapeHtml(replyPreview)}</p></details>
                    </div>
                `;
            }
            searchResultDiv.innerHTML = html;
        }
    } catch (err) {
        console.error(err);
        searchResultDiv.innerHTML = '<span style="color: #ef4444;">查询失败，请稍后重试</span>';
    }
}

// ======================== 折叠功能 ========================
function initCollapse() {
    if (!collapseHeader || !collapseContent || !collapseIcon) return;
    const isCollapsed = localStorage.getItem('ticketSearchCollapsed') === 'true';
    if (isCollapsed) {
        collapseContent.classList.add('collapsed');
        collapseIcon.classList.add('collapsed');
    } else {
        collapseContent.classList.remove('collapsed');
        collapseIcon.classList.remove('collapsed');
    }
    collapseHeader.addEventListener('click', () => {
        const nowCollapsed = collapseContent.classList.contains('collapsed');
        if (nowCollapsed) {
            collapseContent.classList.remove('collapsed');
            collapseIcon.classList.remove('collapsed');
            localStorage.setItem('ticketSearchCollapsed', 'false');
        } else {
            collapseContent.classList.add('collapsed');
            collapseIcon.classList.add('collapsed');
            localStorage.setItem('ticketSearchCollapsed', 'true');
        }
    });
}

// ======================== 核心发送逻辑 ========================
async function sendMessageFixed() {
    const userText = chatInput.value.trim();
    if (!userText && !currentFile) {
        alert('请输入问题或上传图片/视频');
        return;
    }
    const messageText = userText;
    const fileToSend = currentFile;
    const fileName = fileToSend ? fileToSend.name : '';
    let displayText = messageText;
    if (fileToSend) displayText += `\n[已上传文件: ${fileName}]`;
    addMessage('user', displayText);
    conversationHistory.push({ role: 'user', content: messageText });

    chatInput.value = '';
    if (fileToSend) {
        currentFile = null;
        chatImage.value = '';
        filePreview.innerHTML = '';
    }

    sendBtn.disabled = true;
    const thinkingDiv = showThinkingIndicator();

    try {
        const formData = new FormData();
        formData.append('session_id', sessionId);
        formData.append('message', messageText);
        const recentHistory = conversationHistory.slice(-10);
        formData.append('history', JSON.stringify(recentHistory));
        if (fileToSend) formData.append('image', fileToSend);

        const res = await fetch('http://localhost:8000/chat', {
            method: 'POST',
            body: formData
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();

        hideThinkingIndicator();
        const assistantFullReply = data.reply || '抱歉，未获得有效回复。';
        const { messageDiv, replyText } = addAssistantMessageWithThinking(assistantFullReply, {});
        isStreaming = true;
        await typeTextToReplyContainer(messageDiv, replyText, 20);
        isStreaming = false;
        conversationHistory.push({ role: 'assistant', content: assistantFullReply });

        if (data.ticket_preview && data.preview_id) {
            attachTicketPreviewCard(messageDiv, data.ticket_preview, data.preview_id);
        }
        chatMessages.scrollTop = chatMessages.scrollHeight;
    } catch (err) {
        hideThinkingIndicator();
        console.error(err);
        addMessage('assistant', '❌ 服务暂时不可用，请稍后再试。');
        alert('连接后端失败: ' + err.message);
    } finally {
        sendBtn.disabled = false;
        chatInput.focus();
    }
}

// ======================== 文件上传 ========================
if (chatImage && fileLabel) {
    fileLabel.addEventListener('click', () => chatImage.click());
    chatImage.addEventListener('change', () => {
        const file = chatImage.files[0];
        if (!file) {
            currentFile = null;
            filePreview.innerHTML = '';
            return;
        }
        if (file.size > 50 * 1024 * 1024) {
            alert('文件不能超过50MB');
            chatImage.value = '';
            return;
        }
        currentFile = file;
        filePreview.innerHTML = `📎 已选择: ${file.name}`;
    });
}

// ======================== 新对话 ========================
function newChat() {
    sessionId = generateSessionId();
    localStorage.setItem('chat_session_id', sessionId);
    conversationHistory = [];
    chatMessages.innerHTML = '';
    const welcomeDiv = document.createElement('div');
    welcomeDiv.className = 'message assistant';
    welcomeDiv.innerHTML = `<div class="bubble">您好！我是智能客服助手 👋<br>您可以随时描述遇到的问题，也可以上传图片或视频。<br>我会根据您的需求生成工单或提供解决方案。</div>`;
    chatMessages.appendChild(welcomeDiv);
    chatInput.value = '';
    if (currentFile) {
        currentFile = null;
        chatImage.value = '';
        filePreview.innerHTML = '';
    }
}

// ======================== 事件绑定 ========================
if (sendBtn) sendBtn.addEventListener('click', sendMessageFixed);
if (newChatBtn) newChatBtn.addEventListener('click', newChat);
if (backBtn) backBtn.addEventListener('click', () => window.location.href = 'welcome.html');
if (userSearchBtn) userSearchBtn.addEventListener('click', searchUserTicket);
if (userSearchInput) userSearchInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') searchUserTicket();
});
chatInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessageFixed();
    }
});

// 初始化折叠
initCollapse();