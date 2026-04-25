/* AI Chat assistant — auto-injects floating button + panel on every page.
   Sends current indices.json + rhymes.json as system prompt to Anthropic API.
   API key stored in localStorage (browser-only). */
(function () {
  if (window.__taichatLoaded) return;
  window.__taichatLoaded = true;

  const STORAGE_KEY = 'taichat_api_key';
  const MODEL = 'claude-sonnet-4-20250514';
  const MAX_TOKENS = 1000;
  const SYSTEM_PROMPT_PREFIX =
    '你是一個台股交易分析助手，以下是用戶的韻腳資料庫和歷史K線數據，請根據這些資料回答用戶問題。';

  function dataPath(file) {
    return location.pathname.includes('/pages/')
      ? '../data/' + file
      : 'data/' + file;
  }

  const css = `
    .aichat-fab {
      position: fixed; right: 20px; bottom: 20px; width: 52px; height: 52px;
      border-radius: 50%; background: #3b82f6; color: white; border: none;
      cursor: pointer; box-shadow: 0 4px 14px rgba(59,130,246,0.4);
      display: flex; align-items: center; justify-content: center;
      font-size: 22px; z-index: 9999; transition: transform 0.15s;
    }
    .aichat-fab:hover { transform: scale(1.06); }
    .aichat-panel {
      position: fixed; right: 20px; bottom: 86px;
      width: min(380px, calc(100vw - 40px));
      height: min(560px, calc(100vh - 120px));
      background: #1e293b; border: 0.5px solid #334155;
      border-radius: 12px; box-shadow: 0 10px 40px rgba(0,0,0,0.5);
      display: none; flex-direction: column; z-index: 9999;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      color: #e2e8f0; overflow: hidden;
    }
    .aichat-panel.open { display: flex; }
    .aichat-header {
      padding: 12px 14px; border-bottom: 0.5px solid #334155;
      display: flex; align-items: center; justify-content: space-between;
      font-size: 0.95rem; font-weight: 500; color: #f1f5f9;
    }
    .aichat-header-actions { display: flex; gap: 4px; }
    .aichat-header-btn {
      background: transparent; border: none; color: #64748b;
      font-size: 0.75rem; cursor: pointer; padding: 4px 8px; border-radius: 4px;
    }
    .aichat-header-btn:hover { color: #e2e8f0; background: #2a3547; }
    .aichat-msgs {
      flex: 1; overflow-y: auto; padding: 12px 14px;
      display: flex; flex-direction: column; gap: 10px;
      font-size: 0.85rem; line-height: 1.55;
    }
    .aichat-msg {
      max-width: 92%; padding: 8px 12px; border-radius: 10px;
      white-space: pre-wrap; word-break: break-word;
    }
    .aichat-msg.user {
      background: #1e3a5f; color: #e0f2fe;
      align-self: flex-end; border: 0.5px solid #3b82f6;
    }
    .aichat-msg.assistant {
      background: #15202d; color: #cbd5e1;
      align-self: flex-start; border: 0.5px solid #2a3547;
    }
    .aichat-msg.error {
      background: #3f1d1d; color: #fca5a5;
      align-self: stretch; border: 0.5px solid #ef4444; font-size: 0.78rem;
    }
    .aichat-msg.thinking { color: #64748b; font-style: italic; }
    .aichat-empty {
      color: #64748b; font-size: 0.78rem; text-align: center;
      padding: 2rem 1rem; line-height: 1.75;
    }
    .aichat-input-wrap {
      padding: 10px; border-top: 0.5px solid #334155;
      display: flex; gap: 8px; align-items: flex-end;
    }
    .aichat-input {
      flex: 1; background: #0f172a; border: 0.5px solid #334155;
      border-radius: 8px; padding: 8px 10px; color: #e2e8f0;
      font-size: 0.85rem; resize: none; font-family: inherit;
      max-height: 100px; min-height: 36px; line-height: 1.4;
    }
    .aichat-input:focus { outline: none; border-color: #3b82f6; }
    .aichat-send {
      background: #3b82f6; color: white; border: none; border-radius: 8px;
      padding: 8px 14px; cursor: pointer; font-size: 0.85rem; font-weight: 500;
      height: 36px; flex-shrink: 0;
    }
    .aichat-send:disabled { background: #475569; cursor: not-allowed; }
    .aichat-send:hover:not(:disabled) { background: #2563eb; }
    @media (max-width: 480px) {
      .aichat-panel { right: 10px; left: 10px; width: auto; bottom: 80px; }
      .aichat-fab { right: 14px; bottom: 14px; }
    }
  `;
  const style = document.createElement('style');
  style.textContent = css;
  document.head.appendChild(style);

  const fab = document.createElement('button');
  fab.className = 'aichat-fab';
  fab.title = 'AI 助手';
  fab.textContent = '💬';

  const panel = document.createElement('div');
  panel.className = 'aichat-panel';
  panel.innerHTML = `
    <div class="aichat-header">
      <span>🤖 AI 韻腳助手</span>
      <div class="aichat-header-actions">
        <button class="aichat-header-btn" data-action="reset-key">換 Key</button>
        <button class="aichat-header-btn" data-action="close">✕</button>
      </div>
    </div>
    <div class="aichat-msgs" id="aichatMsgs">
      <div class="aichat-empty">
        詢問關於 K 線、韻腳規則、或歷史資料的問題。<br>
        每次送出會將 indices.json + rhymes.json 一併送給 Claude Sonnet 4。
      </div>
    </div>
    <div class="aichat-input-wrap">
      <textarea class="aichat-input" id="aichatInput" rows="1"
        placeholder="輸入問題，Enter 送出 / Shift+Enter 換行"></textarea>
      <button class="aichat-send" id="aichatSend">送出</button>
    </div>
  `;

  document.body.appendChild(fab);
  document.body.appendChild(panel);

  const msgsEl = panel.querySelector('#aichatMsgs');
  const inputEl = panel.querySelector('#aichatInput');
  const sendEl = panel.querySelector('#aichatSend');

  fab.addEventListener('click', () => {
    panel.classList.toggle('open');
    if (panel.classList.contains('open')) setTimeout(() => inputEl.focus(), 50);
  });
  panel.querySelector('[data-action="close"]').addEventListener('click',
    () => panel.classList.remove('open'));
  panel.querySelector('[data-action="reset-key"]').addEventListener('click', () => {
    localStorage.removeItem(STORAGE_KEY);
    addMsg('已清除 API Key。下次送出時會重新詢問。', 'error');
  });

  function addMsg(text, role) {
    const empty = msgsEl.querySelector('.aichat-empty');
    if (empty) empty.remove();
    const m = document.createElement('div');
    m.className = 'aichat-msg ' + role;
    m.textContent = text;
    msgsEl.appendChild(m);
    msgsEl.scrollTop = msgsEl.scrollHeight;
    return m;
  }

  function getApiKey() {
    let key = localStorage.getItem(STORAGE_KEY);
    if (!key) {
      key = prompt('請輸入 Anthropic API Key（會儲存於本機 localStorage，僅此瀏覽器可見）：');
      if (key && key.trim()) {
        localStorage.setItem(STORAGE_KEY, key.trim());
        return key.trim();
      }
      return null;
    }
    return key;
  }

  let cachedData = null;
  async function loadData() {
    if (cachedData) return cachedData;
    const [indices, rhymes] = await Promise.all([
      fetch(dataPath('indices.json')).then(r => r.ok ? r.json() : null).catch(() => null),
      fetch(dataPath('rhymes.json')).then(r => r.ok ? r.json() : null).catch(() => null),
    ]);
    cachedData = { indices, rhymes };
    return cachedData;
  }

  async function send() {
    const text = inputEl.value.trim();
    if (!text) return;
    const apiKey = getApiKey();
    if (!apiKey) {
      addMsg('未提供 API Key，無法送出。', 'error');
      return;
    }

    addMsg(text, 'user');
    inputEl.value = '';
    inputEl.style.height = 'auto';
    sendEl.disabled = true;
    const thinking = addMsg('思考中…', 'assistant');
    thinking.classList.add('thinking');

    try {
      const { indices, rhymes } = await loadData();
      const systemPrompt =
        SYSTEM_PROMPT_PREFIX +
        '\n\n=== indices.json ===\n' + JSON.stringify(indices) +
        '\n\n=== rhymes.json ===\n' + JSON.stringify(rhymes);

      const resp = await fetch('https://api.anthropic.com/v1/messages', {
        method: 'POST',
        headers: {
          'content-type': 'application/json',
          'x-api-key': apiKey,
          'anthropic-version': '2023-06-01',
          'anthropic-dangerous-direct-browser-access': 'true',
        },
        body: JSON.stringify({
          model: MODEL,
          max_tokens: MAX_TOKENS,
          system: systemPrompt,
          messages: [{ role: 'user', content: text }],
        }),
      });

      const data = await resp.json().catch(() => ({}));
      thinking.remove();

      if (!resp.ok) {
        const errMsg = (data && data.error && data.error.message) || ('HTTP ' + resp.status);
        addMsg('API 錯誤：' + errMsg, 'error');
        return;
      }

      const assistantText = (data.content || [])
        .filter(c => c.type === 'text').map(c => c.text).join('\n');
      addMsg(assistantText || '(空回應)', 'assistant');
    } catch (e) {
      thinking.remove();
      addMsg('呼叫失敗：' + e.message, 'error');
    } finally {
      sendEl.disabled = false;
    }
  }

  sendEl.addEventListener('click', send);
  inputEl.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  });
  inputEl.addEventListener('input', () => {
    inputEl.style.height = 'auto';
    inputEl.style.height = Math.min(inputEl.scrollHeight, 100) + 'px';
  });
})();
