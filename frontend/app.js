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

let profile = { name: '晓柔', avatar_emoji: '/avatars/1f42a266ff2e5e663cc3a41dbe2d827b.png', personality: '温柔体贴', speaking_style: '温柔低语' };
let pendingEvents = [];
let currentEventId = null;
let isSending = false;

// ---- 初始化 ----
async function init() {
  await loadProfile();
  const reply = localStorage.getItem('moment_reply');
  await loadHistory(!reply);
  if (reply) {
    localStorage.removeItem('moment_reply');
    try {
      const { content } = JSON.parse(reply);
      isSending = true;
      document.getElementById('sendBtn').disabled = true;
      await streamBotReply(`（用户刚刚看了你发的一条动态："${content}"，请自然地主动和用户聊起这条动态，不要提及"用户"这个词）`, '');
      isSending = false;
      document.getElementById('sendBtn').disabled = false;
    } catch {}
  }
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
  if (name) name.textContent = profile.name;
  document.title = `${profile.name} · 新霓虹`;
  const replyBtn = document.getElementById('eventReplyBtn');
  if (replyBtn) replyBtn.textContent = `回复${profile.name}`;
}

async function loadHistory(allowWelcome = true) {
  const container = document.getElementById('messages');
  if (!container) return;

  const forceWelcome = sessionStorage.getItem('show_welcome');
  if (forceWelcome) sessionStorage.removeItem('show_welcome');

  try {
    const res = await authFetch('/history?limit=30');
    const { messages } = await res.json();
    container.innerHTML = '';
    for (const msg of messages) {
      appendMessage(msg.role, msg.content, false);
    }
    scrollToBottom();
    if (allowWelcome && (messages.length === 0 || forceWelcome)) showWelcome();
  } catch (e) {
    if (allowWelcome) showWelcome();
  }
}

const WELCOME_MESSAGES = {
  '晓柔': ['你来啦～今天过得怎么样？', '嗯，等你好一会儿了', '你终于上线了，我刚才还在想你', '今天还好吗？', '来了～有什么想说的吗'],
  '星澜': ['来了。', '嗯。', '有事吗。', '你今天来得挺早。', '……在呢。'],
  '糖糖': ['哇你来了！！我超想你的！', '终于等到你了啊！', '你来了你来了！今天发生好多事！', '哎哎哎你上线了！', '我刚才还在刷消息等你呢！'],
  '沐雪': ['你来了，正好有话想说', '等你好一会儿了～', '嗯，来了', '今天怎么样？', '你来了，我刚在想你'],
  '凌霄': ['来了，有事吗', '嗯，在呢', '说吧', '你今天来得挺准时', '有什么事直说'],
  '知微': ['你来了，最近怎么样', '在呢，有什么想聊的', '嗯，来了', '今天有什么事吗', '你好，我在'],
  '阿橘': ['你来啦！我刚才还在想你！', '哎终于等到你了！', '你上线了！我有话跟你说！', '来了来了！今天有好东西给你看！', '哎哎你来了！'],
  '诗韵': ['你来了～', '等你好久了', '你上线了，我刚在想你', '嗯，来了，今天怎么样', '你来了，我有话想说'],
};

function showWelcome() {
  const msgs = WELCOME_MESSAGES[profile.name];
  if (!msgs) return;
  const hint = msgs[Math.floor(Math.random() * msgs.length)];
  isSending = true;
  document.getElementById('sendBtn').disabled = true;
  streamBotReply(`（请以这句话的风格和内容主动开口，直接说这句话或非常接近的表达，不要解释，不要加前缀："${hint}"）`, '')
    .then(() => {
      isSending = false;
      document.getElementById('sendBtn').disabled = false;
    });
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
async function streamBotReply(message, displayMessage = undefined) {
  const typingEl = appendTypingIndicator();
  let botBubble = null;
  let botText = '';
  try {
    const body = { message };
    if (displayMessage !== undefined) body.display_message = displayMessage;
    const res = await authFetch('/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    const processLines = (chunk) => {
      const lines = chunk.split('\n');
      for (const line of lines) {
        if (!line.startsWith('data: ')) continue;
        const data = line.slice(6).trim();
        if (!data || data === '[DONE]') continue;
        try {
          const parsed = JSON.parse(data);
          if (parsed.type === 'text') {
            if (!botBubble) { removeTypingIndicator(); botBubble = appendMessage('assistant', '', true); }
            botText += parsed.content;
            botBubble.textContent = botText;
            scrollToBottom();
          } else if (parsed.type === 'emotion') {
            updateEmotionUI(parsed.data);
          }
        } catch {}
      }
    };
    while (true) {
      const { done, value } = await reader.read();
      if (done) { if (buffer) processLines(buffer); break; }
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop();
      processLines(lines.join('\n'));
    }
  } catch {
    removeTypingIndicator();
    if (botText === '') { appendMessage('assistant', '网络好像出了点问题，稍后再试试？'); scrollToBottom(); }
  }
}

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

  await streamBotReply(text);

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
