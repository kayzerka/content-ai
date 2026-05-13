
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
    sendToContact: '/api/telegram/birthday/send-to-contact',
    autoRun: '/api/telegram/birthday/auto-run',
    backupContacts: '/api/telegram/birthday/contacts/backup-save',
    restoreContacts: '/api/telegram/birthday/contacts/restore',
    backupDownload: '/api/telegram/birthday/contacts/backup-download',
    restoreJson: '/api/telegram/birthday/contacts/restore-json'
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
      tgBirthdayForceLivePreviewBinding();
      tgBirthdayBindDragCanvas();
      tgBirthdayRenderPreviewWithFrames();
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


    window.__bdPositions = {
      message: {
        x: Number(s.pos_message_x ?? 0.040),
        y: Number(s.pos_message_y ?? 0.300)
      },
      discount: {
        x: Number(s.pos_discount_x ?? 0.565),
        y: Number(s.pos_discount_y ?? 0.205)
      },
      services: {
        x: Number(s.pos_services_x ?? 0.565),
        y: Number(s.pos_services_y ?? 0.505)
      },
      date: {
        x: Number(s.pos_date_x ?? 0.685),
        y: Number(s.pos_date_y ?? 0.846)
      }
    };

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
    tgBirthdayRenderPreviewWithFrames();
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
      services_template: $('bdServicesTemplate')?.value || '',

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
      font_date_size: Number($('bdFontDateSize')?.value || 30),
      font_date_color: $('bdFontDateColor')?.value || '#a55d63',

      pos_message_x: window.__bdPositions?.message?.x ?? 0.040,
      pos_message_y: window.__bdPositions?.message?.y ?? 0.300,
      pos_discount_x: window.__bdPositions?.discount?.x ?? 0.565,
      pos_discount_y: window.__bdPositions?.discount?.y ?? 0.205,
      pos_services_x: window.__bdPositions?.services?.x ?? 0.565,
      pos_services_y: window.__bdPositions?.services?.y ?? 0.505,
      pos_date_x: window.__bdPositions?.date?.x ?? 0.685,
      pos_date_y: window.__bdPositions?.date?.y ?? 0.846
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
      template_image: $('bdContactTemplateImage')?.value || $('bdTemplateImage')?.value || ''
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

    tgBirthdayRenderPreviewWithFrames();
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

    await tgBirthdaySaveSettings();
    await tgBirthdaySaveContact();

    setStatus('⏳ Відправляю контакту поздравлялку...');
    const data = await apiPost(API.sendToContact || '/api/telegram/birthday/send-to-contact', {chat_id: chatId});
    setStatus(data.ok ? '✅ Відправлено контакту' : '⚠️ Помилка тесту', data);
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
      font_date_color: $('bdFontDateColor')?.value || '#a55d63',
      positions: window.__bdPositions || {
        message:{x:0.040,y:0.300},
        discount:{x:0.565,y:0.205},
        services:{x:0.565,y:0.505},
        date:{x:0.685,y:0.846}
      }
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
        Math.floor(w * data.positions.message.x),
        Math.floor(h * data.positions.message.y),
        Math.floor(w * 0.255),
        Math.floor(h * 0.028)
      );

      // Знижка
      if (String(data.discount_percent || '').trim()) {
        ctx.fillStyle = data.font_discount_color;
        ctx.font = `${data.font_discount_size}px ${data.font_discount_family}, Georgia, "Times New Roman", serif`;
        ctx.fillText(
          `${data.discount_percent}%`,
          Math.floor(w * data.positions.discount.x),
          Math.floor(h * data.positions.discount.y)
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

      let sy = Math.floor(h * data.positions.services.y);
      const sx = Math.floor(w * data.positions.services.x);
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
        Math.floor(w * data.positions.date.x),
        Math.floor(h * data.positions.date.y)
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
    setStatus('⏳ Готую JSON backup контактів...');
    const data = await apiGet(API.backupDownload || '/api/telegram/birthday/contacts/backup-download');

    if (!data || data.ok === false) {
      setStatus('⚠️ Backup помилка', data);
      return;
    }

    const blob = new Blob([JSON.stringify(data, null, 2)], {type: 'application/json'});
    const url = URL.createObjectURL(blob);

    const a = document.createElement('a');
    const ts = new Date().toISOString().slice(0,19).replace(/[:T]/g, '-');
    a.href = url;
    a.download = `birthday-contacts-backup-${ts}.json`;
    document.body.appendChild(a);
    a.click();
    a.remove();

    URL.revokeObjectURL(url);

    setStatus('✅ Backup скачано JSON файлом', {count: data.count || 0});
  }

  async function tgBirthdayRestoreContacts(){
    const input = document.getElementById('bdRestoreJsonFile');
    if (!input) {
      setStatus('⚠️ Не знайдено input для JSON restore');
      return;
    }

    input.value = '';
    input.click();
  }

  async function tgBirthdayHandleRestoreFile(file){
    if (!file) return;

    setStatus('⏳ Читаю JSON backup...');

    try {
      const text = await file.text();
      const data = JSON.parse(text);

      setStatus('⏳ Відновлюю контакти з JSON...');
      const res = await apiPost(API.restoreJson || '/api/telegram/birthday/contacts/restore-json', data);

      setStatus(res.ok ? '✅ Контакти відновлено з JSON' : '⚠️ Restore помилка', res);

      await tgBirthdayLoadContacts();
      await tgBirthdayLoadSettings();
      await tgBirthdayRenderPreviewWithFrames();
    } catch(e) {
      setStatus('❌ Помилка читання JSON: ' + e.message);
    }
  }




  function tgBirthdayCanvasPoint(evt, canvas){
    const rect = canvas.getBoundingClientRect();
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;
    return {
      x: (evt.clientX - rect.left) * scaleX,
      y: (evt.clientY - rect.top) * scaleY
    };
  }

  function tgBirthdayBlockRects(canvas){
    const w = canvas.width;
    const h = canvas.height;
    const p = window.__bdPositions || {};
    return [
      {key:'message', label:'Привітання', x:(p.message?.x ?? 0.040)*w, y:(p.message?.y ?? 0.300)*h, width:w*0.27, height:h*0.25},
      {key:'discount', label:'Знижка', x:(p.discount?.x ?? 0.565)*w, y:(p.discount?.y ?? 0.205)*h, width:w*0.18, height:h*0.12},
      {key:'services', label:'Послуги', x:(p.services?.x ?? 0.565)*w, y:(p.services?.y ?? 0.505)*h, width:w*0.27, height:h*0.22},
      {key:'date', label:'Дата', x:(p.date?.x ?? 0.685)*w, y:(p.date?.y ?? 0.846)*h, width:w*0.10, height:h*0.05},
    ];
  }

  function tgBirthdayDrawDragFrames(){
    const canvas = $('bdTemplatePreviewCanvas');
    if (!canvas || !canvas.width || !canvas.height) return;
    const ctx = canvas.getContext('2d');
    const rects = tgBirthdayBlockRects(canvas);

    ctx.save();
    rects.forEach(r => {
      ctx.strokeStyle = window.__bdDraggingKey === r.key ? '#2563eb' : 'rgba(37,99,235,0.55)';
      ctx.lineWidth = window.__bdDraggingKey === r.key ? 4 : 2;
      ctx.setLineDash([8, 5]);
      ctx.strokeRect(r.x, r.y, r.width, r.height);

      ctx.setLineDash([]);
      ctx.fillStyle = 'rgba(37,99,235,0.85)';
      ctx.font = '20px Arial';
      ctx.fillText(r.label, r.x + 8, r.y - 24);
    });
    ctx.restore();
  }

  async function tgBirthdayRenderPreviewWithFrames(){
    await tgBirthdayRenderPreview();
    setTimeout(tgBirthdayDrawDragFrames, 80);
  }

  function tgBirthdayBindDragCanvas(){
    const canvas = $('bdTemplatePreviewCanvas');
    if (!canvas || canvas.__bdDragBound) return;
    canvas.__bdDragBound = true;

    canvas.style.cursor = 'move';

    canvas.addEventListener('mousedown', (evt) => {
      const p = tgBirthdayCanvasPoint(evt, canvas);
      const rects = tgBirthdayBlockRects(canvas).reverse();
      const hit = rects.find(r => p.x >= r.x && p.x <= r.x + r.width && p.y >= r.y && p.y <= r.y + r.height);
      if (!hit) return;

      window.__bdDraggingKey = hit.key;
      window.__bdDragOffset = {x: p.x - hit.x, y: p.y - hit.y};
      evt.preventDefault();
      tgBirthdayRenderPreviewWithFrames();
    });

    window.addEventListener('mousemove', (evt) => {
      if (!window.__bdDraggingKey) return;
      const p = tgBirthdayCanvasPoint(evt, canvas);
      const key = window.__bdDraggingKey;

      window.__bdPositions = window.__bdPositions || {};
      window.__bdPositions[key] = window.__bdPositions[key] || {x:0, y:0};

      const ox = window.__bdDragOffset?.x || 0;
      const oy = window.__bdDragOffset?.y || 0;

      window.__bdPositions[key].x = Math.max(0, Math.min(0.95, (p.x - ox) / canvas.width));
      window.__bdPositions[key].y = Math.max(0, Math.min(0.95, (p.y - oy) / canvas.height));

      tgBirthdayRenderPreviewWithFrames();
    });

    window.addEventListener('mouseup', () => {
      if (!window.__bdDraggingKey) return;
      window.__bdDraggingKey = null;
      window.__bdDragOffset = null;
      tgBirthdayRenderPreviewWithFrames();
    });
  }




  function tgBirthdayForceLivePreviewBinding(){
    [
      'bdMessageTemplate',
      'bdServicesTemplate',
      'bdDiscountPercent',
      'bdDiscountCode',
      'bdFirstName',
      'bdTemplateImage',
      'bdContactTemplateImage',
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
      const el = document.getElementById(id);
      if (!el || el.__forcePreviewBound) return;
      el.__forcePreviewBound = true;
      const handler = () => {
        if (typeof tgBirthdayRenderPreviewWithFrames === 'function') {
          tgBirthdayRenderPreviewWithFrames();
        } else if (typeof tgBirthdayRenderPreview === 'function') {
          tgBirthdayRenderPreview();
        }
      };
      el.addEventListener('input', handler);
      el.addEventListener('change', handler);
      el.addEventListener('keyup', handler);
    });
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
  window.tgBirthdayHandleRestoreFile = tgBirthdayHandleRestoreFile;

  setInterval(tgBirthdayAutoRunCheck, 60000);
})();
