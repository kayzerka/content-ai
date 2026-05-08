const CalendarModal = (function() {
  let modalElement = null;
  let selectedDate = null;

  function getTemplate() {
    return `
      <div id="calendarModalOverlay" class="modal-overlay">
        <div class="modal-container" style="max-width:1100px;">
          <div class="modal-header">
            <h3><span>📅</span> Календар відкладеного постингу</h3>
            <button class="modal-close" onclick="CalendarModal.close()">×</button>
          </div>

          <div class="modal-body">
            <div class="toolbar">
              <input id="calendar_pick_datetime" type="datetime-local" style="max-width:260px;" />
              <button class="btn primary" onclick="CalendarModal.applySelected()">✅ Вибрати час</button>
              <button class="btn" onclick="CalendarModal.loadScheduled()">🔄 Оновити календар</button>
            </div>

            <div id="calendar_list">
              <div class="loading-spinner"><div class="spinner"></div><span>Завантаження календаря...</span></div>
            </div>
          </div>

          <div class="modal-footer">
            <button class="btn" onclick="CalendarModal.close()">Закрити</button>
          </div>
        </div>
      </div>
    `;
  }

  function ensure() {
    if (!modalElement) {
      document.body.insertAdjacentHTML('beforeend', getTemplate());
      modalElement = document.getElementById('calendarModalOverlay');
    }
  }

  async function loadScheduled() {
    const box = document.getElementById('calendar_list');
    if (!box) return;

    box.innerHTML = '<div class="loading-spinner"><div class="spinner"></div><span>Завантаження...</span></div>';

    try {
      const res = await fetch('/calendar/events');
      const data = await res.json();
      const events = data.events || data || [];

      if (!events.length) {
        box.innerHTML = '<div class="empty-state">📭 Запланованих постів поки немає.</div>';
        return;
      }

      let html = `
        <div class="table-wrapper">
          <table>
            <thead>
              <tr>
                <th>Дата</th>
                <th>Платформа</th>
                <th>Контент</th>
                <th>Статус</th>
              </tr>
            </thead>
            <tbody>
      `;

      for (const ev of events) {
        html += `
          <tr>
            <td>${ev.start || ev.scheduled_at || '—'}</td>
            <td>${ev.platform || '—'}</td>
            <td class="small">${ev.title || ev.caption || '—'}</td>
            <td>${ev.status || 'scheduled'}</td>
          </tr>
        `;
      }

      html += '</tbody></table></div>';
      box.innerHTML = html;
    } catch (e) {
      box.innerHTML = `<div class="empty-state" style="color:#dc2626;">❌ Помилка календаря: ${e.message}</div>`;
    }
  }

  function open() {
    ensure();
    modalElement.classList.add('active');
    loadScheduled();
  }

  function close() {
    if (modalElement) modalElement.classList.remove('active');
  }

  function applySelected() {
    const value = document.getElementById('calendar_pick_datetime')?.value || '';
    const target = document.getElementById('post_scheduled_at');

    if (!value) {
      alert('Оберіть дату і час');
      return;
    }

    selectedDate = value;

    if (target) {
      target.value = value;
      const enabled = document.getElementById('post_schedule_enabled');
      if (enabled) enabled.checked = true;
    }

    close();
  }

  return {
    open,
    close,
    loadScheduled,
    applySelected
  };
})();

window.CalendarModal = CalendarModal;
