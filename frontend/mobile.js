// ======================== Configuration ========================
var API_BASE = 'http://localhost:8000';

// ======================== DOM Elements ========================
// Tabs
var tabBtns = document.querySelectorAll('.tab-btn');
var tabChat = document.getElementById('tabChat');
var tabTickets = document.getElementById('tabTickets');

// Chat
var chatMessages = document.getElementById('chatMessages');
var chatInput = document.getElementById('chatInput');
var sendBtn = document.getElementById('sendBtn');
var chatFile = document.getElementById('chatFile');
var fileLabel = document.getElementById('fileLabel');
var filePreview = document.getElementById('filePreview');

// Tickets
var ticketSearchInput = document.getElementById('ticketSearchInput');
var ticketSearchBtn = document.getElementById('ticketSearchBtn');
var ticketList = document.getElementById('ticketList');
var ticketCount = document.getElementById('ticketCount');
var refreshTicketsBtn = document.getElementById('refreshTicketsBtn');

var toastEl = document.getElementById('toast');

// ======================== State ========================
var sessionId = localStorage.getItem('mobile_chat_session_id');
if (!sessionId) {
  sessionId = 'mobile_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
  localStorage.setItem('mobile_chat_session_id', sessionId);
}
var conversationHistory = [];
var currentFile = null;
var isStreaming = false;
var toastTimer = null;

// ======================== Toast ========================
function showToast(msg, duration) {
  if (!msg) return;
  var dur = duration || 2500;
  toastEl.textContent = msg;
  toastEl.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(function () { toastEl.classList.remove('show'); }, dur);
}

// ======================== Tab Switching ========================
for (let i = 0; i < tabBtns.length; i++) {
  tabBtns[i].addEventListener('click', function () {
    for (let j = 0; j < tabBtns.length; j++) {
      tabBtns[j].classList.remove('active');
    }
    this.classList.add('active');
    var tab = this.getAttribute('data-tab');
    tabChat.classList.toggle('active', tab === 'chat');
    tabTickets.classList.toggle('active', tab === 'tickets');
    if (tab === 'tickets') {
      loadTickets();
    }
  });
}

// ======================== Utility Functions ========================
function escapeHtml(str) {
  if (!str && str !== 0) return '';
  var div = document.createElement('div');
  div.textContent = String(str);
  return div.innerHTML;
}

function parseThinkingReply(rawText) {
  if (!rawText) return { thinking: null, reply: '' };
  var thinkRegex = /<think>([\s\S]*?)<\/think>/;
  var match = rawText.match(thinkRegex);
  if (match) {
    return { thinking: match[1].trim(), reply: rawText.replace(thinkRegex, '').trim() };
  }
  return { thinking: null, reply: rawText };
}

// ======================== File Upload ========================
fileLabel.addEventListener('click', function () { chatFile.click(); });

chatFile.addEventListener('change', function () {
  var file = chatFile.files[0];
  if (!file) return;
  if (file.size > 50 * 1024 * 1024) {
    showToast('文件大小不能超过 50MB');
    chatFile.value = '';
    return;
  }
  currentFile = file;
  var fileType = file.type.startsWith('video/') ? '视频' : '图片';
  filePreview.innerHTML =
    '<span class="tag">' + fileType + '</span>' +
    '<span class="fname">' + escapeHtml(file.name) + '</span>' +
    '<button class="fclear" id="fileClearBtn">×</button>';
  document.getElementById('fileClearBtn').addEventListener('click', function (e) {
    e.stopPropagation();
    clearFileInput();
  });
  updateSendButton();
});

function clearFileInput() {
  currentFile = null;
  chatFile.value = '';
  filePreview.innerHTML = '';
  updateSendButton();
}

// ======================== Send Button State ========================
function updateSendButton() {
  var hasText = chatInput.value.trim().length > 0;
  var hasFile = currentFile !== null;
  sendBtn.disabled = !(hasText || hasFile);
}

chatInput.addEventListener('input', updateSendButton);
updateSendButton();

