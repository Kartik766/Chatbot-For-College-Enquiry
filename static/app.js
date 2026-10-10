/**
 * app.js — RCPIT Chatbot Frontend
 *
 * Features:
 *  - Unique session ID per browser tab (no expiry on frontend)
 *  - Auto-grow textarea
 *  - Markdown-style formatting of bot responses
 *  - Quick suggestion buttons loaded from API
 *  - Typing indicator
 *  - Timestamps
 *  - Clear chat with confirmation
 *  - Mobile sidebar toggle
 */

/* ── Session ID — persists in sessionStorage (per tab) ── */
const SESSION_KEY = 'rcpit_session_id';
let sessionId = sessionStorage.getItem(SESSION_KEY);
if (!sessionId) {
  sessionId = 'rcpit_' + Date.now() + '_' + Math.random().toString(36).slice(2, 8);
  sessionStorage.setItem(SESSION_KEY, sessionId);
}

/* ── DOM refs ── */
const messagesEl  = document.getElementById('messages');
const inputEl     = document.getElementById('userInput');
const sendBtn     = document.getElementById('sendBtn');
const clearBtn    = document.getElementById('clearBtn');
const menuBtn     = document.getElementById('menuBtn');
const quickBtns   = document.getElementById('quickBtns');
const typingRow   = document.getElementById('typingRow');
const leftPanel   = document.querySelector('.left-panel');
const overlay     = document.getElementById('panelOverlay');

/* ══════════════════════════════════════════════════════
   UTILITIES
   ══════════════════════════════════════════════════════ */

function now() {
  return new Date().toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' });
}

/**
 * Lightweight markdown → HTML conversion for bot messages.
 * Handles: **bold**, *italic*, bullet lists, line breaks, ---
 */
function escapeHtml(s) {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function formatBotText(text) {
  return escapeHtml(text)
    // Code inline
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    // Bold
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    // Italic with *
    .replace(/\*([^*\n]+)\*/g, '<em>$1</em>')
    // Horizontal rule
    .replace(/^---+$/gm, '<hr/>')
    // Bullet lists — lines starting with - or •
    .replace(/^[\-•]\s+(.+)$/gm, '<li>$1</li>')
    .replace(/(<li>.*<\/li>)/s, '<ul>$1</ul>')
    // Line breaks → <br>
    .replace(/\n\n/g, '</p><p>')
    .replace(/\n/g, '<br/>')
    // Wrap in paragraph
    .replace(/^(.+)$/, (m) => m.startsWith('<') ? m : `<p>${m}</p>`);
}

/* ══════════════════════════════════════════════════════
   RENDER MESSAGES
   ══════════════════════════════════════════════════════ */

function renderMessage(text, role, isError = false, sources = []) {
  const row = document.createElement('div');
  row.className = `msg-row ${role}`;

  const avatar = document.createElement('div');
  avatar.className = `msg-avatar ${role}`;
  avatar.textContent = role === 'bot' ? '🎓' : 'U';

  const content = document.createElement('div');
  content.className = 'msg-content';

  const bubble = document.createElement('div');
  bubble.className = `msg-bubble ${role}${isError ? ' error' : ''}`;

  if (role === 'bot') {
    bubble.innerHTML = formatBotText(text);
  } else {
    bubble.textContent = text;
  }

  const time = document.createElement('div');
  time.className = 'msg-time';
  time.textContent = now();

  content.appendChild(bubble);
  if (role === 'bot' && sources.length) {
    const box = document.createElement('div');
    box.className = 'sources';
    const label = document.createElement('span');
    label.className = 'sources-label';
    label.textContent = 'Sources';
    box.appendChild(label);
    sources.forEach(s => {
      const el = document.createElement(s.url ? 'a' : 'span');
      el.className = 'source-chip';
      el.textContent = `${s.title} · ${s.pages}`;
      if (s.url) { el.href = s.url; el.target = '_blank'; el.rel = 'noopener'; }
      el.title = s.url || s.title;
      box.appendChild(el);
    });
    content.appendChild(box);
  }
  content.appendChild(time);
  row.appendChild(avatar);
  row.appendChild(content);
  messagesEl.appendChild(row);
  scrollToBottom();
  return row;
}

function scrollToBottom() {
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

/* ══════════════════════════════════════════════════════
   WELCOME SCREEN
   ══════════════════════════════════════════════════════ */

function renderWelcome() {
  const card = document.createElement('div');
  card.className = 'welcome-card';
  card.id = 'welcomeCard';
  card.innerHTML = `
    <div class="wc-icon">🎓</div>
    <div class="wc-title">Welcome to RCPIT Enquiry Assistant</div>
    <div class="wc-sub">
      I'm here to help you with everything about<br/>
      <strong>R. C. Patel Institute of Technology, Shirpur</strong>.<br/>
      Ask me about admissions, fees, courses, placements, and more!
    </div>
    <div class="welcome-chips">
      <span class="chip" data-q="What courses does RCPIT offer?">📚 Courses</span>
      <span class="chip" data-q="What is the fee structure for 2025-26?">💰 Fees</span>
      <span class="chip" data-q="Tell me about placements at RCPIT">💼 Placements</span>
      <span class="chip" data-q="How do I apply for admission?">📋 Admissions</span>
      <span class="chip" data-q="Is hostel available at RCPIT?">🏠 Hostel</span>
      <span class="chip" data-q="What student clubs are available?">🎯 Clubs</span>
    </div>
  `;

  // Chip clicks
  card.querySelectorAll('.chip').forEach(chip => {
    chip.addEventListener('click', () => {
      const q = chip.dataset.q;
      removeWelcome();
      sendUserMessage(q);
    });
  });

  messagesEl.appendChild(card);
}

function removeWelcome() {
  document.getElementById('welcomeCard')?.remove();
}

/* ══════════════════════════════════════════════════════
   SEND MESSAGE
   ══════════════════════════════════════════════════════ */

async function sendUserMessage(text) {
  if (!text || !text.trim()) return;

  removeWelcome();
  renderMessage(text, 'user');
  inputEl.value = '';
  autoResize();

  sendBtn.disabled = true;
  inputEl.disabled = true;
  typingRow.style.display = 'flex';
  scrollToBottom();

  try {
    const res = await fetch('/api/chat', {
      method : 'POST',
      headers: { 'Content-Type': 'application/json' },
      body   : JSON.stringify({ sessionId, message: text.trim() }),
    });

    const data = await res.json();
    typingRow.style.display = 'none';

    if (res.ok && data.reply) {
      renderMessage(data.reply, 'bot', false, data.sources || []);
    } else {
      renderMessage(data.error || 'Something went wrong. Please try again.', 'bot', true);
    }
  } catch {
    typingRow.style.display = 'none';
    renderMessage('Network error. Please check your connection and try again.', 'bot', true);
  } finally {
    sendBtn.disabled = false;
    inputEl.disabled = false;
    inputEl.focus();
  }
}

/* ── Send button ── */
sendBtn.addEventListener('click', () => sendUserMessage(inputEl.value));

/* ── Enter key (Shift+Enter for new line) ── */
inputEl.addEventListener('keydown', e => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendUserMessage(inputEl.value);
  }
});

