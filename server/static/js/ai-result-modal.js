const AIResultModal = (function() {
  let modalElement = null;

  function getTemplate() {
    return `
      <div id="aiResultModalOverlay" class="modal-overlay">
        <div class="modal-container" style="max-width: 900px;">
          <div class="modal-header">
            <h3><span>🧠</span> Відповідь AI-моделі</h3>
            <button class="modal-close" onclick="AIResultModal.close()">×</button>
          </div>
          <div class="modal-body">
            <pre id="aiResultModalText" style="white-space:pre-wrap; max-height:65vh; overflow:auto; background:#f9fafb; color:#111827; border:1px solid #e5e7eb;"></pre>
          </div>
          <div class="modal-footer">
            <button class="btn" onclick="AIResultModal.copy()">📋 Скопіювати</button>
            <button class="btn primary" onclick="AIResultModal.close()">Закрити</button>
          </div>
        </div>
      </div>
    `;
  }

  function ensure() {
    if (!modalElement) {
      document.body.insertAdjacentHTML('beforeend', getTemplate());
      modalElement = document.getElementById('aiResultModalOverlay');
    }
  }

  function open(text) {
    ensure();
    const box = document.getElementById('aiResultModalText');
    if (box) box.innerText = text || 'Відповідь порожня';
    modalElement.classList.add('active');
  }

  function close() {
    if (modalElement) modalElement.classList.remove('active');
  }

  async function copy() {
    const box = document.getElementById('aiResultModalText');
    const text = box ? (box.innerText || box.textContent || '') : '';

    if (!text.trim()) {
      alert('Немає тексту для копіювання');
      return;
    }

    try {
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(text);
      } else {
        const ta = document.createElement('textarea');
        ta.value = text;
        ta.style.position = 'fixed';
        ta.style.left = '-9999px';
        ta.style.top = '0';
        document.body.appendChild(ta);
        ta.focus();
        ta.select();
        document.execCommand('copy');
        document.body.removeChild(ta);
      }

      alert('✅ Текст скопійовано');
    } catch (e) {
      console.error('Copy failed:', e);
      alert('❌ Не вдалося скопіювати текст');
    }
  }

  return { open, close, copy };
})();

window.AIResultModal = AIResultModal;
