/* TELEGRAM GROUPS MODAL MODULE V1 */

(function () {
  window.tgSelectedGroup = window.tgSelectedGroup || null;

  function escapeSafe(str) {
    if (window.escapeHtml) return window.escapeHtml(str);
    return String(str || '').replace(/[&<>]/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[m]));
  }

  function tgChatLabel(c) {
    if (window.tgChatLabel) return window.tgChatLabel(c);
    return c.title || [c.first_name, c.last_name].filter(Boolean).join(' ') || c.username || c.chat_id;
  }

  function tgIsGroupChat(c) {
    return ['group', 'supergroup', 'channel'].includes(String(c.type || '').toLowerCase());
  }

  function ensureTelegramGroupsModal() {
    if (document.getElementById('tgGroupsModal')) return;

    const wrapper = document.createElement('div');
    wrapper.innerHTML = `
<div id="tgGroupsModal" class="modal-overlay">
  <div class="modal-container" style="max-width:980px;">
    <div class="modal-header">
      <h3>📋 Перелік Telegram-груп</h3>
      <button class="modal-close" onclick="tgCloseGroupsModal()">✕</button>
    </div>

    <div class="modal-body">
      <div class="toolbar">
        <button class="btn primary" onclick="tgLoadGroupsModal()">🔄 Оновити список</button>
        <button class="btn" onclick="tgPullUpdates()">📥 Забрати updates</button>
      </div>

      <div id="tgGroupsModalBody">Завантаження...</div>

      <hr style="margin:24px 0;">

      <div id="tgGroupActionPanel" style="display:none;">
        <h3 id="tgGroupActionTitle">Дія з групою</h3>

        <div id="tgGroupAdminPanel" style="display:none;">
          <div class="status-grid">
            <div class="status-item">
              <div class="status-header">Chat ID</div>
              <div id="tgAdminChatId" class="muted">—</div>
            </div>
            <div class="status-item">
              <div class="status-header">Тип</div>
              <div id="tgAdminType" class="muted">—</div>
            </div>
            <div class="status-item">
              <div class="status-header">Статус</div>
              <div id="tgAdminEnabled" class="muted">—</div>
            </div>
          </div>

          <div class="toolbar">
            <button class="btn" onclick="tgAdminToggleSelected()">🔁 Увімкнути / вимкнути</button>
            <button class="btn" onclick="tgAdminSendTestSelected()">📨 Тест у цю групу</button>
          </div>

          <pre id="tgAdminResult">Готово.</pre>
        </div>

        <div id="tgGroupGeneratorPanel" style="display:none;">
          <label>Тема / запит для AI</label>
          <textarea id="tgGenTopic" rows="3" placeholder="Наприклад: прогрів на тему квантової регресії на 7 днів"></textarea>

          <label>Період плану</label>
          <select id="tgGenPeriod">
            <option value="1">1 день</option>\n<option value="3">3 дні</option>\n<option value="7">7 днів</option>
            <option value="14">14 днів</option>
            <option value="30">30 днів</option>
          </select>

          <label>Контекст для AI</label>
          <select id="tgContextDays">
            <option value="3">останні 3 дні</option>
            <option value="7" selected>останній тиждень</option>
            <option value="14">останні 14 днів</option>
            <option value="30">останній місяць</option>
          </select>

          <label>Типи повідомлень</label>
          <select id="tgGenTypes" multiple size="6">
            <option value="STATE" selected>1. Стан / емоція</option>
            <option value="MEANING" selected>2. Сенс / інфо-глибина</option>
            <option value="DIALOG">3. Діалог</option>
            <option value="FLOW">4. Потік / інсайт</option>
            <option value="FRAME">5. Рамка / позиція</option>
            <option value="PRACTICAL">6. Практична порада</option>
            <option value="DEPTH" selected>7. Глибина для своїх</option>
            <option value="SELL">8. Продаж</option>
            <option value="OBJECTION">9. Заперечення</option>
          </select>

          <label>Тип поста</label>
          <select id="tgPostType">
            <option value="announce">1. Пост-повідомлення / анонс</option>
            <option value="argument">2. Пост-аргумент / пояснення</option>
            <option value="hard_sale">3. Лобова продажа</option>
            <option value="warmup">4. Підводка до лобової продажі</option>
            <option value="reminder">5. Нагадування</option>
          </select>

          <div class="toolbar">
            <button class="btn primary" onclick="tgGenerateContentPlanStub()">🧠 Згенерувати план</button>
            <button class="btn" onclick="tgCopyGeneratedToScheduler()">📅 Перенести в планувальник</button>
          </div>

          <pre id="tgGeneratedPlan">AI endpoint ще не підключений. Поки тут буде локальний шаблон плану.</pre>

          <hr style="margin:18px 0;">

          <h3>📅 Контент-календар</h3>
          <div class="toolbar">
            <button class="btn" onclick="tgBuildCalendarFromGeneratedPlan()">📌 Розкласти план у календар</button>
            <button class="btn" onclick="tgClearContentCalendar()">🧹 Очистити календар</button>
          </div>
          <div id="tgContentCalendar" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:12px;">
            Поки календар порожній.
          </div>

          <hr style="margin:18px 0;">

          <h3>👥 Кандидати для прогріву</h3>
          <div class="toolbar">
            <button class="btn" onclick="tgGenerateEngagementCandidates()">🧲 Знайти кого залучити</button>
            <button class="btn" onclick="tgLoadEngagementCandidates()">🔄 Оновити кандидатів</button>
          </div>
          <div id="tgEngagementCandidates">Поки не аналізували.</div>
        </div>

        <div id="tgGroupSchedulerPanel" style="display:none;">
          <label>Дата і час постингу</label>
          <input id="tgScheduleAt" type="datetime-local">

          <label>Текст поста</label>
          <textarea id="tgScheduleText" rows="8" placeholder="Текст, який має піти у вибрану групу"></textarea>

          <label>Confirm admins</label>
          <div class="telegram-status">
            За замовчуванням: Олексій + Даша
            <br>
            <code>330800472, 697587340</code>
          </div>

          <div class="toolbar">
            <button class="btn primary" onclick="tgCreateScheduleForSelectedGroup()">📅 Запланувати з confirm</button>
            <button class="btn" onclick="tgSendNowToSelectedGroup()">🚀 Надіслати зараз у групу</button>
          </div>

          <pre id="tgScheduleResult">Готово до планування.</pre>
        </div>
      </div>
    </div>
  </div>
</div>`;
    document.body.appendChild(wrapper.firstElementChild);
  }

  async function tgOpenGroupsModal() {
    ensureTelegramGroupsModal();
    document.getElementById('tgGroupsModal')?.classList.add('active');
    await tgLoadGroupsModal();
  }

  function tgCloseGroupsModal() {
    document.getElementById('tgGroupsModal')?.classList.remove('active');
  }

  async function tgLoadGroupsModal() {
    ensureTelegramGroupsModal();

    const host = document.getElementById('tgGroupsModalBody');
    if (!host) return;

    host.innerHTML = 'Завантаження груп...';

    try {
      const res = await fetch('/api/telegram/chats');
      const data = await res.json();
      const groups = (data.chats || []).filter(tgIsGroupChat);

      if (!groups.length) {
        host.innerHTML = `
          <div class="muted">
            Груп ще немає. Додай бота в групу або канал, напиши там <code>/register</code>,
            потім натисни “Забрати updates”.
          </div>`;
        return;
      }

      let html = '<div class="table-wrapper"><table><thead><tr><th>Статус</th><th>Група</th><th>Тип</th><th>Chat ID</th><th>Дії</th></tr></thead><tbody>';

      for (const g of groups) {
        const label = escapeSafe(tgChatLabel(g));
        const id = escapeSafe(g.chat_id);
        const enabled = Number(g.enabled || 0) === 1;
        const encoded = encodeURIComponent(JSON.stringify(g));

        html += `<tr>
          <td>${enabled ? '✅ active' : '⏸ disabled'}</td>
          <td><b>${label}</b></td>
          <td>${escapeSafe(g.type || '—')}</td>
          <td><code>${id}</code></td>
          <td style="white-space:nowrap;">
            <button class="btn" onclick="tgOpenGroupAdminFromEncoded('${encoded}')">⚙️ Адмінка</button>
            <button class="btn" onclick="tgOpenGroupGeneratorFromEncoded('${encoded}')">🧠 Генератор</button>
            <button class="btn" onclick="tgOpenGroupSchedulerFromEncoded('${encoded}')">📅 Планувальник</button>
          </td>
        </tr>`;
      }

      html += '</tbody></table></div>';
      host.innerHTML = html;
    } catch (e) {
      host.innerHTML = `<div class="muted">❌ Помилка: ${window.window.escapeSafe(e.message)}</div>`;
    }
  }

  function decodeGroup(encoded) {
    return JSON.parse(decodeURIComponent(encoded));
  }

  function tgHideGroupPanels() {
    ['tgGroupAdminPanel', 'tgGroupGeneratorPanel', 'tgGroupSchedulerPanel'].forEach(id => {
      const el = document.getElementById(id);
      if (el) el.style.display = 'none';
    });

    const panel = document.getElementById('tgGroupActionPanel');
    if (panel) panel.style.display = 'block';
  }

  function tgSetSelectedGroup(g, modeLabel) {
    window.tgSelectedGroup = g;
    const title = document.getElementById('tgGroupActionTitle');
    if (title) title.innerText = `${modeLabel}: ${tgChatLabel(g)} (${g.chat_id})`;
  }

  function tgOpenGroupAdmin(g) {
    ensureTelegramGroupsModal();
    tgHideGroupPanels();
    tgSetSelectedGroup(g, '⚙️ Адмінка групи');

    document.getElementById('tgGroupAdminPanel').style.display = 'block';
    document.getElementById('tgAdminChatId').innerText = g.chat_id || '—';
    document.getElementById('tgAdminType').innerText = g.type || '—';
    document.getElementById('tgAdminEnabled').innerText = Number(g.enabled || 0) === 1 ? '✅ active' : '⏸ disabled';
  }

  function tgOpenGroupGenerator(g) {
    ensureTelegramGroupsModal();
    tgHideGroupPanels();
    tgSetSelectedGroup(g, '🧠 Генератор контенту');
    document.getElementById('tgGroupGeneratorPanel').style.display = 'block';
  }

  function tgOpenGroupScheduler(g) {
    ensureTelegramGroupsModal();
    tgHideGroupPanels();
    tgSetSelectedGroup(g, '📅 Планувальник постингу');
    document.getElementById('tgGroupSchedulerPanel').style.display = 'block';

    const dt = document.getElementById('tgScheduleAt');
    if (dt && !dt.value) {
      const d = new Date(Date.now() + 3600 * 1000);
      d.setMinutes(0, 0, 0);
      dt.value = d.toISOString().slice(0,16);
    }
  }

  async function tgAdminToggleSelected() {
    if (!window.window.tgSelectedGroup) return alert('Групу не вибрано');

    const enabled = Number(window.tgSelectedGroup.enabled || 0) === 1 ? 0 : 1;

    const res = await fetch('/api/telegram/chats/' + encodeURIComponent(window.tgSelectedGroup.chat_id) + '/toggle', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({ enabled: !!enabled})
    });

    const data = await res.json();
    document.getElementById('tgAdminResult').textContent = JSON.stringify(data, null, 2);

    await tgLoadGroupsModal();
    if (window.tgLoadChats) await window.tgLoadChats();
  }

  async function tgAdminSendTestSelected() {
    if (!window.window.tgSelectedGroup) return alert('Групу не вибрано');

    const res = await fetch('/api/telegram/send_client_target', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({ purpose: "planner_internal",  
        chat_ids: [window.tgSelectedGroup.chat_id],
        text: `✅ TEST у групу: ${tgChatLabel(window.tgSelectedGroup)}`
      })
    });

    const data = await res.json();
    document.getElementById('tgAdminResult').textContent = JSON.stringify(data, null, 2);
  }

  function tgSelectedTypes() {
    return Array.from(document.getElementById('tgGenTypes')?.selectedOptions || []).map(o => o.value);
  }


  function tgSelectedPostType() {
    return document.getElementById('tgPostType')?.value || 'announce';
  }

  function tgBuildDashaPrompt(topic, days, styleTypes, postType) {
    const styleMap = {
      STATE: '1. Стан / емоція: теплий, енергетичний текст, який веде людину у внутрішній стан через відчуття, згадування, дозвіл і мʼяке проживання.',
      MEANING: '2. Сенс / інфо-глибина: пояснює складну тему просто, без академічності, через глибший сенс, але без сухої лекції.',
      DIALOG: '3. Діалог: коротко, живо, як у чаті, з емоцією, без офіційності та без ботського тону.',
      FLOW: '4. Потік / інсайт: короткі фрази, інтуїтивна подача, думки як сигнал, не все пояснюється до кінця.',
      FRAME: '5. Рамка / позиція: чітка позиція, зупинка хаосу або неправильного фокусу, без агресії, але впевнено.',
      PRACTICAL: '6. Практична порада: особистий досвід, конкретні цифри/дії, проста життєва логіка, користь одразу.',
      DEPTH: '7. Глибина для своїх: текст для людей у процесі, без спрощення, про внутрішню чесність, трансформацію, зняття зайвого.',
      SELL: '8. Продаж: мʼяке закриття без тиску, через готовність людини, внутрішнє рішення і ясний CTA.',
      OBJECTION: '9. Заперечення: знімає сумнів, не сперечається, а показує справжню причину страху або відкладання.'
    };

    const postTypeMap = {
      announce: '1. Пост-повідомлення / анонс: повідомити про старт стриму, появу нового курсу, нову подію, запуск набору або важливу новину. Має бути ясно що сталося, для кого це і що зробити далі.',
      argument: '2. Пост-аргумент / пояснення: донести читачу думку, пояснити причинно-наслідковий звʼязок, розкрити чому це важливо і змінити погляд.',
      hard_sale: '3. Лобова продажа: прямий продаж без зайвої обхідної дороги, але в стилі Даші — без базарного тиску, через ясність, цінність і запрошення діяти.',
      warmup: '4. Підводка до лобової продажі: прогріти людину перед прямою пропозицією, підвести до проблеми, показати внутрішню готовність, створити очікування.',
      reminder: '5. Нагадування: коротко і живо повернути увагу до події, ефіру, дедлайну, дії, практики, поста або важливого сенсу.'
    };

    const selectedStyles = (styleTypes || []).map(t => styleMap[t] || t).join('\\n');

    return `Ти пишеш у стилі Даші Побережної.

Задача:
Згенерувати контент-план і чернетки Telegram-повідомлень.

Тема:
${topic || 'Без теми'}

Період:
${days} днів

Обраний характер / режим подачі:
${selectedStyles || 'MEANING'}

Обраний тип поста:
${postTypeMap[postType] || postType}

Правила стилю Даші:
- писати живо, не як AI;
- короткі абзаци;
- звернення на "ти" або до "мої люди", якщо доречно;
- не давати середньостатистичний мотиваційний текст;
- використовувати стан, сенс, позицію і внутрішню чесність;
- можна використовувати патерни: "це не..., це...", "подивись...", "відчуй...", "якщо ти вже...";
- без академічності, без сухої лекції, без канцеляриту.

Формат відповіді:
Для кожного дня дай:
1) день;
2) тип повідомлення;
3) кут подачі;
4) готовий текст повідомлення;
5) короткий CTA або дія, якщо доречно.`;
  }


  async function tgGenerateContentPlanStub() {
    const topic = document.getElementById('tgGenTopic')?.value.trim() || 'що запланувати для групи';
    const days = Number(document.getElementById('tgGenPeriod')?.value || 7);
    const types = tgSelectedTypes();
    const postType = tgSelectedPostType();
    const contextDays = Number(document.getElementById('tgContextDays')?.value || 7);

    const outEl = document.getElementById('tgGeneratedPlan');
    if (outEl) {
      outEl.textContent = '⏳ AI аналізує повідомлення групи і генерує план...';
    }

    const group = window.tgSelectedGroup || tgSelectedGroup;
    const chatId = group?.parent_chat_id || group?.chat_id;
    const threadId = group?.thread_id || null;

    if (!chatId) {
      if (outEl) outEl.textContent = '❌ Групу не вибрано або немає chat_id';
      return;
    }

    try {
      const res = await fetch('/api/telegram/ai/generate-plan', {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify({ 
          chat_id: chatId,
          thread_id: threadId,
          topic,
          days,
          style_types: types,
          post_type: postType,
          context_days: contextDays,
          ai_mode: 'deepseek_draft_openai_polish',
          limit: 80
        })
      });

      const data = await res.json();

      if (!data.ok) {
        const fallbackPrompt = tgBuildDashaPrompt(topic, days, types, postType);
        if (outEl) {
          outEl.textContent =
            '⚠️ AI не згенерував відповідь. Технічна відповідь нижче:\\n\\n' +
            JSON.stringify(data, null, 2) +
            '\\n\\nPROMPT:\\n' +
            fallbackPrompt;
        }
        return;
      }

      if (outEl) {
        outEl.textContent =
          `✅ AI план готовий\n` +
          `Група: ${group ? tgChatLabel(group) : '—'}\n` +
          `Chat ID: ${chatId}\n` +
          `Thread ID: ${threadId || '—'}\n` +
          `Повідомлень враховано: ${data.messages_used || 0}\n` +
          `Контекст: останні ${data.context_days || contextDays} днів\n` +
          `Учасників у контексті: ${(data.participants || []).length}\n` +
          `AI mode: ${data.ai_mode || '—'}\n\n` +
          (data.final_text || data.text || '');
      }

    } catch (e) {
      if (outEl) {
        outEl.textContent = '❌ Помилка AI генерації: ' + e.message;
      }
    }
  }

  function tgCopyGeneratedToScheduler() {
    const txt = document.getElementById('tgGeneratedPlan')?.textContent || '';
    document.getElementById('tgScheduleText').value = txt;
    if (window.tgSelectedGroup) tgOpenGroupScheduler(window.tgSelectedGroup);
  }

  async function tgCreateScheduleForSelectedGroup() {
    if (!window.window.tgSelectedGroup) return alert('Групу не вибрано');

    const text = document.getElementById('tgScheduleText')?.value.trim() || '';
    const scheduledAtRaw = document.getElementById('tgScheduleAt')?.value || '';

    if (!text) return alert('Введи текст поста');
    if (!scheduledAtRaw) return alert('Вибери дату і час');

    const scheduled_at = scheduledAtRaw.length === 16 ? scheduledAtRaw + ':00' : scheduledAtRaw;

    const res = await fetch('/api/telegram/schedule', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({ 
        target_chat_id: window.tgSelectedGroup.chat_id,
        control_chat_ids: ['330800472', '697587340'],
        text,
        scheduled_at
      })
    });

    const data = await res.json();
    document.getElementById('tgScheduleResult').textContent = JSON.stringify(data, null, 2);
    alert(data.ok ? '✅ Пост заплановано. Confirm прийде адмінам.' : '❌ Помилка планування');
  }

  async function tgSendNowToSelectedGroup() {
    if (!window.window.tgSelectedGroup) return alert('Групу не вибрано');

    const text = document.getElementById('tgScheduleText')?.value.trim() || '';
    if (!text) return alert('Введи текст поста');

    const res = await fetch('/api/telegram/send_client_target', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({ purpose: "planner_internal",  
        chat_ids: [window.tgSelectedGroup.chat_id],
        text
      })
    });

    const data = await res.json();
    document.getElementById('tgScheduleResult').textContent = JSON.stringify(data, null, 2);
    alert(`Готово. Надіслано: ${data.sent_count || 0}`);
  }

  window.tgOpenGroupsModal = tgOpenGroupsModal;
  window.tgCloseGroupsModal = tgCloseGroupsModal;
  window.tgLoadGroupsModal = tgLoadGroupsModal;

  window.tgOpenGroupAdminFromEncoded = encoded => tgOpenGroupAdmin(decodeGroup(encoded));
  window.tgOpenGroupGeneratorFromEncoded = encoded => tgOpenGroupGenerator(decodeGroup(encoded));
  window.tgOpenGroupSchedulerFromEncoded = encoded => tgOpenGroupScheduler(decodeGroup(encoded));

  window.tgAdminToggleSelected = tgAdminToggleSelected;
  window.tgAdminSendTestSelected = tgAdminSendTestSelected;
  window.tgGenerateContentPlanStub = tgGenerateContentPlanStub;
  window.tgCopyGeneratedToScheduler = tgCopyGeneratedToScheduler;
  window.tgCreateScheduleForSelectedGroup = tgCreateScheduleForSelectedGroup;
  window.tgSendNowToSelectedGroup = tgSendNowToSelectedGroup;
})();


