// ======================== DOM 元素 ========================
const chatMessages = document.getElementById('chatMessages');
const chatInput = document.getElementById('chatInput');
const sendBtn = document.getElementById('sendBtn');
const chatImage = document.getElementById('chatImage');
const fileLabel = document.getElementById('fileLabel');
const filePreview = document.getElementById('filePreview');
const newChatBtn = document.getElementById('newChatBtn');
const backBtn = document.getElementById('backToWelcome');

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

/**
 * 解析回复中的思考链
 * @param {string} rawText - 包含可能 <think>...</think> 的文本
 * @returns {object} { thinking: string|null, reply: string }
 */
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

// 普通添加消息（用户消息或简单提示）
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

// 带思考链的助手消息（折叠思考块 + 最终回复可打字）
function addAssistantMessageWithThinking(fullRawText, extra = {}) {
    const { thinking, reply } = parseThinkingReply(fullRawText);
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message assistant';

    let bubbleHtml = `<div class="bubble">`;
    // 如果有思考内容，添加折叠块
    if (thinking) {
        bubbleHtml += `
            <div class="think-container">
                <div class="think-summary">🤔 思考过程</div>
                <div class="think-content" style="display: none;">${escapeHtml(thinking)}</div>
            </div>
        `;
    }
    // 最终回复容器（用于打字机效果）
    bubbleHtml += `<div class="reply-content"></div>`;
    if (extra.ticket_id) {
        bubbleHtml += `<span class="ticket-badge">工单: ${extra.ticket_id}</span>`;
    }
    bubbleHtml += `</div>`;
    messageDiv.innerHTML = bubbleHtml;
    chatMessages.appendChild(messageDiv);

    // 绑定折叠事件
    const thinkContainer = messageDiv.querySelector('.think-container');
    if (thinkContainer) {
        const summary = thinkContainer.querySelector('.think-summary');
        const content = thinkContainer.querySelector('.think-content');
        summary.addEventListener('click', () => {
            const isHidden = content.style.display === 'none';
            content.style.display = isHidden ? 'block' : 'none';
            summary.innerHTML = isHidden ? '🤔 思考过程 ▼' : '🤔 思考过程 ▶';
        });
        // 初始状态为折叠
        summary.innerHTML = '🤔 思考过程 ▶';
    }

    chatMessages.scrollTop = chatMessages.scrollHeight;
    return { messageDiv, replyText: reply };
}

// 打字机效果：将文本逐字输出到指定的 .reply-content 容器
async function typeTextToReplyContainer(messageDiv, text, speed = 20) {
    const replyContainer = messageDiv.querySelector('.reply-content');
    if (!replyContainer) return;
    replyContainer.innerHTML = ''; // 清空
    for (let i = 0; i < text.length; i++) {
        if (!isStreaming) break;
        replyContainer.innerHTML += escapeHtml(text[i]);
        chatMessages.scrollTop = chatMessages.scrollHeight;
        await new Promise(resolve => setTimeout(resolve, speed));
    }
}

// 显示思考指示器（三点动画）
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

    // 显示用户消息
    let displayText = messageText;
    if (fileToSend) {
        displayText += `\n[已上传文件: ${fileName}]`;
    }
    addMessage('user', displayText);
    conversationHistory.push({ role: 'user', content: messageText });

    // 清空输入框和文件预览
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
        if (fileToSend) {
            formData.append('image', fileToSend);
        }

        const res = await fetch('http://localhost:8000/chat', {
            method: 'POST',
            body: formData
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();

        hideThinkingIndicator();

        let assistantFullReply = data.reply || '抱歉，未获得有效回复。';

        // 创建带思考链折叠的助手消息容器
        const { messageDiv, replyText } = addAssistantMessageWithThinking(assistantFullReply, { ticket_id: data.ticket_id });

        // 开始对最终回复进行打字机输出
        isStreaming = true;
        await typeTextToReplyContainer(messageDiv, replyText, 20);
        isStreaming = false;

        // 保存对话历史（保存原始完整回复，包含思考链，以便下次对话上下文）
        conversationHistory.push({ role: 'assistant', content: assistantFullReply });

        if (data.ticket_id) {
            // 额外显示工单生成提示（简单消息，无需打字）
            addMessage('assistant', `✅ 已为您生成工单：${data.ticket_id}`);
            conversationHistory.push({ role: 'assistant', content: `工单号: ${data.ticket_id}` });
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

chatInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessageFixed();
    }
});