
(function(){
  const API = {
    settings: '/api/telegram/birthday/settings',
    saveSettings: '/api/telegram/birthday/settings/save',
    templates: '/api/telegram/birthday/templates',
    contacts: '/api/telegram/birthday/contacts',
    upsert: '/api/telegram/birthday/contact/upsert',
    logs: '/api/telegram/birthday/logs',
    runDue: '/api/telegram/birthday/run-due',
    testSend: '/api/telegram/birthday/test-send',
    autoRun: '/api/telegram/birthday/auto-run'
  };

  function $(id){ return document.getElementById(id); }

  function esc(s){
    return String(s ?? '').replace(/[&<>"']/g, m => ({
      '&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'
    }[m]));
  }

  async function apiGet(url){
    const r = await fetch(url);
    return await r.json();
  }

  async function apiPost(url, data){
    const r = await fetch(url, {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify(data || {})
    });
    return await r.json();
  }

  function setStatus(msg, obj){
    const el = $('birthdayStatus');
    if (!el) return;
    el.textContent = obj ? (msg + '\n' + JSON.stringify(obj, null, 2)) : msg;
  }

  function defaultTemplate(){
    return `🎉 {first_name}, вітаємо з Днем народження!

Нехай цей новий рік життя принесе більше легкості, радості та внутрішньої опори 💛

А від нас — маленький подарунок: персональна знижка {discount_percent}% на сесію / консультацію.

🎁 Ваш промокод: {discount_code}

Промокод діє до {valid_until}.`;
  }

  async function tgBirthdayLoad(){
    try {
      await Promise.all([
        tgBirthdayLoadSettings(),
        tgBirthdayLoadTemplates(),
        tgBirthdayLoadContacts(),
        tgBirthdayLoadLogs()
      ]);
      setStatus('✅ Birthday Bot модуль завантажено');
    } catch(e) {
      setStatus('❌ Помилка завантаження: ' + e.message);
    }
  }

  async function tgBirthdayLoadSettings(){
    const data = await apiGet(API.settings);
    const s = data.settings || {};

    if ($('bdEnabled')) $('bdEnabled').checked = Number(s.enabled ?? 1) === 1;
    if ($('bdAutoRun')) $('bdAutoRun').checked = Number(s.auto_run_enabled ?? 0) === 1;
    if ($('bdAutoHour')) $('bdAutoHour').value = s.auto_run_hour ?? 9;
    if ($('bdAutoMinute')) $('bdAutoMinute').value = s.auto_run_minute ?? 0;
    if ($('bdMessageTemplate')) $('bdMessageTemplate').value = s.message_template || defaultTemplate();
    if ($('bdCaptionTemplate')) $('bdCaptionTemplate').value = s.caption_template || '🎁 Ваш подарунок до Дня народження';
    if ($('bdServicesTemplate')) $('bdServicesTemplate').value = s.services_template || `📖 Навчання БВ
♡ 5 сеансів БВ
◎ Сеанс квантової регресії
☼ Сеанс Божого потоку
◌ Обмін енергіями
♧ Родові програми
☆ Курс «Етика сили»`;

    const last = $('bdLastRun');
    if (last) {
      last.innerHTML = `
        <div><b>Останній запуск:</b> ${s.last_run_at ? new Date(Number(s.last_run_at)*1000).toLocaleString() : '—'}</div>
        <div><b>Відправлено:</b> ${esc(s.last_run_sent ?? 0)}</div>
        <div><b>Помилок:</b> ${esc(s.last_run_errors ?? 0)}</div>
        <div><b>Останній auto-run date:</b> ${esc(s.last_auto_run_date || '—')}</div>
      `;
    }

    window.__bdSettings = s;
  }

  async function tgBirthdayLoadTemplates(){
    const data = await apiGet(API.templates);
    const items = data.items || [];
    const selects = ['bdTemplateImage', 'bdContactTemplateImage'];

    for (const id of selects) {
      const sel = $(id);
      if (!sel) continue;
      const current = sel.value || (window.__bdSettings && window.__bdSettings.template_image) || '';
      sel.innerHTML = '<option value="">— без картинки / тільки текст —</option>' +
        items.map(x => `<option value="${esc(x.name)}">${esc(x.name)}</option>`).join('');
      if (current) sel.value = current;
    }

    if ($('bdTemplateImage') && window.__bdSettings?.template_image) {
      $('bdTemplateImage').value = window.__bdSettings.template_image;
    }

    tgBirthdayUpdatePreview();
  }

  function tgBirthdayUpdatePreview(){
    const sel = $('bdTemplateImage');
    const img = $('bdTemplatePreview');
    if (!sel || !img) return;

    if (sel.value) {
      img.src = '/static/birthday_templates/' + encodeURIComponent(sel.value);
      img.style.display = 'block';
    } else {
      img.removeAttribute('src');
      img.style.display = 'none';
    }
  }

  async function tgBirthdaySaveSettings(){
    const payload = {
      enabled: $('bdEnabled')?.checked ? 1 : 0,
      auto_run_enabled: $('bdAutoRun')?.checked ? 1 : 0,
      auto_run_hour: Number($('bdAutoHour')?.value || 9),
      auto_run_minute: Number($('bdAutoMinute')?.value || 0),
      template_image: $('bdTemplateImage')?.value || '',
      message_template: $('bdMessageTemplate')?.value || defaultTemplate(),
      caption_template: $('bdCaptionTemplate')?.value || '',
      services_template: $('bdServicesTemplate')?.value || '' ''
    };

    const data = await apiPost(API.saveSettings, payload);
    setStatus(data.ok ? '✅ Налаштування збережено' : '⚠️ Помилка збереження', data);
    await tgBirthdayLoadSettings();
  }

  async function tgBirthdaySaveContact(){
    const payload = {
      chat_id: $('bdChatId')?.value?.trim(),
      first_name: $('bdFirstName')?.value?.trim(),
      last_name: $('bdLastName')?.value?.trim(),
      username: $('bdUsername')?.value?.trim(),
      birthday_date: $('bdBirthdayDate')?.value,
      discount_percent: Number($('bdDiscountPercent')?.value || 15),
      discount_code: $('bdDiscountCode')?.value?.trim() || 'BDAY15',
      template_image: $('bdContactTemplateImage')?.value || ''
    };

    if (!payload.chat_id) {
      setStatus('⚠️ Вкажи Telegram chat_id');
      return;
    }
    if (!payload.birthday_date) {
      setStatus('⚠️ Вкажи дату народження');
      return;
    }

    const data = await apiPost(API.upsert, payload);
    setStatus(data.ok ? '✅ Контакт збережено' : '⚠️ Помилка контакту', data);
    await tgBirthdayLoadContacts();
  }

  async function tgBirthdayLoadContacts(){
    const data = await apiGet(API.contacts);
    const box = $('bdContactsTable');
    if (!box) return;

    const items = data.items || [];
    if (!items.length) {
      box.innerHTML = '<div class="birthday-muted">Контактів ще немає.</div>';
      return;
    }

    box.innerHTML = `
      <div class="birthday-table-wrap">
        <table class="birthday-table">
          <thead>
            <tr>
              <th>Імʼя</th>
              <th>chat_id</th>
              <th>ДН</th>
              <th>Знижка</th>
              <th>Шаблон</th>
              <th>Рік</th>
              <th>Дія</th>
            </tr>
          </thead>
          <tbody>
            ${items.map(x => `
              <tr>
                <td>${esc(x.first_name || '')}<br><span class="birthday-muted">@${esc(x.username || '')}</span></td>
                <td>${esc(x.chat_id)}</td>
                <td>${esc(x.birthday_date || '')}</td>
                <td>${esc(x.discount_percent || 15)}%<br>${esc(x.discount_code || '')}</td>
                <td>${esc(x.template_image || '')}</td>
                <td>${esc(x.birthday_last_sent_year || '—')}</td>
                <td><button class="btn" onclick="tgBirthdayFillContact('${esc(x.chat_id)}')">✏️</button></td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      </div>
    `;

    window.__bdContacts = items;
  }

  function tgBirthdayFillContact(chatId){
    const x = (window.__bdContacts || []).find(i => String(i.chat_id) === String(chatId));
    if (!x) return;

    if ($('bdChatId')) $('bdChatId').value = x.chat_id || '';
    if ($('bdFirstName')) $('bdFirstName').value = x.first_name || '';
    if ($('bdLastName')) $('bdLastName').value = x.last_name || '';
    if ($('bdUsername')) $('bdUsername').value = x.username || '';
    if ($('bdBirthdayDate')) $('bdBirthdayDate').value = x.birthday_date || '';
    if ($('bdDiscountPercent')) $('bdDiscountPercent').value = x.discount_percent || 15;
    if ($('bdDiscountCode')) $('bdDiscountCode').value = x.discount_code || 'BDAY15';
    if ($('bdContactTemplateImage')) $('bdContactTemplateImage').value = x.template_image || '';

    setStatus('✏️ Контакт завантажено в форму');
  }

  async function tgBirthdayRunDue(){
    setStatus('⏳ Запускаю перевірку днів народження...');
    const data = await apiPost(API.runDue, {});
    setStatus(data.ok ? '✅ Перевірку завершено' : '⚠️ Помилка перевірки', data);
    await tgBirthdayLoadSettings();
    await tgBirthdayLoadContacts();
    await tgBirthdayLoadLogs();
  }

  async function tgBirthdayTestSend(){
    const chatId = $('bdChatId')?.value?.trim();
    if (!chatId) {
      setStatus('⚠️ Для тесту вкажи chat_id у формі контакта');
      return;
    }

    await tgBirthdaySaveContact();

    setStatus('⏳ Відправляю тестову поздравлялку...');
    const data = await apiPost(API.testSend, {chat_id: chatId});
    setStatus(data.ok ? '✅ Тест відправлено' : '⚠️ Помилка тесту', data);
    await tgBirthdayLoadLogs();
  }

  async function tgBirthdayAutoRunCheck(){
    try {
      const data = await apiPost(API.autoRun, {});
      if (data && data.status && data.status !== 'auto_disabled' && data.status !== 'not_time_yet' && data.status !== 'already_ran_today') {
        console.log('[birthday auto-run]', data);
      }
      if (data && data.sent) {
        setStatus('🎂 Auto-run відправив привітання', data);
        await tgBirthdayLoadSettings();
        await tgBirthdayLoadContacts();
        await tgBirthdayLoadLogs();
      }
    } catch(e) {
      console.warn('[birthday auto-run error]', e);
    }
  }

  async function tgBirthdayLoadLogs(){
    const data = await apiGet(API.logs + '?limit=30');
    const box = $('bdLogs');
    if (!box) return;

    const items = data.items || [];
    if (!items.length) {
      box.innerHTML = '<div class="birthday-muted">Логів ще немає.</div>';
      return;
    }

    box.innerHTML = `
      <div class="birthday-table-wrap">
        <table class="birthday-table">
          <thead>
            <tr>
              <th>Час</th>
              <th>Контакт</th>
              <th>Статус</th>
              <th>Помилка</th>
            </tr>
          </thead>
          <tbody>
            ${items.map(x => `
              <tr>
                <td>${x.sent_at ? esc(new Date(Number(x.sent_at)*1000).toLocaleString()) : '—'}</td>
                <td>${esc(x.contact_name || '')}<br><span class="birthday-muted">${esc(x.chat_id || '')}</span></td>
                <td>${esc(x.status || '')}</td>
                <td>${esc(x.error || '')}</td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      </div>
    `;
  }

  window.tgBirthdayLoad = tgBirthdayLoad;
  window.tgBirthdaySaveSettings = tgBirthdaySaveSettings;
  window.tgBirthdaySaveContact = tgBirthdaySaveContact;
  window.tgBirthdayRunDue = tgBirthdayRunDue;
  window.tgBirthdayTestSend = tgBirthdayTestSend;
  window.tgBirthdayFillContact = tgBirthdayFillContact;
  window.tgBirthdayUpdatePreview = tgBirthdayUpdatePreview;

  setInterval(tgBirthdayAutoRunCheck, 60000);
})();