async function tgManualAdd() {
  const val = document.getElementById('tgManualChatInput').value;

  let chat_id = val;

  if (val.includes("web.telegram")) {
    const m = val.match(/#(-?100\d+)/);
    if (m) chat_id = m[1];
  }

  await fetch('/api/telegram/add_manual', {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({ chat_id})
  });

  await tgLoadChats();
}
window.tgManualAdd = tgManualAdd;

/* TELEGRAM ENGAGEMENT FRONTEND V1 */

async function tgGenerateEngagementCandidates() {
  if (!window.window.tgSelectedGroup) return alert('Групу не вибрано');

  const host = document.getElementById('tgEngagementCandidates');
  const topic = document.getElementById('tgGenTopic')?.value.trim() || 'мʼяке залучення до спілкування';
  const contextDays = Number(document.getElementById('tgContextDays')?.value || 7);

  const chatId = window.tgSelectedGroup.parent_chat_id || window.tgSelectedGroup.chat_id;
  const threadId = window.tgSelectedGroup.thread_id || null;

  if (host) host.innerHTML = '⏳ AI аналізує учасників і активність...';

  const res = await fetch('/api/telegram/ai/engagement-candidates', {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({ 
      chat_id: chatId,
      thread_id: threadId,
      context_days: contextDays,
      topic,
      limit: 120
    })
  });

  const data = await res.json();

  if (!data.ok) {
    if (host) host.innerHTML = '<pre>' + JSON.stringify(data, null, 2) + '</pre>';
    return;
  }

  await tgLoadEngagementCandidates();
}

async function tgLoadEngagementCandidates() {
  if (!window.window.tgSelectedGroup) return alert('Групу не вибрано');

  const host = document.getElementById('tgEngagementCandidates');
  const chatId = window.tgSelectedGroup.parent_chat_id || window.tgSelectedGroup.chat_id;
  const threadId = window.tgSelectedGroup.thread_id || null;

  if (host) host.innerHTML = 'Завантаження кандидатів...';

  const url = new URL('/api/telegram/engagement/candidates', window.location.origin);
  url.searchParams.set('chat_id', chatId);
  if (threadId) url.searchParams.set('thread_id', threadId);

  const res = await fetch(url);
  const data = await res.json();
  const items = data.items || [];

  if (!items.length) {
    if (host) host.innerHTML = '<div class="muted">Кандидатів ще немає.</div>';
    return;
  }

  let html = '<div class="table-wrapper"><table><thead><tr><th>Людина</th><th>Причина</th><th>Тон</th><th>Confidence</th><th>Status</th><th>Дії</th></tr></thead><tbody>';

  for (const c of items) {
    html += `<tr>
      <td><b>${window.window.escapeSafe(c.name || c.username || c.from_id || '—')}</b><br>${c.username ? '@' + window.window.escapeSafe(c.username) : ''}</td>
      <td>${window.window.escapeSafe(c.reason || '—')}</td>
      <td>${window.window.escapeSafe(c.tone || '—')}</td>
      <td>${window.window.escapeSafe(c.confidence || '—')}</td>
      <td>${window.window.escapeSafe(c.status || '—')}</td>
      <td style="white-space:nowrap;">
        <button class="btn" onclick="tgGeneratePersonalMessage(${c.id})">🧠 Особисте повідомлення</button>
        <button class="btn primary" onclick="tgConfirmEngagement(${c.id})">✅ Confirm send</button>
      </td>
    </tr>
    <tr>
      <td colspan="6">
        <pre id="tgCandidateMsg_${c.id}">${window.window.escapeSafe(c.generated_message || 'Повідомлення ще не згенеровано.')}</pre>
      </td>
    </tr>`;
  }

  html += '</tbody></table></div>';
  host.innerHTML = html;
}

async function tgGeneratePersonalMessage(candidateId) {
  const topic = document.getElementById('tgGenTopic')?.value.trim() || 'мʼяке залучення до спілкування';
  const out = document.getElementById('tgCandidateMsg_' + candidateId);

  if (out) out.textContent = '⏳ Генерую персональне звернення...';

  const res = await fetch('/api/telegram/ai/personal-message', {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({ 
      candidate_id: candidateId,
      topic,
      history_days: 30,
      limit: 50
    })
  });

  const data = await res.json();

  if (out) {
    out.textContent = data.ok ? (data.final_text || data.text || '') : JSON.stringify(data, null, 2);
  }
}

async function tgConfirmEngagement(candidateId) {
  const out = document.getElementById('tgCandidateMsg_' + candidateId);
  const text = out ? out.textContent.trim() : '';

  if (!text || text.includes('ще не згенеровано')) {
    return alert('Спочатку згенеруй особисте повідомлення');
  }

  if (!confirm('Відправити це звернення у групу/гілку?')) return;

  const res = await fetch('/api/telegram/engagement/' + candidateId + '/confirm', {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({ text})
  });

  const data = await res.json();
  alert(data.ok ? '✅ Відправлено' : '❌ Не відправлено');
  await tgLoadEngagementCandidates();
}

window.tgGenerateEngagementCandidates = tgGenerateEngagementCandidates;
window.tgLoadEngagementCandidates = tgLoadEngagementCandidates;
window.tgGeneratePersonalMessage = tgGeneratePersonalMessage;
window.tgConfirmEngagement = tgConfirmEngagement;

/* TELEGRAM CONTENT CALENDAR V1 */

window.tgGeneratedItems = window.tgGeneratedItems || [];

function tgDateISOPlusDays(days) {
  const d = new Date();
  d.setDate(d.getDate() + days);
  return d.toISOString().slice(0, 10);
}

function tgDefaultDateTimeForDay(dayIndex, slotIndex) {
  const d = new Date();
  d.setDate(d.getDate() + dayIndex);
  const hours = [9, 12, 15, 18, 20];
  d.setHours(hours[slotIndex % hours.length], 0, 0, 0);
  return d.toISOString().slice(0, 16);
}

function tgExtractGeneratedItems(text) {
  const raw = String(text || '').trim();
  if (!raw) return [];

  const chunks = raw
    .split(/\n(?=(День\s+\d+|###\s*День\s+\d+|##\s*День\s+\d+|\d+\.\s))/i)
    .map(x => x.trim())
    .filter(Boolean);

  let items = [];

  for (const chunk of chunks) {
    if (!/(День\s+\d+|\d+\.)/i.test(chunk)) continue;

    const dayMatch = chunk.match(/День\s+(\d+)/i);
    const day = dayMatch ? Number(dayMatch[1]) : (items.length + 1);

    let title = '';
    const titleMatch =
      chunk.match(/Тема[:\-]\s*(.+)/i) ||
      chunk.match(/День\s+\d+[:\-]\s*(.+)/i) ||
      chunk.match(/^\d+\.\s*(.+)/);

    if (titleMatch) title = titleMatch[1].split('\n')[0].trim();

    if (!title) title = `Тема ${day}`;

    items.push({
      id: Date.now() + items.length,
      day,
      title,
      text: chunk,
      post_type: document.getElementById('tgPostType')?.value || 'argument',
      style_types: tgSelectedTypes ? tgSelectedTypes() : [],
      scheduled_at: tgDefaultDateTimeForDay(day - 1, 0),
      status: 'draft'
    });
  }

  if (!items.length) {
    // fallback: якщо AI повернув неструктурований текст
    items = raw.split(/\n\n+/).filter(Boolean).slice(0, 7).map((part, idx) => ({
      id: Date.now() + idx,
      day: idx + 1,
      title: `Тема ${idx + 1}`,
      text: part,
      post_type: document.getElementById('tgPostType')?.value || 'argument',
      style_types: tgSelectedTypes ? tgSelectedTypes() : [],
      scheduled_at: tgDefaultDateTimeForDay(idx, 0),
      status: 'draft'
    }));
  }

  return items.slice(0, 35);
}

function tgBuildCalendarFromGeneratedPlan() {
  const src = document.getElementById('tgGeneratedPlan')?.textContent || '';
  const items = tgExtractGeneratedItems(src);

  window.tgGeneratedItems = items;
  tgRenderContentCalendar();

  alert(`✅ У календар додано: ${items.length} карток`);
}

function tgClearContentCalendar() {
  window.tgGeneratedItems = [];
  tgRenderContentCalendar();
}

function tgUpdateCalendarItem(id, field, value) {
  const item = window.tgGeneratedItems.find(x => String(x.id) === String(id));
  if (!item) return;
  item[field] = value;
}

function tgRenderContentCalendar() {
  const host = document.getElementById('tgContentCalendar');
  if (!host) return;

  const items = window.tgGeneratedItems || [];

  if (!items.length) {
    host.innerHTML = '<div class="muted">Поки календар порожній.</div>';
    return;
  }

  let html = '';

  for (const item of items) {
    html += `
      <div class="card" style="padding:12px;">
        <div style="display:flex;justify-content:space-between;gap:8px;align-items:center;">
          <b>День ${item.day}</b>
          <span class="muted">${window.window.escapeSafe(item.post_type || '')}</span>
        </div>

        <label>Тема</label>
        <input
          value="${window.window.escapeSafe(item.title || '')}"
          onchange="tgUpdateCalendarItem('${item.id}', 'title', this.value)"
          style="width:100%;padding:8px;border-radius:8px;border:1px solid #d0d7de;"
        >

        <label>Дата / час публікації</label>
        <input
          type="datetime-local"
          value="${window.window.escapeSafe(item.scheduled_at || '')}"
          onchange="tgUpdateCalendarItem('${item.id}', 'scheduled_at', this.value)"
          style="width:100%;padding:8px;border-radius:8px;border:1px solid #d0d7de;"
        >

        <label>Текст повідомлення</label>
        <textarea
          rows="10"
          onchange="tgUpdateCalendarItem('${item.id}', 'text', this.value)"
          style="width:100%;padding:8px;border-radius:8px;border:1px solid #d0d7de;"
        >${window.window.escapeSafe(item.text || '')}</textarea>

        <div class="toolbar">
          <button class="btn primary" onclick="tgScheduleCalendarItem('${item.id}')">✅ Запланувати через confirm</button>
          <button class="btn" onclick="tgSendCalendarItemNow('${item.id}')">🚀 Надіслати зараз</button>
          <button class="btn" onclick="tgRemoveCalendarItem('${item.id}')">🗑</button>
        </div>

        <pre id="tgCalendarItemResult_${item.id}">${window.window.escapeSafe(item.status || 'draft')}</pre>
      </div>
    `;
  }

  host.innerHTML = html;
}

function tgRemoveCalendarItem(id) {
  window.tgGeneratedItems = (window.tgGeneratedItems || []).filter(x => String(x.id) !== String(id));
  tgRenderContentCalendar();
}

async function tgScheduleCalendarItem(id) {
  const item = window.tgGeneratedItems.find(x => String(x.id) === String(id));
  const group = window.tgSelectedGroup || tgSelectedGroup;

  if (!item) return alert('Картку не знайдено');
  if (!group) return alert('Групу не вибрано');

  const chatId = group.parent_chat_id || group.chat_id;
  const threadId = group.thread_id || null;

  const text = item.text;
  const scheduledAt = item.scheduled_at && item.scheduled_at.length === 16
    ? item.scheduled_at + ':00'
    : item.scheduled_at;

  const out = document.getElementById('tgCalendarItemResult_' + id);
  if (out) out.textContent = '⏳ Планую...';

  const res = await fetch('/api/telegram/schedule', {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({ 
      target_chat_id: chatId,
      thread_id: threadId,
      control_chat_ids: ['330800472', '697587340'],
      text,
      scheduled_at: scheduledAt
    })
  });

  const data = await res.json();

  item.status = data.ok ? 'scheduled_pending_confirm' : 'schedule_failed';
  if (out) out.textContent = JSON.stringify(data, null, 2);

  alert(data.ok ? '✅ Картку заплановано. Confirm прийде адмінам.' : '❌ Помилка планування');
}

async function tgSendCalendarItemNow(id) {
  const item = window.tgGeneratedItems.find(x => String(x.id) === String(id));
  const group = window.tgSelectedGroup || tgSelectedGroup;

  if (!item) return alert('Картку не знайдено');
  if (!group) return alert('Групу не вибрано');

  const chatId = group.parent_chat_id || group.chat_id;
  const threadId = group.thread_id || null;

  const out = document.getElementById('tgCalendarItemResult_' + id);
  if (out) out.textContent = '⏳ Відправляю...';

  const res = await fetch('/api/telegram/send_client_target', {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({ purpose: "planner_internal",  
      chat_ids: [chatId],
      thread_id: threadId,
      text: item.text
    })
  });

  const data = await res.json();

  item.status = data.ok ? 'sent' : 'send_failed';
  if (out) out.textContent = JSON.stringify(data, null, 2);
}

window.tgBuildCalendarFromGeneratedPlan = tgBuildCalendarFromGeneratedPlan;
window.tgClearContentCalendar = tgClearContentCalendar;
window.tgRenderContentCalendar = tgRenderContentCalendar;
window.tgUpdateCalendarItem = tgUpdateCalendarItem;
window.tgScheduleCalendarItem = tgScheduleCalendarItem;
window.tgSendCalendarItemNow = tgSendCalendarItemNow;
window.tgRemoveCalendarItem = tgRemoveCalendarItem;

/* TELEGRAM CONTENT CALENDAR GLOBAL FIX V1 */

window.tgDateISOPlusDays = function(days) {
  const d = new Date();
  d.setDate(d.getDate() + days);
  return d.toISOString().slice(0, 10);
};

window.tgDefaultDateTimeForDay = function(dayIndex, slotIndex) {
  const d = new Date();
  d.setDate(d.getDate() + dayIndex);
  const hours = [9, 12, 15, 18, 20];
  d.setHours(hours[slotIndex % hours.length], 0, 0, 0);
  return d.toISOString().slice(0, 16);
};

window.tgExtractGeneratedItems = function(text) {
  const raw = String(text || '').trim();
  if (!raw) return [];

  const chunks = raw
    .split(/\n(?=(\*\*День\s+\d+|День\s+\d+|###\s*День\s+\d+|##\s*День\s+\d+|\d+\.\s))/i)
    .map(x => x.trim())
    .filter(Boolean);

  let items = [];

  for (const chunk of chunks) {
    if (!/(День\s+\d+|\d+\.)/i.test(chunk)) continue;

    const dayMatch = chunk.match(/День\s+(\d+)/i);
    const day = dayMatch ? Number(dayMatch[1]) : (items.length + 1);

    const titleMatch =
      chunk.match(/\*\*Тема:\*\*\s*(.+)/i) ||
      chunk.match(/Тема[:\-]\s*(.+)/i) ||
      chunk.match(/День\s+\d+[:\-]\s*(.+)/i) ||
      chunk.match(/^\d+\.\s*(.+)/);

    const title = titleMatch ? titleMatch[1].split('\n')[0].replace(/\*\*/g, '').trim() : `Тема ${day}`;

    items.push({
      id: Date.now() + items.length,
      day,
      title,
      text: chunk,
      post_type: document.getElementById('tgPostType')?.value || 'argument',
      style_types: window.tgSelectedTypes ? window.tgSelectedTypes() : [],
      scheduled_at: window.tgDefaultDateTimeForDay(day - 1, 0),
      status: 'draft'
    });
  }

  if (!items.length) {
    items = raw.split(/\n\n+/).filter(Boolean).slice(0, 7).map((part, idx) => ({
      id: Date.now() + idx,
      day: idx + 1,
      title: `Тема ${idx + 1}`,
      text: part,
      post_type: document.getElementById('tgPostType')?.value || 'argument',
      style_types: window.tgSelectedTypes ? window.tgSelectedTypes() : [],
      scheduled_at: window.tgDefaultDateTimeForDay(idx, 0),
      status: 'draft'
    }));
  }

  return items.slice(0, 35);
};

window.tgBuildCalendarFromGeneratedPlan = function() {
  const src = document.getElementById('tgGeneratedPlan')?.textContent || '';
  const items = window.tgExtractGeneratedItems(src);

  window.tgGeneratedItems = items;
  window.tgRenderContentCalendar();

  alert(`✅ У календар додано: ${items.length} карток`);
};


/* GLOBAL ESCAPE FALLBACK FIX V1 */
window.escapeSafe = window.escapeSafe || function(str) {
  return String(str || '').replace(/[&<>"']/g, function(m) {
    return {
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      '"': '&quot;',
      "'": '&#039;'
    }[m];
  });
};

// ============================================================================
// EDITABLE AI RESULT PATCH V1
// ============================================================================

(function EditableAiResultPatchV1() {
  if (window.__editableAiResultPatchV1) return;
  window.__editableAiResultPatchV1 = true;

  function findGeneratedBlock() {
    const blocks = Array.from(document.querySelectorAll("pre, div, textarea"));
    return blocks.find(el => {
      const txt = el.innerText || el.value || "";
      return txt.includes("CTA") || txt.includes("сьогодні") || txt.includes("Telegram-поста");
    });
  }

  function getEditableText() {
    return "";
  }

  // Перехоплюємо перенос у календар/планувальник, щоб брати відредагований текст
  const originalFetch = window.fetch;
  window.fetch = async function(input, init) {
    const url = String(input || "");

    if (
      init &&
      init.body &&
      (
        url.includes("/api/telegram/schedule_safe") ||
        url.includes("/api/telegram/send_client_target") ||
        url.includes("/api/telegram/send_safe")
      )
    ) {
      try {
        const edited = getEditableText();

        if (edited) {
          const payload = JSON.parse(init.body);
          payload.text = edited;
          init.body = JSON.stringify(payload);
          console.log("[editable ai result used]", payload);
        }
      } catch (e) {
        console.warn("[editable ai result patch failed]", e);
      }
    }

    return originalFetch(input, init);
  };

  document.addEventListener("click", () => {
  });

  document.addEventListener("DOMContentLoaded", () => {
  });

})();

// ============================================================================
// /EDITABLE AI RESULT PATCH V1
// ============================================================================

// ============================================================================
// MULTI PLATFORM CTA BUILDER UI V1
// ============================================================================

(function MultiPlatformCtaBuilderUiV1() {
  if (window.__multiPlatformCtaBuilderUiV1) return;
  window.__multiPlatformCtaBuilderUiV1 = true;

  function injectPlatformCtaFields() {

    const modal = Array.from(document.querySelectorAll("div"))
      .find(x => (x.textContent || "").includes("Основний м’який CTA"));

    if (!modal) return;

    if (document.getElementById("multi-platform-cta-builder-v1")) return;

    const wrap = document.createElement("div");
    wrap.id = "multi-platform-cta-builder-v1";

    wrap.style.marginTop = "18px";
    wrap.style.paddingTop = "18px";
    wrap.style.borderTop = "1px solid #e5e7eb";

    wrap.innerHTML = `
      <div style="font-size:22px;font-weight:900;margin-bottom:18px;">
        🎯 CTA Стратегія платформ
      </div>

      <label style="display:block;font-weight:800;margin-bottom:8px;">
        Платформа CTA
      </label>

      <select id="cta-platform-mode"
        style="width:100%;padding:10px;border-radius:10px;border:1px solid #d1d5db;margin-bottom:18px;">
        <option value="telegram">Telegram</option>
        <option value="instagram">Instagram</option>
        <option value="both">Telegram + Instagram</option>
        <option value="auto">Auto</option>
      </select>

      <div style="font-size:18px;font-weight:900;margin:12px 0;">
        📣 Telegram CTA
      </div>

      <label style="display:block;font-weight:700;margin-bottom:6px;">
        Telegram CTA
      </label>

      <textarea id="telegram-cta-text"
        style="width:100%;min-height:90px;padding:12px;border-radius:12px;border:1px solid #d1d5db;margin-bottom:14px;"
        placeholder="Напиши мені в direct слово СЕСІЯ..."></textarea>

      <label style="display:block;font-weight:700;margin-bottom:6px;">
        Telegram lead keywords
      </label>

      <input id="telegram-cta-keywords"
        style="width:100%;padding:10px;border-radius:10px;border:1px solid #d1d5db;margin-bottom:22px;"
        placeholder="СЕСІЯ, ПРИЧИНА, ХОЧУ..." />

      <div style="font-size:18px;font-weight:900;margin:12px 0;">
        📸 Instagram CTA
      </div>

      <label style="display:block;font-weight:700;margin-bottom:6px;">
        Instagram CTA
      </label>

      <textarea id="instagram-cta-text"
        style="width:100%;min-height:90px;padding:12px;border-radius:12px;border:1px solid #d1d5db;margin-bottom:14px;"
        placeholder="Напиши слово ПРИЧИНА в коментарі або в direct..."></textarea>

      <label style="display:block;font-weight:700;margin-bottom:6px;">
        Instagram engagement goal
      </label>

      <select id="instagram-cta-goal"
        style="width:100%;padding:10px;border-radius:10px;border:1px solid #d1d5db;">
        <option value="comment">Коментар</option>
        <option value="direct">Direct</option>
        <option value="save">Збереження</option>
        <option value="share">Поширення</option>
        <option value="follow">Підписка</option>
      </select>
    `;

    const offerField = Array.from(
      modal.querySelectorAll("input, textarea")
    ).find(el => {
      const parent = el.parentElement || {};
      return (parent.innerText || "").includes("Офер / куди ведемо");
    });

    if (
      offerField &&
      offerField.parentElement &&
      offerField.parentElement.parentElement
    ) {
      offerField.parentElement.parentElement.after(wrap);
    } else {
      modal.appendChild(wrap);
    }

    console.log("[multi platform CTA builder injected]");
  }

  document.addEventListener("click", () => {
    setTimeout(injectPlatformCtaFields, 400);
  });

  document.addEventListener("DOMContentLoaded", () => {
    setTimeout(injectPlatformCtaFields, 1200);
  });

})();

// ============================================================================
// /MULTI PLATFORM CTA BUILDER UI V1
// ============================================================================


/* TELEGRAM_AI_FLOATING_BUTTON_IN_GROUPS_MODAL_V1 */
(function(){
  const oldOpen = window.tgOpenGroupsModal;
  if (typeof oldOpen === "function" && !window.__tgAiGroupsModalWrapped) {
    window.__tgAiGroupsModalWrapped = true;
    window.tgOpenGroupsModal = function(){
      const res = oldOpen.apply(this, arguments);
      setTimeout(function(){
        if (window.injectTelegramAiFloatingButton) {
          window.injectTelegramAiFloatingButton();
        }
      }, 250);
      setTimeout(function(){
        if (window.injectTelegramAiFloatingButton) {
          window.injectTelegramAiFloatingButton();
        }
      }, 900);
      return res;
    };
  }
})();
