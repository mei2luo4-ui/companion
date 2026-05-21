const BUILTIN_AVATAR = '/avatars/1f42a266ff2e5e663cc3a41dbe2d827b.png';

function renderAvatar(val) {
  const src = val && val.startsWith('/') ? val : BUILTIN_AVATAR;
  return `<img src="${src}" alt="头像">`;
}

const EMOTION_COLORS = {
  '高兴': '#52c41a',
  '平静': '#40a9ff',
  '焦虑': '#faad14',
  '悲伤': '#9e7c84',
  '愤怒': '#ff4d4f',
  '疲惫': '#bfbfbf',
};

const TYPE_LABELS = {
  morning: '晨间问候',
  afternoon: '午后闲聊',
  activity: '活动邀请',
  evening: '睡前陪伴',
  emotion_care: '情绪关怀',
  lore: '她想告诉你',
};

const token = localStorage.getItem('token');
if (!token) location.href = 'login.html';

function authFetch(url, options = {}) {
  const headers = { 'Authorization': `Bearer ${token}`, ...(options.headers || {}) };
  if (options.body && !headers['Content-Type']) headers['Content-Type'] = 'application/json';
  return fetch(url, { ...options, headers }).then(res => {
    if (res.status === 401) { localStorage.removeItem('token'); location.href = 'login.html'; }
    return res;
  });
}

let profile = { name: '小暖', avatar_emoji: '🌸', personality: '温柔体贴', speaking_style: '亲密随意' };
let pendingEvents = [];
let currentEventId = null;
let isSending = false;

// ---- 初始化 ----
async function init() {
  await loadProfile();
  await loadHistory();
  startEventPolling();
}

async function loadProfile() {
  try {
    const res = await authFetch('/profile');
    profile = await res.json();
    updateProfileUI();
  } catch (e) {
    console.error('加载配置失败', e);
  }
}

function updateProfileUI() {
  const avatar = document.getElementById('topAvatar');
  const name = document.getElementById('topName');
  if (avatar) avatar.innerHTML = renderAvatar(profile.avatar_emoji);
  if (name) name.textContent = profile.name || '小暖';
  const replyBtn = document.getElementById('eventReplyBtn');
  if (replyBtn) replyBtn.textContent = `回复${profile.name}`;
}

async function loadHistory() {
  const container = document.getElementById('messages');
  if (!container) return;

  const cached = sessionStorage.getItem('chat_html');
  if (cached) {
    container.innerHTML = cached;
    scrollToBottom();
    return;
  }

  try {
    const res = await authFetch('/history?limit=30');
    const { messages } = await res.json();
    container.innerHTML = '';
    for (const msg of messages) {
      appendMessage(msg.role, msg.content, false);
    }
    scrollToBottom();
    if (messages.length === 0) showWelcome();
    sessionStorage.setItem('chat_html', container.innerHTML);
  } catch (e) {
    showWelcome();
  }
}

const WELCOME_MESSAGES = {
  '晓柔': '嗯，你来了。今天过得怎么样？',
  '星澜': '……是你。有什么事吗。',
  '糖糖': '哇你终于上线了！我刚才还在想你呢！',
  '沐雪': '茶刚泡好，坐吧。',
  '凌霄': '来了。说吧，什么事。',
  '知微': '你好。有什么想聊的，直接说。',
  '阿橘': '哎你来啦！正好，我刚捡到个好东西，等会儿给你看。',
  '诗韵': '你来了……我今天写了一句话，一直想找人说。',
};

function showWelcome() {
  const msg = WELCOME_MESSAGES[profile.name] || `你好呀！我是${profile.name}，很高兴认识你。`;
  appendMessage('assistant', msg, false);
  scrollToBottom();
}

// ---- 消息渲染 ----
function appendMessage(role, content, animate = true) {
  const container = document.getElementById('messages');
  if (!container) return null;

  const isUser = role === 'user';
  const div = document.createElement('div');
  div.className = `message ${isUser ? 'user' : 'bot'}${animate ? '' : ''}`;

  const avatarEl = document.createElement('div');
  avatarEl.className = 'msg-avatar';
  avatarEl.innerHTML = isUser ? '◎' : renderAvatar(profile.avatar_emoji);

  const bubble = document.createElement('div');
  bubble.className = 'bubble';
  bubble.textContent = content;

  div.appendChild(avatarEl);
  div.appendChild(bubble);
  container.appendChild(div);
  return bubble;
}

function appendTypingIndicator() {
  const container = document.getElementById('messages');
  if (!container) return null;

  const div = document.createElement('div');
  div.className = 'message bot';
  div.id = 'typingMsg';

  const avatarEl = document.createElement('div');
  avatarEl.className = 'msg-avatar';
  avatarEl.innerHTML = renderAvatar(profile.avatar_emoji);

  const bubble = document.createElement('div');
  bubble.className = 'bubble';
  bubble.innerHTML = '<div class="typing-indicator"><span></span><span></span><span></span></div>';

  div.appendChild(avatarEl);
  div.appendChild(bubble);
  container.appendChild(div);
  scrollToBottom();
  return div;
}

function removeTypingIndicator() {
  const el = document.getElementById('typingMsg');
  if (el) el.remove();
}

function scrollToBottom() {
  window.scrollTo(0, document.body.scrollHeight);
}

