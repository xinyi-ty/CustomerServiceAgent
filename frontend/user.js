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
let isStreaming = false;  // 防止重复打字

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

// 添加消息到界面（非打字机模式，用于用户消息）
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

// 打字机效果：将内容逐字添加到指定元素中
async function typeText(element, text, speed = 20) {
    if (!element) return;
    const bubble = element.querySelector('.bubble');
    if (!bubble) return;
    bubble.innerHTML = ''; // 清空
    for (let i = 0; i < text.length; i++) {
        if (!isStreaming) break; // 如果被中断则停止
        bubble.innerHTML += escapeHtml(text[i]);
        chatMessages.scrollTop = chatMessages.scrollHeight;
        await new Promise(resolve => setTimeout(resolve, speed));
    }
}

// 显示思考链提示（气泡内显示“思考中...”）
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

// 核心发送逻辑（带思考链 + 逐字输出）
async function sendMessageFixed() {
    const userText = chatInput.value.trim();
    if (!userText && !currentFile) {
        alert('请输入问题或上传图片/视频');
        return;
    }

    // 保存当前消息和文件
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

    // 禁用发送按钮，显示思考指示器
    sendBtn.disabled = true;
    const thinkingDiv = showThinkingIndicator();

    try {
        // 准备请求数据
        const formData = new FormData();
        formData.append('session_id', sessionId);
        formData.append('message', messageText);
        const recentHistory = conversationHistory.slice(-10);
        formData.append('history', JSON.stringify(recentHistory));
        if (fileToSend) {
            formData.append('image', fileToSend);
        }

        // 发起请求
        const res = await fetch('http://localhost:8000/chat', {
            method: 'POST',
            body: formData
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();

        // 隐藏思考指示器
        hideThinkingIndicator();

        // 获取助手的回复内容
        let assistantReply = data.reply || '抱歉，未获得有效回复。';

        // 创建新的助手消息气泡（空内容，准备打字）
        const assistantMessageDiv = document.createElement('div');
        assistantMessageDiv.className = 'message assistant';
        assistantMessageDiv.innerHTML = `<div class="bubble"></div>`;
        chatMessages.appendChild(assistantMessageDiv);
        chatMessages.scrollTop = chatMessages.scrollHeight;

        // 开始打字机效果（速度 20ms/字）
        isStreaming = true;
        await typeText(assistantMessageDiv, assistantReply, 20);
        isStreaming = false;

        // 保存对话历史
        conversationHistory.push({ role: 'assistant', content: assistantReply });

        // 如果有工单号，额外显示提示
        if (data.ticket_id) {
            const ticketDiv = document.createElement('div');
            ticketDiv.className = 'message assistant';
            ticketDiv.innerHTML = `<div class="bubble">✅ 已为您生成工单：${escapeHtml(data.ticket_id)}</div>`;
            chatMessages.appendChild(ticketDiv);
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

// 文件上传预览逻辑不变
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

// 新对话
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

// 绑定事件
if (sendBtn) sendBtn.addEventListener('click', sendMessageFixed);
if (newChatBtn) newChatBtn.addEventListener('click', newChat);
if (backBtn) backBtn.addEventListener('click', () => window.location.href = 'welcome.html');

// 回车发送
chatInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessageFixed();
    }
});