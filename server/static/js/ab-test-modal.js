const ABTestModal = (function() {
  let modalElement = null;

  function getModalTemplate() {
    return `
      <div id="abTestModalOverlay" class="modal-overlay">
        <div class="modal-container" style="max-width: 1000px;">
          <div class="modal-header">
            <h3><span>🔬</span> A/B Тестування контенту</h3>
            <button class="modal-close" onclick="ABTestModal.close()">×</button>
          </div>
          <div class="modal-body" id="abTestModalBody">
            <div class="loading-spinner"><div class="spinner"></div><span>Завантаження...</span></div>
          </div>
          <div class="modal-footer">
            <button class="btn" onclick="ABTestModal.showCreateForm()">➕ Новий тест</button>
            <button class="btn" onclick="ABTestModal.close()">Закрити</button>
            <button class="btn primary" onclick="ABTestModal.loadTests()">🔄 Оновити</button>
          </div>
        </div>
      </div>
    `;
  }

  function loadTests() {
    const body = document.getElementById('abTestModalBody');
    if (!body) return;
    
    const tests = JSON.parse(localStorage.getItem('ab_tests') || '[]');
    
    if (tests.length === 0) {
      body.innerHTML = `<div class="empty-state">🔬 Немає A/B тестів.<br><button class="btn primary" onclick="ABTestModal.showCreateForm()">➕ Створити тест</button></div>`;
      return;
    }
    
    let html = `<div style="display: flex; flex-direction: column; gap: 16px;">`;
    for (const test of tests) {
      const winnerClass = test.winner === 'B' ? 'score-high' : (test.winner === 'A' ? 'score-mid' : 'score-low');
      const winnerText = test.winner === 'B' ? '🏆 Переміг B' : (test.winner === 'A' ? '📌 Переміг A' : '🤝 Нічия');
      
      html += `<div class="card"><div style="display: flex; justify-content: space-between;"><strong>🔬 Тест #${test.id} — ${test.platform}</strong><span class="status-badge ${test.status === 'completed' ? 'success' : 'warning'}">${test.status === 'completed' ? '✅ Завершено' : '🟢 Активний'}</span></div>
      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin: 12px 0;">
        <div style="background:#f8f9fc; padding:8px;"><strong>Варіант A</strong><br>Score: ${test.original_score || 0}<br>👁️ ${(test.original_views || 0).toLocaleString()}</div>
        <div style="background:${test.winner === 'B' ? '#d1fae5' : '#f8f9fc'}; padding:8px;"><strong>Варіант B</strong><br>Score: ${test.test_score || 0}<br>👁️ ${(test.test_views || 0).toLocaleString()}</div>
      </div>
      <div><span class="score-badge ${winnerClass}">${winnerText}</span> ${test.improvement_percent ? `📈 ${test.improvement_percent > 0 ? '+' : ''}${test.improvement_percent}%` : ''}</div>
      <div style="margin-top:8px; font-size:11px; color:#6b7280;">📝 ${(test.changes_made || '').substring(0, 100)}</div>
      <div style="margin-top:8px;"><a href="${test.original_url}" target="_blank">🔗 Оригінал</a> ${test.test_url ? `| <a href="${test.test_url}" target="_blank">🔗 Тест</a>` : ''}</div>
      </div>`;
    }
    html += `</div>`;
    body.innerHTML = html;
  }

  function showCreateForm() {
    const body = document.getElementById('abTestModalBody');
    body.innerHTML = `<form id="abTestCreateForm" onsubmit="ABTestModal.createTest(event)">
      <div style="margin-bottom:16px;"><label>📝 Платформа</label><select id="ab_platform" style="width:100%; padding:10px;"><option value="Instagram">📸 Instagram</option><option value="YouTube">▶️ YouTube</option></select></div>
      <div style="margin-bottom:16px;"><label>🔗 URL оригіналу</label><input id="ab_original_url" type="text" style="width:100%; padding:10px;" placeholder="https://www.instagram.com/p/..."></div>
      <div style="margin-bottom:16px;"><label>🔗 URL нової версії</label><input id="ab_test_url" type="text" style="width:100%; padding:10px;" placeholder="https://www.instagram.com/p/..."></div>
      <div style="margin-bottom:16px;"><label>✏️ Що змінили?</label><textarea id="ab_changes" rows="3" style="width:100%; padding:10px;" placeholder="Наприклад: змінив хук, додав CTA в середині..."></textarea></div>
      <div style="display:flex; gap:12px;"><button type="submit" class="btn primary">🚀 Створити тест</button><button type="button" class="btn" onclick="ABTestModal.loadTests()">Скасувати</button></div>
    </form>`;
  }

  function createTest(event) {
    event.preventDefault();
    const platform = document.getElementById('ab_platform').value;
    const originalUrl = document.getElementById('ab_original_url').value;
    const testUrl = document.getElementById('ab_test_url').value;
    const changes = document.getElementById('ab_changes').value;
    
    if (!originalUrl || !changes) { alert('Заповніть URL оригіналу та опишіть зміни'); return; }
    
    const tests = JSON.parse(localStorage.getItem('ab_tests') || '[]');
    tests.unshift({ id: Date.now(), platform, original_url: originalUrl, test_url: testUrl, changes_made: changes, created_at: new Date().toISOString(), status: 'active', original_score: 0, test_score: 0, original_views: 0, test_views: 0, winner: null, improvement_percent: null });
    localStorage.setItem('ab_tests', JSON.stringify(tests));
    alert('✅ A/B тест створено! Після збору метрик натисніть "Завершити"');
    loadTests();
  }

  function open() {
    if (!modalElement) {
      document.body.insertAdjacentHTML('beforeend', getModalTemplate());
      modalElement = document.getElementById('abTestModalOverlay');
    }
    if (modalElement) { modalElement.classList.add('active'); loadTests(); }
  }

  function close() { if (modalElement) modalElement.classList.remove('active'); }

  return { open, close, loadTests, showCreateForm, createTest };
})();

window.ABTestModal = ABTestModal;