// ---- 发送消息 ----
async function sendMessage() {
  if (isSending) return;
  const input = document.getElementById('inputBox');
  const text = input.value.trim();
  if (!text) return;

  isSending = true;
  input.value = '';
  input.style.height = 'auto';
  document.getElementById('sendBtn').disabled = true;

  appendMessage('user', text);
  scrollToBottom();

  const typingEl = appendTypingIndicator();
  let botBubble = null;
  let botText = '';

  try {
    const res = await authFetch('/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: text }),
    });

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    const processLines = (text) => {
      const lines = text.split('\n');
      for (const line of lines) {
        if (!line.startsWith('data: ')) continue;
        const data = line.slice(6).trim();
        if (!data || data === '[DONE]') continue;
        try {
          const parsed = JSON.parse(data);
          if (parsed.type === 'text') {
            if (!botBubble) {
              removeTypingIndicator();
              botBubble = appendMessage('assistant', '', true);
            }
            botText += parsed.content;
            botBubble.textContent = botText;
            scrollToBottom();
          } else if (parsed.type === 'emotion') {
            updateEmotionUI(parsed.data);
          }
        } catch (e) {
          // 忽略解析错误
        }
      }
    };

    while (true) {
      const { done, value } = await reader.read();
      if (done) {
        if (buffer) processLines(buffer);
        break;
      }
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop();
      processLines(lines.join('\n'));
    }
  } catch (e) {
    removeTypingIndicator();
    if (botText === '') {
      appendMessage('assistant', '网络好像出了点问题，稍后再试试？');
      scrollToBottom();
    }
  }

  isSending = false;
  document.getElementById('sendBtn').disabled = false;
  sessionStorage.setItem('chat_html', document.getElementById('messages').innerHTML);
  input.focus();
}

function updateEmotionUI(emotion) {
  const dot = document.getElementById('emotionDot');
  const label = document.getElementById('emotionLabel');
  if (!dot || !label) return;
  const color = EMOTION_COLORS[emotion.label] || '#40a9ff';
  dot.style.background = color;
  label.textContent = emotion.label;
}

// ---- 输入框自动高度 ----
function setupInput() {
  const input = document.getElementById('inputBox');
  const sendBtn = document.getElementById('sendBtn');
  if (!input || !sendBtn) return;

  input.addEventListener('input', () => {
    input.style.height = 'auto';
    input.style.height = Math.min(input.scrollHeight, 120) + 'px';
  });

  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });

  sendBtn.addEventListener('click', sendMessage);
}

// ---- 事件轮询 ----
function startEventPolling() {
  checkEvents();
  setInterval(checkEvents, 60000);
}

async function checkEvents() {
  try {
    const res = await authFetch('/events/pending');
    const { events } = await res.json();
    pendingEvents = events;
    const badge = document.getElementById('bellBadge');
    if (badge) {
      badge.classList.toggle('show', events.length > 0);
    }
  } catch (e) {
    // 静默失败
  }
}

function showNextEvent() {
  if (pendingEvents.length === 0) {
    showToast('暂时没有新消息');
    return;
  }
  const event = pendingEvents[0];
  currentEventId = event.id;

  const modal = document.getElementById('eventModal');
  const badge = document.getElementById('eventTypeBadge');
  const title = document.getElementById('eventTitle');
  const content = document.getElementById('eventContent');
  if (!modal) return;

  badge.textContent = TYPE_LABELS[event.type] || '通知';
  title.textContent = event.title;
  let displayContent = event.content;
  if (event.type === 'lore') {
    try { displayContent = JSON.parse(event.content).text; } catch {}
  }
  content.textContent = displayContent;
  modal.classList.remove('hidden');
}

async function dismissCurrentEvent() {
  if (currentEventId === null) return;
  await authFetch(`/events/${currentEventId}/dismiss`, { method: 'POST' });
  pendingEvents = pendingEvents.filter(e => e.id !== currentEventId);
  currentEventId = null;
  document.getElementById('eventModal').classList.add('hidden');
  checkEvents();
}

function replyToEvent() {
  const eventContent = document.getElementById('eventContent')?.textContent || '';
  dismissCurrentEvent();
  const input = document.getElementById('inputBox');
  if (input) {
    input.focus();
  }
}

function setupEventModal() {
  const bellBtn = document.getElementById('bellBtn');
  const replyBtn = document.getElementById('eventReplyBtn');
  const dismissBtn = document.getElementById('eventDismissBtn');
  const modal = document.getElementById('eventModal');

  if (bellBtn) bellBtn.addEventListener('click', showNextEvent);
  if (replyBtn) replyBtn.addEventListener('click', replyToEvent);
  if (dismissBtn) dismissBtn.addEventListener('click', dismissCurrentEvent);
  if (modal) {
    modal.addEventListener('click', (e) => {
      if (e.target === modal) dismissCurrentEvent();
    });
  }
}

// ---- Toast ----
function showToast(msg) {
  const toast = document.getElementById('toast');
  if (!toast) return;
  toast.textContent = msg;
  toast.classList.add('show');
  setTimeout(() => toast.classList.remove('show'), 2500);
}

// ---- 启动 ----
document.addEventListener('DOMContentLoaded', () => {
  init();
  setupInput();
  setupEventModal();
});
