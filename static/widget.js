(function () {
  const sid = 'w_' + Date.now() + Math.random().toString(36).slice(2, 7);
  const esc = s => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  const md = t => esc(t).replace(/\*\*([^*]+)\*\*/g, '<b>$1</b>')
    .replace(/^[-•*]\s+(.+)$/gm, '<li>$1</li>').replace(/((?:<li>.*<\/li>\n?)+)/g, '<ul>$1</ul>')
    .replace(/\n/g, '<br>').replace(/<br>(<\/?ul>)/g, '$1').replace(/(<\/ul>)<br>/g, '$1');
  document.body.insertAdjacentHTML('beforeend', `
  <button id="cb-launch" title="Chat with us" aria-label="Open chat">💬</button>
  <div id="cb-panel" role="dialog" aria-label="RCPIT chat">
    <div class="cb-head"><span style="font-size:26px">🎓</span><div><b>RCPIT Assistant</b>R. C. Patel Institute of Technology, Shirpur</div><button id="cb-close" aria-label="Close">✕</button></div>
    <div id="cb-msgs"></div>
    <div class="cb-in"><input id="cb-input" placeholder="Ask about admissions, fees, placements…" autocomplete="off"><button id="cb-send" aria-label="Send">➤</button></div>
    <div class="cb-foot">AI answers from the college website · confirm important details officially</div>
  </div>`);
  const $ = id => document.getElementById(id), panel = $('cb-panel'), msgs = $('cb-msgs'), input = $('cb-input');
  function add(text, cls, sources) {
    const d = document.createElement('div'); d.className = 'cb-m ' + cls;
    d.innerHTML = cls === 'user' ? esc(text) : md(text);
    if (sources && sources.length) {
      const b = document.createElement('div'); b.className = 'cb-src';
      sources.forEach(s => { const e = document.createElement(s.url ? 'a' : 'span');
        e.textContent = `${s.title.replace('Knowledge Base - ', '')} · ${s.pages}`;
        if (s.url) { e.href = s.url; e.target = '_blank'; e.rel = 'noopener'; } b.appendChild(e); });
      d.appendChild(b);
    }
    msgs.appendChild(d); msgs.scrollTop = msgs.scrollHeight; return d;
  }
  async function ask(q) {
    q = q.trim(); if (!q) return; input.value = ''; add(q, 'user');
    const wait = add('Typing…', 'bot');
    try {
      const r = await fetch('/api/chat', { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ sessionId: sid, message: q }) });
      const j = await r.json(); wait.remove();
      j.reply ? add(j.reply, 'bot', j.sources) : add(j.error || 'Something went wrong.', 'bot err');
    } catch { wait.remove(); add('Network error. Is the server running?', 'bot err'); }
  }
  async function welcome() {
    add('Hi! 👋 I can help with admissions, fees, branches, hostel and placements at RCPIT. What would you like to know?', 'bot');
    try {
      const j = await (await fetch('/api/suggestions')).json();
      const c = document.createElement('div'); c.className = 'cb-chips';
      j.suggestions.slice(0, 6).forEach(s => { const b = document.createElement('button');
        b.textContent = s; b.onclick = () => { c.remove(); ask(s.replace(/^\S+\s/, '')); }; c.appendChild(b); });
      msgs.appendChild(c);
    } catch {}
  }
  let started = false;
  const toggle = open => { panel.classList.toggle('open', open); $('cb-launch').textContent = open ? '✕' : '💬';
    if (open && !started) { started = true; welcome(); } if (open) input.focus(); };
  $('cb-launch').onclick = () => toggle(!panel.classList.contains('open'));
  $('cb-close').onclick = () => toggle(false);
  $('cb-send').onclick = () => ask(input.value);
  input.addEventListener('keydown', e => { if (e.key === 'Enter') ask(input.value); });
  document.addEventListener('keydown', e => { if (e.key === 'Escape') toggle(false); });
})();
