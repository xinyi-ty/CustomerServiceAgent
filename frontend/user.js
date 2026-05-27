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

// 存储对话历史（用于发送给后端）
let conversationHistory = [];

// 当前选中的图片/视频文件
let currentFile = null;

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

// 添加消息到界面
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
    // 滚动到底部
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// 显示“正在输入”动画
function showTyping() {
    const typingDiv = document.createElement('div');
    typingDiv.className = 'message assistant';
    typingDiv.id = 'typingIndicator';
    typingDiv.innerHTML = `<div class="bubble typing"><span></span><span></span><span></span></div>`;
    chatMessages.appendChild(typingDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function hideTyping() {
    const indicator = document.getElementById('typingIndicator');
    if (indicator) indicator.remove();
}

// 发送消息到后端
async function sendMessageToBackend(userMessage, file) {
    const formData = new FormData();
    formData.append('session_id', sessionId);
    formData.append('message', userMessage);
    // 将历史消息（最近10条）也传给后端，帮助上下文理解
    const recentHistory = conversationHistory.slice(-10);
    formData.append('history', JSON.stringify(recentHistory));
    if (file) {
        formData.append('image', file);
    }

    const response = await fetch('http://localhost:8000/chat', {
        method: 'POST',
        body: formData
    });
    if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
    }
    return await response.json();
}

// 核心发送逻辑
async function sendMessage() {
    const userText = chatInput.value.trim();
    if (!userText && !currentFile) {
        alert('请输入问题或上传图片/视频');
        return;
    }

    // 1. 显示用户消息
    let displayText = userText;
    if (currentFile) {
        displayText += `\n[已上传文件: ${currentFile.name}]`;
    }
    addMessage('user', displayText);
    // 保存到历史
    conversationHistory.push({ role: 'user', content: userText });

    // 2. 清空输入框和文件预览
    chatInput.value = '';
    if (currentFile) {
        currentFile = null;
        chatImage.value = '';
        filePreview.innerHTML = '';
    }

    // 3. 调用后端
    sendBtn.disabled = true;
    showTyping();
    try {
        const data = await sendMessageToBackend(userText, currentFile); // 注意 currentFile 已清空？上面已清空，需要在调用前保存
        // 修正：应该在清空前保存文件引用
        // 重新获取文件引用（因为上面清空了，需要提前保存）
    } catch (err) {
        hideTyping();
        alert('发送失败: ' + err.message);
        sendBtn.disabled = false;
        return;
    }

    // 由于上面逻辑有瑕疵，重新组织：先保存文件引用，再清空
}

// 正确的发送实现（修复上述问题）
async function sendMessageFixed() {
    const userText = chatInput.value.trim();
    if (!userText && !currentFile) {
        alert('请输入问题或上传图片/视频');
        return;
    }

    // 保存当前文件和文本
    const messageText = userText;
    const fileToSend = currentFile;
    const fileName = fileToSend ? fileToSend.name : '';

    // 显示用户消息
    let displayText = messageText;
    if (fileToSend) {
        displayText += `\n[已上传文件: ${fileName}]`;
    }
    addMessage('user', displayText);
    // 保存历史
    conversationHistory.push({ role: 'user', content: messageText });

    // 清空输入框和文件预览
    chatInput.value = '';
    if (fileToSend) {
        currentFile = null;
        chatImage.value = '';
        filePreview.innerHTML = '';
    }

    sendBtn.disabled = true;
    showTyping();

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

        hideTyping();

        // 显示助手回复
        let assistantReply = data.reply || '抱歉，未获得有效回复。';
        addMessage('assistant', assistantReply, { ticket_id: data.ticket_id });
        // 保存历史
        conversationHistory.push({ role: 'assistant', content: assistantReply });

        // 如果后端生成了工单，可以额外提示
        if (data.ticket_id) {
            addMessage('assistant', `✅ 已为您生成工单：${data.ticket_id}，请妥善保管。`, {});
        }
    } catch (err) {
        hideTyping();
        console.error(err);
        addMessage('assistant', '抱歉，服务暂时不可用，请稍后再试。');
        alert('连接后端失败: ' + err.message);
    } finally {
        sendBtn.disabled = false;
        chatInput.focus();
    }
}

// 文件上传预览
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

// 新对话：重置 session 和历史
function newChat() {
    sessionId = generateSessionId();
    localStorage.setItem('chat_session_id', sessionId);
    conversationHistory = [];
    // 清空聊天区域，保留欢迎消息
    chatMessages.innerHTML = '';
    const welcomeDiv = document.createElement('div');
    welcomeDiv.className = 'message assistant';
    welcomeDiv.innerHTML = `<div class="bubble">您好！我是智能客服助手 👋<br>您可以随时描述遇到的问题，也可以上传图片或视频。<br>我会根据您的需求生成工单或提供解决方案。</div>`;
    chatMessages.appendChild(welcomeDiv);
    // 清空文件和输入
    chatInput.value = '';
    if (currentFile) {
        currentFile = null;
        chatImage.value = '';
        filePreview.innerHTML = '';
    }
}

// 绑定事件
if (sendBtn) sendBtn.addEventListener('click', sendMessageFixed);
if (newChatBtn) newChatBtn.addEventListener('click', newChat);
if (backBtn) backBtn.addEventListener('click', () => window.location.href = 'welcome.html');

// 支持回车发送（Ctrl+Enter换行）
chatInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessageFixed();
    }
});