/* ══════════════════════════════════════════════════════
   AUTO-RESIZE TEXTAREA
   ══════════════════════════════════════════════════════ */

function autoResize() {
  inputEl.style.height = 'auto';
  inputEl.style.height = Math.min(inputEl.scrollHeight, 120) + 'px';
}
inputEl.addEventListener('input', autoResize);

/* ══════════════════════════════════════════════════════
   CLEAR CHAT
   ══════════════════════════════════════════════════════ */

clearBtn.addEventListener('click', async () => {
  if (!confirm('Clear the chat? This will start a fresh conversation.')) return;

  // Tell server to clear session
  fetch(`/api/chat/${sessionId}`, { method: 'DELETE' }).catch(() => {});

  // Reset session ID
  sessionId = 'rcpit_' + Date.now() + '_' + Math.random().toString(36).slice(2, 8);
  sessionStorage.setItem(SESSION_KEY, sessionId);

  // Clear UI
  messagesEl.innerHTML = '';
  renderWelcome();
});

/* ══════════════════════════════════════════════════════
   SIDEBAR TOGGLE (mobile)
   ══════════════════════════════════════════════════════ */

menuBtn.addEventListener('click', () => {
  leftPanel.classList.toggle('open');
  overlay.classList.toggle('open');
});
overlay.addEventListener('click', () => {
  leftPanel.classList.remove('open');
  overlay.classList.remove('open');
});

/* ══════════════════════════════════════════════════════
   LOAD QUICK SUGGESTIONS FROM API
   ══════════════════════════════════════════════════════ */

async function loadSuggestions() {
  try {
    const res  = await fetch('/api/suggestions');
    const data = await res.json();
    data.suggestions.forEach(s => {
      const btn = document.createElement('button');
      btn.className = 'quick-btn';
      btn.textContent = s;
      btn.addEventListener('click', () => {
        leftPanel.classList.remove('open');
        overlay.classList.remove('open');
        sendUserMessage(s.replace(/^[^\s]+\s/, '')); // strip the emoji
      });
      quickBtns.appendChild(btn);
    });
  } catch {
    // Fail silently — suggestions are optional
  }
}

/* ══════════════════════════════════════════════════════
   INIT
   ══════════════════════════════════════════════════════ */

renderWelcome();
loadSuggestions();
inputEl.focus();