// ======================== Message Rendering ========================
function addMessage(role, content, extra) {
  extra = extra || {};
  var messageDiv = document.createElement('div');
  messageDiv.className = 'message ' + role;

  var bubbleHtml = '<div class="bubble">' + escapeHtml(content);
  if (extra.fileName) {
    bubbleHtml += '<span class="file-attach">' + escapeHtml(extra.fileName) + '</span>';
  }
  if (extra.ticket_id) {
    var urg = (extra.urgency_level || '').toLowerCase();
    var urgLabel = urg === 'high' ? '紧急' : urg === 'medium' ? '中等' : '普通';
    var warrantyStatus = extra.warranty_status || '';
    let warrantyLabel, warrantyClass;
    if (warrantyStatus) {
      var ws = warrantyStatus.toLowerCase();
      warrantyLabel = ws === 'in_warranty' ? '在保' : ws === 'out_of_warranty' ? '过保' : '待核验';
      warrantyClass = ws === 'in_warranty' ? 'in' : ws === 'out_of_warranty' ? 'out' : 'unknown';
    }
    bubbleHtml += '<div class="ticket-badge">' +
      '<span class="badge-dot"></span>' +
      '<span class="badge-text">已创建工单</span>' +
      '<span class="badge-id">' + escapeHtml(extra.ticket_id) + '</span>';
    if (warrantyStatus) {
      bubbleHtml += '<span class="badge-warranty ' + warrantyClass + '">' + warrantyLabel + '</span>';
    }
    bubbleHtml += '<span class="badge-urg ' + urg + '"><span class="urg-dot"></span>' + urgLabel + '</span>' +
      '</div>';
  }
  bubbleHtml += '</div>';

  messageDiv.innerHTML = bubbleHtml;
  chatMessages.appendChild(messageDiv);
  chatMessages.scrollTop = chatMessages.scrollHeight;
  return messageDiv;
}

function addAssistantMessageWithThinking(fullRawText, extra) {
  extra = extra || {};
  var parsed = parseThinkingReply(fullRawText);
  var thinking = parsed.thinking;
  var reply = parsed.reply;

  var messageDiv = document.createElement('div');
  messageDiv.className = 'message assistant';

  var bubbleHtml = '<div class="bubble">';
  if (thinking) {
    bubbleHtml +=
      '<div class="think-container">' +
      '  <div class="think-summary">[ 展开 AI 推理分析过程 ]</div>' +
      '  <div class="think-content">' + escapeHtml(thinking) + '</div>' +
      '</div>';
  }
  bubbleHtml += '<div class="reply-content"></div>';

  if (extra.ticket_id) {
    var urg = (extra.urgency_level || '').toLowerCase();
    var urgLabel = urg === 'high' ? '紧急' : urg === 'medium' ? '中等' : '普通';
    var warrantyStatus = extra.warranty_status || '';
    let warrantyLabel, warrantyClass;
    if (warrantyStatus) {
      var ws = warrantyStatus.toLowerCase();
      warrantyLabel = ws === 'in_warranty' ? '在保' : ws === 'out_of_warranty' ? '过保' : '待核验';
      warrantyClass = ws === 'in_warranty' ? 'in' : ws === 'out_of_warranty' ? 'out' : 'unknown';
    }
    bubbleHtml += '<div class="ticket-badge">' +
      '<span class="badge-dot"></span>' +
      '<span class="badge-text">已创建工单</span>' +
      '<span class="badge-id">' + escapeHtml(extra.ticket_id) + '</span>';
    if (warrantyStatus) {
      bubbleHtml += '<span class="badge-warranty ' + warrantyClass + '">' + warrantyLabel + '</span>';
    }
    bubbleHtml += '<span class="badge-urg ' + urg + '"><span class="urg-dot"></span>' + urgLabel + '</span>' +
      '</div>';
  }
  bubbleHtml += '</div>';

  messageDiv.innerHTML = bubbleHtml;
  chatMessages.appendChild(messageDiv);

  // Bind think toggle
  var thinkContainer = messageDiv.querySelector('.think-container');
  if (thinkContainer) {
    var summary = thinkContainer.querySelector('.think-summary');
    var contentDiv = thinkContainer.querySelector('.think-content');
    summary.addEventListener('click', function () {
      var isHidden = contentDiv.style.display === 'none' || contentDiv.style.display === '';
      contentDiv.style.display = isHidden ? 'block' : 'none';
      summary.textContent = isHidden ? '[ 收起 AI 推理分析过程 ]' : '[ 展开 AI 推理分析过程 ]';
    });
  }

  chatMessages.scrollTop = chatMessages.scrollHeight;
  return { messageDiv: messageDiv, replyText: reply };
}

