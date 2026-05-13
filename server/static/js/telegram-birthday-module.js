
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
      document.querySelectorAll('main section, body > section').forEach(sec => {
        sec.style.display = 'none';
      });
      const birthdaySection = document.getElementById('birthday');
      if (birthdaySection) {
        birthdaySection.style.display = 'block';
        birthdaySection.style.visibility = 'visible';
        birthdaySection.style.opacity = '1';
      }
      await Promise.all([
        tgBirthdayLoadSettings(),
        tgBirthdayLoadTemplates(),
        tgBirthdayLoadContacts(),
        tgBirthdayLoadLogs()
      ]);
      tgBirthdayBindPreviewInputs();
      tgBirthdayRenderPreview();
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
    if ($('bdFontMessageFamily')) $('bdFontMessageFamily').value = s.font_message_family || 'Avenir';
    if ($('bdFontMessageSize')) $('bdFontMessageSize').value = s.font_message_size || 22;
    if ($('bdFontMessageColor')) $('bdFontMessageColor').value = s.font_message_color || '#463732';

    if ($('bdFontDiscountFamily')) $('bdFontDiscountFamily').value = s.font_discount_family || 'Georgia';
    if ($('bdFontDiscountSize')) $('bdFontDiscountSize').value = s.font_discount_size || 120;
    if ($('bdFontDiscountColor')) $('bdFontDiscountColor').value = s.font_discount_color || '#a55d63';

    if ($('bdFontServicesFamily')) $('bdFontServicesFamily').value = s.font_services_family || 'Georgia';
    if ($('bdFontServicesSize')) $('bdFontServicesSize').value = s.font_services_size || 20;
    if ($('bdFontServicesColor')) $('bdFontServicesColor').value = s.font_services_color || '#3a2d28';

    if ($('bdFontDateFamily')) $('bdFontDateFamily').value = s.font_date_family || 'Georgia';
    if ($('bdFontDateSize')) $('bdFontDateSize').value = s.font_date_size || 34;
    if ($('bdFontDateColor')) $('bdFontDateColor').value = s.font_date_color || '#a55d63';
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
    tgBirthdayRenderPreview();
  }

  function tgBirthdayUpdatePreview(){
    tgBirthdayRenderPreview();
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
      services_template: $('bdServicesTemplate')?.value || ''
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

    tgBirthdayRenderPreview();
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



  function tgBirthdayPreviewData(){
    const valid = new Date();
    valid.setDate(valid.getDate() + 7);
    const dd = String(valid.getDate()).padStart(2, '0');
    const mm = String(valid.getMonth() + 1).padStart(2, '0');
    const yyyy = valid.getFullYear();

    return {
      first_name: $('bdFirstName')?.value?.trim() || '',
      discount_percent: $('bdDiscountPercent')?.value || '',
      discount_code: $('bdDiscountCode')?.value?.trim() || '',
      valid_until: `${dd}.${mm}.${yyyy}`,
      valid_until_short: `${dd}.${mm}`,
      message_template: $('bdMessageTemplate')?.value || defaultTemplate(),
      services_template: $('bdServicesTemplate')?.value || '',
      template_image: $('bdTemplateImage')?.value || $('bdContactTemplateImage')?.value || '',
      font_message_family: $('bdFontMessageFamily')?.value || 'Avenir',
      font_message_size: Number($('bdFontMessageSize')?.value || 22),
      font_message_color: $('bdFontMessageColor')?.value || '#463732',
      font_discount_family: $('bdFontDiscountFamily')?.value || 'Georgia',
      font_discount_size: Number($('bdFontDiscountSize')?.value || 120),
      font_discount_color: $('bdFontDiscountColor')?.value || '#a55d63',
      font_services_family: $('bdFontServicesFamily')?.value || 'Georgia',
      font_services_size: Number($('bdFontServicesSize')?.value || 20),
      font_services_color: $('bdFontServicesColor')?.value || '#3a2d28',
      font_date_family: $('bdFontDateFamily')?.value || 'Georgia',
      font_date_size: Number($('bdFontDateSize')?.value || 34),
      font_date_color: $('bdFontDateColor')?.value || '#a55d63'
    };
  }

  function tgBirthdayApplyVars(text, data){
    return String(text || '')
      .replaceAll('{first_name}', data.first_name)
      .replaceAll('{discount_percent}', data.discount_percent)
      .replaceAll('{discount_code}', data.discount_code)
      .replaceAll('{valid_until}', data.valid_until)
      .replaceAll('{birthday_date}', $('bdBirthdayDate')?.value || '');
  }

  function tgBirthdayWrapCanvasText(ctx, text, x, y, maxWidth, lineHeight){
    const words = String(text || '').replace(/[🎉💛🎁]/g, '').split(/\s+/).filter(Boolean);
    let line = '';
    for (const word of words) {
      const test = line ? line + ' ' + word : word;
      if (ctx.measureText(test).width <= maxWidth) {
        line = test;
      } else {
        if (line) {
          ctx.fillText(line, x, y);
          y += lineHeight;
        }
        line = word;
      }
    }
    if (line) ctx.fillText(line, x, y);
    return y + lineHeight;
  }

  async function tgBirthdayRenderPreview(){
    const canvas = $('bdTemplatePreviewCanvas');
    if (!canvas) return;

    const data = tgBirthdayPreviewData();
    const ctx = canvas.getContext('2d');

    const img = new Image();
    img.crossOrigin = 'anonymous';

    const template = data.template_image;
    if (!template) {
      canvas.width = 1;
      canvas.height = 1;
      ctx.clearRect(0, 0, 1, 1);
      return;
    }
    img.src = '/static/birthday_templates/' + encodeURIComponent(template) + '?v=' + Date.now();

    img.onload = function(){
      canvas.width = img.naturalWidth;
      canvas.height = img.naturalHeight;

      const w = canvas.width;
      const h = canvas.height;

      ctx.clearRect(0, 0, w, h);
      ctx.drawImage(img, 0, 0, w, h);

      // Лівий текст
      ctx.fillStyle = data.font_message_color;
      ctx.font = `${data.font_message_size}px ${data.font_message_family}, "Avenir Next", "Helvetica Neue", Arial, sans-serif`;
      ctx.textBaseline = 'top';

      let msg = data.message_template ? tgBirthdayApplyVars(data.message_template, data) : '';
      if (msg.trim()) tgBirthdayWrapCanvasText(
        ctx,
        msg,
        Math.floor(w * 0.040),
        Math.floor(h * 0.300),
        Math.floor(w * 0.255),
        Math.floor(h * 0.028)
      );

      // Знижка
      if (String(data.discount_percent || '').trim()) {
        ctx.fillStyle = data.font_discount_color;
        ctx.font = `${data.font_discount_size}px ${data.font_discount_family}, Georgia, "Times New Roman", serif`;
        ctx.fillText(
          `${data.discount_percent}%`,
          Math.floor(w * 0.565),
          Math.floor(h * 0.205)
        );
      }

      // Послуги
      ctx.fillStyle = data.font_services_color;
      ctx.font = `${data.font_services_size}px ${data.font_services_family}, Georgia, "Times New Roman", serif`;

      const services = String(data.services_template || '')
        .split('\n')
        .map(x => x.trim())
        .filter(Boolean)
        .map(x => x.match(/^[•♡◎☼◌♧☆📖]/) ? x : '• ' + x);

      let sy = Math.floor(h * 0.505);
      const sx = Math.floor(w * 0.565);
      const lineH = Math.floor(h * 0.031);

      services.forEach(line => {
        ctx.fillText(line, sx, sy);
        sy += lineH;
      });

      // Дата в нижньому блоці
      ctx.fillStyle = data.font_date_color;
      ctx.font = `${data.font_date_size}px ${data.font_date_family}, Georgia, "Times New Roman", serif`;
      ctx.fillText(
        data.valid_until_short,
        Math.floor(w * 0.685),
        Math.floor(h * 0.846)
      );
    };

    img.onerror = function(){
      ctx.clearRect(0, 0, canvas.width, canvas.height);
    };
  }

  function tgBirthdayBindPreviewInputs(){
    [
      'bdFirstName',
      'bdDiscountPercent',
      'bdDiscountCode',
      'bdMessageTemplate',
      'bdServicesTemplate',
      'bdTemplateImage',
      'bdContactTemplateImage',
      'bdBirthdayDate',
      'bdFontMessageFamily',
      'bdFontMessageSize',
      'bdFontMessageColor',
      'bdFontDiscountFamily',
      'bdFontDiscountSize',
      'bdFontDiscountColor',
      'bdFontServicesFamily',
      'bdFontServicesSize',
      'bdFontServicesColor',
      'bdFontDateFamily',
      'bdFontDateSize',
      'bdFontDateColor'
    ].forEach(id => {
      const el = $(id);
      if (!el || el.__bdPreviewBound) return;
      el.__bdPreviewBound = true;
      el.addEventListener('input', tgBirthdayRenderPreview);
      el.addEventListener('change', tgBirthdayRenderPreview);
    });
  }




  async function tgBirthdayBackupContacts(){
    setStatus('⏳ Зберігаю backup контактів...');
    const data = await apiPost(API.backupContacts, {});
    setStatus(data.ok ? '✅ Backup контактів збережено' : '⚠️ Backup помилка', data);
  }

  async function tgBirthdayRestoreContacts(){
    if (!confirm('Відновити контакти Birthday Bot з backup після деплою?')) return;
    setStatus('⏳ Відновлюю контакти...');
    const data = await apiPost(API.restoreContacts, {});
    setStatus(data.ok ? '✅ Контакти відновлено' : '⚠️ Restore помилка', data);
    await tgBirthdayLoadContacts();
    await tgBirthdayLoadSettings();
    await tgBirthdayRenderPreview();
  }


  window.tgBirthdayLoad = tgBirthdayLoad;
  window.tgBirthdaySaveSettings = tgBirthdaySaveSettings;
  window.tgBirthdaySaveContact = tgBirthdaySaveContact;
  window.tgBirthdayRunDue = tgBirthdayRunDue;
  window.tgBirthdayTestSend = tgBirthdayTestSend;
  window.tgBirthdayFillContact = tgBirthdayFillContact;
  window.tgBirthdayUpdatePreview = tgBirthdayUpdatePreview;
  window.tgBirthdayBackupContacts = tgBirthdayBackupContacts;
  window.tgBirthdayRestoreContacts = tgBirthdayRestoreContacts;

  setInterval(tgBirthdayAutoRunCheck, 60000);
})();
