/**
 * Модальне вікно #1 — Аналітика з платформи (API метрики)
 * Підтримує Instagram та YouTube окремо з посиланнями на контент
 */

const MetricsModal = (function() {
  let modalElement = null;
  let currentPlatform = 'all';

  function getModalTemplate() {
    return `
      <div id="metricsModalOverlay" class="modal-overlay">
        <div class="modal-container">
          <div class="modal-header">
            <h3>
              <span>📊</span>
              Аналітика з платформи <span id="metricsModalPlatformLabel">(усі)</span>
            </h3>
            <button class="modal-close" onclick="MetricsModal.close()">×</button>
          </div>
          <div class="modal-body" id="metricsModalBody">
            <div class="loading-spinner">
              <div class="spinner"></div>
              <span>Завантаження метрик...</span>
            </div>
          </div>
          <div class="modal-footer">
            <div style="flex:1; display: flex; gap: 8px;">
              <button class="btn" onclick="MetricsModal.setPlatform('instagram')">📸 Instagram</button>
              <button class="btn" onclick="MetricsModal.setPlatform('youtube')">▶️ YouTube</button>
              <button class="btn" onclick="MetricsModal.setPlatform('all')">🌐 Всі</button>
            </div>
            <button class="btn" onclick="MetricsModal.close()">Закрити</button>
            <button class="btn primary" onclick="MetricsModal.refresh()">🔄 Оновити</button>
          </div>
        </div>
      </div>
    `;
  }

  function formatDate(dateString) {
    if (!dateString) return '—';
    const date = new Date(dateString);
    return date.toLocaleString('uk-UA', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  }

  function getScoreBadge(score) {
    if (!score && score !== 0) return '';
    if (score >= 50) return '<span class="score-badge score-high">🔥 Високий</span>';
    if (score >= 20) return '<span class="score-badge score-mid">📈 Середній</span>';
    return '<span class="score-badge score-low">⚠️ Низький</span>';
  }

  async function fetchInstagramMetrics() {
    try {
      const response = await fetch('/api/ig/media');
      const data = await response.json();
      const mediaList = data?.data || (Array.isArray(data) ? data : []);
      
      return mediaList.map(item => ({
        platform: 'Instagram',
        id: item.id,
        title: (item.caption || '').substring(0, 80),
        views: item.views || item.insights?.impressions || '-',
        likes: item.like_count || 0,
        comments: item.comments_count || 0,
        score: (item.like_count || 0) + (item.comments_count || 0) * 3,
        url: item.permalink || '',
        timestamp: item.timestamp
      }));
    } catch (error) {
      console.error('Instagram metrics error:', error);
      return [];
    }
  }

  async function fetchYouTubeMetrics() {
    try {
      const postsResponse = await fetch('/posts/list');
      if (!postsResponse.ok) return [];
      const postsData = await postsResponse.json();
      
      return (postsData.posts || [])
        .filter(p => String(p.platform || '').toLowerCase() === 'youtube')
        .map(p => ({
          platform: 'YouTube',
          id: p.id,
          title: (p.text || '').split('\n')[0].substring(0, 80),
          views: p.views || 0,
          likes: p.likes || 0,
          comments: p.comments || 0,
          score: p.score || ((p.likes || 0) + (p.comments || 0) * 2),
          url: p.url || '',
          timestamp: p.created_at
        }));
    } catch (error) {
      console.error('YouTube metrics error:', error);
      return [];
    }
  }

  function renderMetricsTable(metrics, platform) {
    const platformLabel = {
      'instagram': 'Instagram',
      'youtube': 'YouTube',
      'all': 'Всі платформи'
    };
    
    const labelSpan = document.getElementById('metricsModalPlatformLabel');
    if (labelSpan) labelSpan.innerHTML = `(${platformLabel[platform] || 'усі'})`;
    
    if (!metrics || metrics.length === 0) {
      return `
        <div class="empty-state">
          📭 Немає даних метрик для ${platformLabel[platform]}.<br>
          ${platform === 'youtube' ? 'Спочатку синхронізуйте YouTube через кнопку "Синхронізувати YouTube"' : 'Спочатку завантажте Instagram стрічку'}
        </div>
      `;
    }

    let html = `
      <div class="modal-table-wrapper">
        <table class="modal-table">
          <thead>
            <tr>
              <th>Platform</th>
              <th>Назва / Текст</th>
              <th>Перегляди</th>
              <th>Лайки</th>
              <th>Коментарі</th>
              <th>Score</th>
              <th>Дата</th>
              <th>Посилання</th>
            </tr>
          </thead>
          <tbody>
    `;

    for (const m of metrics) {
      const score = typeof m.score === 'number' ? m.score : 0;
      
      html += `
        <tr>
          <td><strong>${escapeHtml(m.platform)}</strong></td>
          <td class="analysis-preview" title="${escapeHtml(m.title)}">${escapeHtml(m.title.substring(0, 60))}${m.title.length > 60 ? '…' : ''}<td>
          <td>${typeof m.views === 'number' ? m.views.toLocaleString() : (m.views || '0')}</td>
          <td>${(m.likes || 0).toLocaleString()}</td>
          <td>${(m.comments || 0).toLocaleString()}</td>
          <td>${getScoreBadge(score)} ${score}</td>
          <td style="font-size: 11px;">${formatDate(m.timestamp || m.collected_at)}</td>
          <td>${m.url ? `<a href="${escapeHtml(m.url)}" target="_blank" rel="noopener" style="color: #3b82f6;">🔗 Відкрити</a>` : '—'}</td>
        </tr>
      `;
    }

    html += `
          </tbody>
        </table>
      </div>
      <div class="muted" style="margin-top: 12px; font-size: 12px;">
        📌 Всього записів: ${metrics.length}
      </div>
    `;

    return html;
  }

  async function loadMetrics() {
    const body = document.getElementById('metricsModalBody');
    if (!body) return;

    body.innerHTML = `<div class="loading-spinner"><div class="spinner"></div><span>Завантаження метрик...</span></div>`;

    try {
      let allMetrics = [];
      
      if (currentPlatform === 'instagram' || currentPlatform === 'all') {
        const instagramMetrics = await fetchInstagramMetrics();
        allMetrics = [...allMetrics, ...instagramMetrics];
      }
      
      if (currentPlatform === 'youtube' || currentPlatform === 'all') {
        const youtubeMetrics = await fetchYouTubeMetrics();
        allMetrics = [...allMetrics, ...youtubeMetrics];
      }
      
      body.innerHTML = renderMetricsTable(allMetrics, currentPlatform);
      
    } catch (error) {
      body.innerHTML = `<div class="empty-state" style="color: #dc2626;">❌ Помилка завантаження: ${error.message}<br><button class="btn" style="margin-top: 16px;" onclick="MetricsModal.refresh()">Спробувати ще раз</button></div>`;
    }
  }

  function setPlatform(platform) {
    currentPlatform = platform;
    loadMetrics();
  }

  function open(platform = 'all') {
    currentPlatform = platform;
    if (!modalElement) {
      document.body.insertAdjacentHTML('beforeend', getModalTemplate());
      modalElement = document.getElementById('metricsModalOverlay');
    }
    if (modalElement) {
      modalElement.classList.add('active');
      loadMetrics();
    }
  }

  function close() {
    if (modalElement) modalElement.classList.remove('active');
  }

  function refresh() { loadMetrics(); }

  window.escapeHtml = window.escapeHtml || function(str) {
    if (!str) return '';
    return String(str).replace(/[&<>]/g, m => m === '&' ? '&amp;' : (m === '<' ? '&lt;' : '&gt;'));
  };

  return { open, close, refresh, setPlatform };
})();

window.MetricsModal = MetricsModal;