async function typeTextToReplyContainer(messageDiv, text, speed) {
  speed = speed || 12;
  var replyContainer = messageDiv.querySelector('.reply-content');
  if (!replyContainer) return;
  replyContainer.textContent = '';
  for (let i = 0; i < text.length; i++) {
    if (!isStreaming) break;
    replyContainer.textContent += text[i];
    chatMessages.scrollTop = chatMessages.scrollHeight;
    await new Promise(function (resolve) { setTimeout(resolve, speed); });
  }
}

function showThinkingIndicator() {
  var div = document.createElement('div');
  div.className = 'msg-thinking';
  div.id = 'thinkingIndicator';
  div.innerHTML = '<span class="spinner"></span><span class="txt" id="thinkText">正在分析您的问题...</span>';
  chatMessages.appendChild(div);
  chatMessages.scrollTop = chatMessages.scrollHeight;

  window._thinkTimer = setTimeout(function () {
    var el = document.getElementById('thinkText');
    if (el) el.textContent = '正在查询产品信息与处理方案...';
  }, 8000);
  return div;
}

function hideThinkingIndicator() {
  clearTimeout(window._thinkTimer);
  var el = document.getElementById('thinkingIndicator');
  if (el) el.remove();
}

// ======================== Core Send Logic ========================
async function sendMessage() {
  var userText = chatInput.value.trim();
  if (!userText && !currentFile) return;

  var fileToSend = currentFile;
  var displayText = userText;
  var extra = {};
  if (fileToSend) {
    extra.fileName = fileToSend.name;
  }

  addMessage('user', displayText, extra);
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
    var formData = new FormData();
    formData.append('session_id', sessionId);
    formData.append('message', userText);
    formData.append('history', JSON.stringify(conversationHistory.slice(-10)));
    if (fileToSend) formData.append('image', fileToSend);

    var res = await fetch(API_BASE + '/chat', { method: 'POST', body: formData });
    if (!res.ok) throw new Error('HTTP ' + res.status);

    var data = await res.json();
    hideThinkingIndicator();

    var assistantFullReply = data.reply || '抱歉，未获得有效回复。';

    var result = addAssistantMessageWithThinking(assistantFullReply);
    isStreaming = true;
    await typeTextToReplyContainer(result.messageDiv, result.replyText, 12);
    isStreaming = false;

    // After typewriter, add ticket badge if applicable
    if (data.ticket_created) {
      var urg = (data.urgency_level || '').toLowerCase();
      var urgLabel = urg === 'high' ? '紧急' : urg === 'medium' ? '中等' : '普通';
      var warrantyStatus = data.warranty_status || '';
      var badgeHtml = '<div style="margin-top:10px;font-size:11px;color:var(--sub);line-height:1.6;">';
      if (data.sn_code) {
        badgeHtml += 'SN: <strong style="color:var(--text);font-family:monospace;">' + escapeHtml(data.sn_code) + '</strong><br>';
      }
      if (data.ocr_text) {
        var ocrPreview = data.ocr_text.length > 60 ? data.ocr_text.slice(0, 60) + '...' : data.ocr_text;
        badgeHtml += 'OCR: ' + escapeHtml(ocrPreview) + '<br>';
      }
      badgeHtml += '</div>';

      badgeHtml += '<div class="ticket-badge">' +
        '<span class="badge-dot"></span>' +
        '<span class="badge-text">已创建工单</span>' +
        '<span class="badge-id">' + escapeHtml(data.ticket_id) + '</span>';
      if (warrantyStatus) {
        var wsLevel = warrantyStatus.toLowerCase();
        var wLabel = wsLevel === 'in_warranty' ? '在保' : wsLevel === 'out_of_warranty' ? '过保' : '待核验';
        badgeHtml += '<span class="badge-warranty ' + wsLevel.replace('_', '-') + '">' + wLabel + '</span>';
      }
      badgeHtml += '<span class="badge-urg ' + urg + '"><span class="urg-dot"></span>' + urgLabel + '</span></div>';
      var bubble = result.messageDiv.querySelector('.bubble');
      if (bubble) bubble.insertAdjacentHTML('beforeend', badgeHtml);
    }

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

// ======================== Chat Event Bindings ========================
sendBtn.addEventListener('click', sendMessage);
chatInput.addEventListener('keydown', function (e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});

// ======================== Ticket Search & List ========================
function renderTickets(tickets) {
  if (!tickets || tickets.length === 0) {
    ticketList.innerHTML =
      '<div class="empty-state">' +
      '  <div class="icon-box"><svg viewBox="0 0 24 24"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg></div>' +
      '  <div class="main-msg">暂无工单记录</div>' +
      '  <div class="sub-msg">提交客诉后，工单将显示在这里</div>' +
      '</div>';
    ticketCount.textContent = '';
    return;
  }

  ticketCount.textContent = '共 ' + tickets.length + ' 条';

  var html = '';
  for (let i = 0; i < tickets.length; i++) {
    var t = tickets[i];
    var assessment = t.agent_business_assessment || {};
    var extracted = t.extracted_data || {};
    var urgency = (assessment.urgency_level || 'low').toLowerCase();
    var status = t.status || '未处理';
    var isDone = status === '已处理' || status === '已解决';
    var warrantyStatus = assessment.warranty_status || '';
    var urgencyLabel = urgency === 'high' ? '紧急' : urgency === 'medium' ? '中等' : '普通';
    var statusLabel = isDone ? '已处理' : status;
    var created = t.created_at || '';
    var createdShort = created.length > 16 ? created.slice(0, 16) : created;

    // Warranty badge HTML
    var warrantyHtml = '';
    if (warrantyStatus) {
      var ws = warrantyStatus.toLowerCase();
      var wLabel = ws === 'in_warranty' ? '在保' : ws === 'out_of_warranty' ? '过保' : '待核验';
      var wClass = ws === 'in_warranty' ? 'in' : ws === 'out_of_warranty' ? 'out' : 'unknown';
      warrantyHtml = '<span class="warranty-badge-mobile ' + wClass + '">' + wLabel + '</span>';
    }

    // Evidence count
    var evCount = Array.isArray(extracted.evidence_images) ? extracted.evidence_images.length : 0;
    var evHtml = evCount > 0 ? '<span style="font-size:11px;color:var(--sub);">' + evCount + ' 个附件</span>' : '';

    // Detail rows
    var orderId = extracted.order_id || '--';
    var modelNum = extracted.model_number || '--';
    var batchCode = extracted.batch_code || '--';
    var snCode = extracted.sn_code || '--';
    var issueCategory = assessment.issue_category || '--';
    var businessImpact = assessment.business_impact || '--';
    var routingDecision = t.routing_decision || '--';
    var replyPreview = t.auto_reply_sent || '';
    var replyTruncated = replyPreview.length > 200 ? replyPreview.slice(0, 200) + '...' : replyPreview;

    html += '<div class="ticket-item" data-id="' + escapeHtml(t.ticket_id || '') + '">';
    html += '  <div class="ticket-header">';
    html += '    <span class="ticket-id">' + escapeHtml(t.ticket_id || '--') + '</span>';
    html += '    <span class="ticket-meta-tags">';
    html += '      <span class="urgency-dot ' + urgency + '"></span>';
    html += '      <span class="urgency-label ' + urgency + '">' + urgencyLabel + '</span>';
    html += '      <span class="status-badge ' + (isDone ? 'done' : 'pending') + '">' + escapeHtml(statusLabel) + '</span>';
    html += '      ' + warrantyHtml;
    html += '    </span>';
    html += '  </div>';
    html += '  <div class="ticket-meta-line">' + createdShort + ' · ' + issueCategory + ' ' + evHtml + '</div>';

    // Expandable detail
    html += '  <div class="ticket-detail">';
    html += '    <div class="detail-row"><span class="detail-label">订单号</span><span class="detail-value">' + escapeHtml(orderId) + '</span></div>';
    html += '    <div class="detail-row"><span class="detail-label">型号</span><span class="detail-value">' + escapeHtml(modelNum) + '</span></div>';
    html += '    <div class="detail-row"><span class="detail-label">批次</span><span class="detail-value">' + escapeHtml(batchCode) + '</span></div>';
    html += '    <div class="detail-row"><span class="detail-label">SN码</span><span class="detail-value">' + escapeHtml(snCode) + '</span></div>';
    html += '    <div class="detail-row"><span class="detail-label">影响</span><span class="detail-value">' + escapeHtml(businessImpact) + '</span></div>';
    html += '    <div class="detail-row"><span class="detail-label">路由</span><span class="detail-value">' + escapeHtml(routingDecision) + '</span></div>';
    if (replyTruncated) {
      html += '    <div class="detail-reply">' + escapeHtml(replyTruncated) + '</div>';
    }
    html += '  </div>';

    html += '</div>';
  }

  ticketList.innerHTML = html;

  // Bind expand toggle
  var items = ticketList.querySelectorAll('.ticket-item');
  for (let i = 0; i < items.length; i++) {
    items[i].addEventListener('click', function () {
      this.classList.toggle('expanded');
    });
  }
}

async function searchTicket() {
  var ticketId = ticketSearchInput.value.trim();
  if (!ticketId) {
    showToast('请输入工单号');
    return;
  }
  try {
    var res = await fetch(API_BASE + '/history?ticket_id=' + encodeURIComponent(ticketId));
    if (!res.ok) throw new Error('HTTP ' + res.status);
    var result = await res.json();
    var tickets = result.tickets || [];
    if (tickets.length === 0) {
      showToast('未找到工单：' + ticketId);
      return;
    }
    renderTickets(tickets);
    // Highlight matched
    var idEls = document.querySelectorAll('.ticket-id');
    for (let k = 0; k < idEls.length; k++) {
      if (idEls[k].textContent.indexOf(ticketId) !== -1) {
        idEls[k].style.color = '#2563eb';
        idEls[k].style.fontWeight = '800';
      }
    }
  } catch (err) {
    showToast('查询失败，请检查网络');
  }
}

async function loadTickets() {
  try {
    // 仅获取前台工单（低紧急度），客户不应看到管理者工单
    var res = await fetch(API_BASE + '/history?role=frontline');
    if (!res.ok) throw new Error('HTTP ' + res.status);
    var result = await res.json();
    renderTickets(result.tickets || []);
  } catch (err) {
    ticketList.innerHTML =
      '<div class="empty-state">' +
      '  <div class="icon-box"><svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg></div>' +
      '  <div class="main-msg">加载失败</div>' +
      '  <div class="sub-msg">请确保后端服务运行中</div>' +
      '</div>';
    ticketCount.textContent = '';
  }
}

// ======================== Ticket Event Bindings ========================
ticketSearchBtn.addEventListener('click', searchTicket);
ticketSearchInput.addEventListener('keypress', function (e) {
  if (e.key === 'Enter') searchTicket();
});
refreshTicketsBtn.addEventListener('click', loadTickets);

// ======================== Init ========================
document.addEventListener('DOMContentLoaded', function () {
  loadTickets();
  chatInput.focus();
});
