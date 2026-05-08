(function(){
  const ROOT_ID = "funnels-native-root";
  const PANEL_ID = "funnels-ui-v1-panel";

  let state = {
    selectedKey: "",
    funnels: [],
    funnel: null,
    steps: [],
    leads: [],
    sessions: [],
    last: null
  };

  async function api(path, opts){
    const r = await fetch(path, opts || {});
    const text = await r.text();
    try { return JSON.parse(text); }
    catch(e){ return {ok:false, status:r.status, error:"bad_json", body:text}; }
  }

  function esc(s){
    return String(s == null ? "" : s)
      .replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
  }

  function val(id){ return document.getElementById(id)?.value || ""; }

  function css(){
    if (document.getElementById("funnels-dynamic-style")) return;
    const st = document.createElement("style");
    st.id = "funnels-dynamic-style";
    st.textContent = `
      #${ROOT_ID}, #${PANEL_ID}{
        background:#fff;color:#111;font-family:system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
      }
      #${ROOT_ID}{padding:16px}
      #${PANEL_ID}{
        position:fixed;right:18px;bottom:120px;width:920px;max-width:calc(100vw - 36px);
        max-height:82vh;overflow:auto;z-index:99999;border:1px solid #ddd;border-radius:18px;
        box-shadow:0 20px 70px rgba(0,0,0,.32);padding:16px;
      }
      .fu-head{display:flex;justify-content:space-between;align-items:flex-start;gap:12px;margin-bottom:12px}
      .fu-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px}
      .fu-grid3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px}
      .fu-card{border:1px solid #eee;border-radius:14px;padding:12px;margin:10px 0;background:#fafafa}
      .fu-row{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin:8px 0}
      .fu-muted{color:#666;font-size:12px}
      .fu-pill{display:inline-block;border:1px solid #ddd;border-radius:999px;padding:2px 8px;font-size:12px;background:#fff}
      .fu-ok{color:#087b2f}.fu-bad{color:#a00000}
      #${ROOT_ID} input,#${ROOT_ID} textarea,#${ROOT_ID} select,
      #${PANEL_ID} input,#${PANEL_ID} textarea,#${PANEL_ID} select{
        width:100%;box-sizing:border-box;border:1px solid #ddd;border-radius:10px;
        padding:9px;margin:4px 0;background:#fff;color:#111;font:inherit;
      }
      #${ROOT_ID} textarea,#${PANEL_ID} textarea{min-height:70px;resize:vertical;font-size:13px}
      #${ROOT_ID} button,#${PANEL_ID} button{
        border:1px solid #ddd;border-radius:10px;background:#f7f7f7;
        padding:8px 10px;cursor:pointer;font-weight:650;
      }
      #${ROOT_ID} button.primary,#${PANEL_ID} button.primary{background:#111;color:#fff;border-color:#111}
      #${ROOT_ID} button.danger,#${PANEL_ID} button.danger{background:#fff2f2;color:#900;border-color:#f0caca}
      #${ROOT_ID} pre,#${PANEL_ID} pre{
        white-space:pre-wrap;background:#f6f6f6;border-radius:12px;padding:10px;font-size:12px;
        max-height:260px;overflow:auto;
      }
      .fu-table{width:100%;border-collapse:collapse;font-size:13px}
      .fu-table th,.fu-table td{border-bottom:1px solid #eee;padding:7px;text-align:left;vertical-align:top}
    `;
    document.head.appendChild(st);
  }

  function root(){
    let r = document.getElementById(ROOT_ID);
    if (!r) {
      r = document.getElementById(PANEL_ID);
      if (!r) {
        r = document.createElement("div");
        r.id = PANEL_ID;
        document.body.appendChild(r);
      }
    }
    return r;
  }

  async function refresh(){
    const res = await api("/api/funnels/configs/list");
    state.funnels = res.items || [];
    if (!state.selectedKey && state.funnels[0]) state.selectedKey = state.funnels[0].funnel_key;
    if (state.selectedKey) await loadSelected(false);
    await loadLeads(false);
    await loadSessions(false);
  }

  async function loadSelected(showRaw){
    if (!state.selectedKey) return;
    const res = await api(`/api/funnels/configs/by-key/${encodeURIComponent(state.selectedKey)}`);
    state.funnel = res.item || null;
    state.steps = res.steps || [];
    if (showRaw) show(res);
  }

  async function loadLeads(showRaw){
    const res = await api("/api/funnels/runtime/leads?limit=50");
    state.leads = res.items || [];
    if (showRaw) show(res);
  }

  async function loadSessions(showRaw){
    const res = await api("/api/funnels/runtime/sessions?limit=50");
    state.sessions = res.items || [];
    if (showRaw) show(res);
  }

  async function render(){
    css();
    await refresh();

    const r = root();
    r.innerHTML = `
      <div class="fu-head">
        <div>
          <h3 style="margin:0">🧲 Конструктор воронок</h3>
          <div class="fu-muted">Динамічні funnel_key, тригери, Telegram deep-link, кроки, ручний запуск лідів.</div>
        </div>
        <button id="fu-close">×</button>
      </div>

      <div class="fu-card">
        <h4>Воронки</h4>
        <div class="fu-row">
          <select id="fu-select-key">
            <option value="">— вибери воронку —</option>
            ${state.funnels.map(f => `<option value="${esc(f.funnel_key)}" ${f.funnel_key===state.selectedKey?"selected":""}>${esc(f.funnel_name || f.funnel_key)} (${esc(f.funnel_key)})</option>`).join("")}
          </select>
          <button class="primary" id="fu-load">Завантажити</button>
          <button id="fu-status">Status</button>
        </div>
      </div>

      ${funnelEditorHtml()}
      ${stepsHtml()}
      ${leadsHtml()}
      ${sessionsHtml()}

      <div class="fu-card">
        <h4>Raw output</h4>
        <pre id="fu-output">${esc(JSON.stringify(state.last || {}, null, 2))}</pre>
      </div>
    `;

    bind();
  }

  function funnelEditorHtml(){
    const f = state.funnel || {};
    return `
      <div class="fu-card">
        <h4>Створити / редагувати воронку</h4>
        <div class="fu-grid3">
          <label>funnel_key<input id="fu-key" value="${esc(f.funnel_key || "")}" placeholder="legke_tilo_bv"></label>
          <label>Назва<input id="fu-name" value="${esc(f.funnel_name || "")}" placeholder="Легке тіло БВ"></label>
          <label>Активна<select id="fu-active"><option value="1" ${String(f.active ?? 1)==="1"?"selected":""}>1</option><option value="0" ${String(f.active)==="0"?"selected":""}>0</option></select></label>
        </div>
        <div class="fu-grid3">
          <label>Пріоритет<input id="fu-priority" value="${esc(f.priority || 100)}"></label>
          <label>Платформа<input id="fu-source" value="${esc(f.source_platform || "instagram")}"></label>
          <label>Telegram bot username<input id="fu-bot" value="${esc(f.telegram_bot_username || "")}" placeholder="content_ai_planner_bot"></label>
        </div>
        <label>Trigger keywords<textarea id="fu-triggers" placeholder="вага, схуднення, ...">${esc(f.trigger_keywords || "")}</textarea></label>
        <label>Content keywords<textarea id="fu-content-keywords">${esc(f.content_keywords || "")}</textarea></label>
        <div class="fu-grid">
          <label>Telegram channel URL<input id="fu-channel" value="${esc(f.telegram_channel_url || "")}"></label>
          <label>Next funnel key<input id="fu-next" value="${esc(f.next_funnel_key || "")}"></label>
        </div>
        <label>DM template <span class="fu-muted">Плейсхолдери: {{funnel_name}}, {{telegram_deeplink}}, {{source_user_id}}, {{source_message}}</span>
          <textarea id="fu-dm">${esc(f.dm_template || "")}</textarea>
        </label>
        <label>Intro text<textarea id="fu-intro">${esc(f.intro_text || "")}</textarea></label>
        <label>Notes<textarea id="fu-notes">${esc(f.notes || "")}</textarea></label>

        <div class="fu-row">
          <button class="primary" id="fu-save-config">Зберегти воронку</button>
          <button id="fu-seed-legke">Заповнити приклад “Легке тіло БВ”</button>
        </div>
      </div>
    `;
  }

  function stepsHtml(){
    return `
      <div class="fu-card">
        <h4>Кроки воронки</h4>
        <div class="fu-muted">Це контент сценарію. Бек не знає “Легке тіло” — він читає ці кроки з БД.</div>
        ${state.steps.map(stepCard).join("") || `<div class="fu-muted">Кроків ще немає.</div>`}

        <div class="fu-card">
          <h4>Додати / оновити крок</h4>
          <div class="fu-grid3">
            <label>step_key<input id="st-key" value="intro"></label>
            <label>order<input id="st-order" value="${state.steps.length + 1}"></label>
            <label>active<select id="st-active"><option value="1">1</option><option value="0">0</option></select></label>
          </div>
          <div class="fu-grid">
            <label>trigger_stage<input id="st-trigger" value="tg_started"></label>
            <label>next_stage<input id="st-next" value="intro_sent"></label>
          </div>
          <label>message_text<textarea id="st-message">🌿 Текст повідомлення</textarea></label>
          <div class="fu-grid">
            <label>button_text<input id="st-button" value="🌿 Почати"></label>
            <label>button_url<input id="st-url" value=""></label>
          </div>
          <label>delay_minutes<input id="st-delay" value="0"></label>
          <button class="primary" id="st-save">Зберегти крок</button>
        </div>
      </div>
    `;
  }

  function stepCard(st){
    return `
      <div class="fu-card">
        <div class="fu-row">
          <b>${esc(st.step_order)}. ${esc(st.step_key)}</b>
          <span class="fu-pill">${esc(st.trigger_stage)} → ${esc(st.next_stage)}</span>
          <button data-edit-step="${esc(st.step_key)}">Редагувати</button>
          <button class="danger" data-del-step="${esc(st.step_key)}">Видалити</button>
        </div>
        <div>${esc((st.message_text || "").slice(0,220))}</div>
        ${st.button_text ? `<div class="fu-muted">Button: ${esc(st.button_text)} ${st.button_url ? "→ " + esc(st.button_url) : ""}</div>` : ""}
      </div>
    `;
  }

  function leadsHtml(){
    return `
      <div class="fu-card">
        <h4>Ліди з Instagram / AI drafts</h4>
        <div class="fu-row">
          <button id="fu-refresh-leads">Оновити ліди</button>
        </div>
        <table class="fu-table">
          <thead><tr><th>Дата</th><th>Джерело</th><th>User</th><th>Текст</th><th>Matched</th><th>Дія</th></tr></thead>
          <tbody>
            ${state.leads.slice(0,20).map(l => `
              <tr>
                <td>${esc(l.created_at || "")}</td>
                <td>${esc(l.source_table || "")}</td>
                <td>${esc(l.source_user_id || "")}<br><span class="fu-muted">${esc(l.username || "")}</span></td>
                <td>${esc((l.text || "").slice(0,160))}</td>
                <td>${esc(l.matched_plan_key || "")}</td>
                <td>
                  <button class="primary" data-start-lead="${esc(l.source_user_id || "")}" data-lead-text="${esc(l.text || "")}" data-lead-user="${esc(l.username || "")}">
                    Запустити
                  </button>
                </td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      </div>
    `;
  }

  function sessionsHtml(){
    return `
      <div class="fu-card">
        <h4>Запущені sessions</h4>
        <div class="fu-row"><button id="fu-refresh-sessions">Оновити sessions</button></div>
        <table class="fu-table">
          <thead><tr><th>ID</th><th>Funnel</th><th>User</th><th>Status</th><th>Link / DM</th></tr></thead>
          <tbody>
            ${state.sessions.slice(0,20).map(s => `
              <tr>
                <td>${esc(s.id)}</td>
                <td>${esc(s.funnel_key)}<br><span class="fu-muted">${esc(s.funnel_name)}</span></td>
                <td>${esc(s.source_user_id)}</td>
                <td>${esc(s.status)}<br><span class="fu-muted">${esc(s.stage)}</span></td>
                <td>
                  <button data-copy="${esc(s.dm_text || "")}">Copy DM</button>
                  <div class="fu-muted">${esc(s.telegram_deeplink || "")}</div>
                </td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      </div>
    `;
  }

  function bind(){
    const close = document.getElementById("fu-close");
    if (close) close.onclick = () => {
      const r = root();
      if (r.id === ROOT_ID) r.innerHTML = "";
      else r.remove();
    };

    document.getElementById("fu-load").onclick = async () => {
      state.selectedKey = val("fu-select-key");
      await loadSelected(true);
      await render();
    };

    document.getElementById("fu-status").onclick = async () => show(await api("/api/funnels/runtime/status"));

    document.getElementById("fu-save-config").onclick = saveConfig;
    document.getElementById("fu-seed-legke").onclick = seedLegke;
    document.getElementById("st-save").onclick = saveStep;

    document.getElementById("fu-refresh-leads").onclick = async () => { await loadLeads(true); await render(); };
    document.getElementById("fu-refresh-sessions").onclick = async () => { await loadSessions(true); await render(); };

    document.querySelectorAll("[data-edit-step]").forEach(b => {
      b.onclick = () => {
        const key = b.getAttribute("data-edit-step");
        const st = state.steps.find(x => x.step_key === key);
        if (!st) return;
        document.getElementById("st-key").value = st.step_key || "";
        document.getElementById("st-order").value = st.step_order || 100;
        document.getElementById("st-active").value = String(st.active ?? 1);
        document.getElementById("st-trigger").value = st.trigger_stage || "";
        document.getElementById("st-next").value = st.next_stage || "";
        document.getElementById("st-message").value = st.message_text || "";
        document.getElementById("st-button").value = st.button_text || "";
        document.getElementById("st-url").value = st.button_url || "";
        document.getElementById("st-delay").value = st.delay_minutes || 0;
      };
    });

    document.querySelectorAll("[data-del-step]").forEach(b => {
      b.onclick = async () => {
        const step_key = b.getAttribute("data-del-step");
        const res = await api(`/api/funnels/configs/${encodeURIComponent(state.selectedKey)}/steps/delete`, {
          method:"POST", headers:{"Content-Type":"application/json"},
          body:JSON.stringify({step_key})
        });
        show(res);
        await loadSelected(false);
        await render();
      };
    });

    document.querySelectorAll("[data-start-lead]").forEach(b => {
      b.onclick = async () => {
        const source_user_id = b.getAttribute("data-start-lead") || "";
        const source_message = b.getAttribute("data-lead-text") || "";
        const source_username = b.getAttribute("data-lead-user") || "";
        const funnel_key = state.selectedKey || val("fu-key");
        const res = await api("/api/funnels/runtime/manual-start", {
          method:"POST", headers:{"Content-Type":"application/json"},
          body:JSON.stringify({
            funnel_key,
            source_platform:"instagram",
            source_user_id,
            source_username,
            source_message,
            mode:"draft"
          })
        });
        show(res);
        await loadSessions(false);
        await render();
      };
    });

    document.querySelectorAll("[data-copy]").forEach(b => {
      b.onclick = async () => {
        const text = b.getAttribute("data-copy") || "";
        try { await navigator.clipboard.writeText(text); b.textContent = "Copied"; }
        catch(e){ show({ok:false, error:"clipboard_failed", text}); }
      };
    });
  }

  async function saveConfig(){
    const payload = {
      funnel_key: val("fu-key"),
      funnel_name: val("fu-name"),
      active: Number(val("fu-active") || 1),
      priority: Number(val("fu-priority") || 100),
      source_platform: val("fu-source") || "instagram",
      telegram_bot_username: val("fu-bot"),
      trigger_keywords: val("fu-triggers"),
      content_keywords: val("fu-content-keywords"),
      telegram_channel_url: val("fu-channel"),
      next_funnel_key: val("fu-next"),
      dm_template: val("fu-dm"),
      intro_text: val("fu-intro"),
      notes: val("fu-notes")
    };

    const res = await api("/api/funnels/configs/upsert", {
      method:"POST", headers:{"Content-Type":"application/json"},
      body:JSON.stringify(payload)
    });

    state.selectedKey = payload.funnel_key;
    show(res);
    await render();
  }

  async function saveStep(){
    const funnel_key = state.selectedKey || val("fu-key");
    if (!funnel_key) return show({ok:false, error:"Спочатку збережи/вибери воронку"});

    const payload = {
      step_key: val("st-key"),
      step_order: Number(val("st-order") || 100),
      active: Number(val("st-active") || 1),
      trigger_stage: val("st-trigger"),
      next_stage: val("st-next"),
      message_text: val("st-message"),
      button_text: val("st-button"),
      button_url: val("st-url"),
      delay_minutes: Number(val("st-delay") || 0)
    };

    const res = await api(`/api/funnels/configs/${encodeURIComponent(funnel_key)}/steps/upsert`, {
      method:"POST", headers:{"Content-Type":"application/json"},
      body:JSON.stringify(payload)
    });

    show(res);
    state.selectedKey = funnel_key;
    await loadSelected(false);
    await render();
  }

  async function seedLegke(){
    document.getElementById("fu-key").value = "legke_tilo_bv";
    document.getElementById("fu-name").value = "Легке тіло БВ";
    document.getElementById("fu-priority").value = "1";
    document.getElementById("fu-source").value = "instagram";
    document.getElementById("fu-triggers").value = "вага, схуднення, худнути, тіло, зайва вага, не можу схуднути";
    document.getElementById("fu-content-keywords").value = "вага, тіло, схуднення, БВ, безкоштовний сеанс";
    document.getElementById("fu-dm").value =
`🌿 Я підготувала для тебе безкоштовний ознайомчий сеанс «{{funnel_name}}».

Там ти зрозумієш:
• чому тіло може тримати вагу
• як стрес і напруга впливають на схуднення
• як мʼяко почати відновлення через метод БВ

👇 Натисни й почни тут:
{{telegram_deeplink}}`;
    document.getElementById("fu-intro").value =
`🌿 Простір м’якого відновлення тіла через метод БВ

Тут ти:
• пройдеш безкоштовний сеанс
• зрозумієш причини набору ваги
• відчуєш реакцію тіла
• познайомишся з методом БВ

👇 Натисни «Почати»`;
    document.getElementById("fu-notes").value = "Instagram keyword Вага → Telegram bot → канал → переднавчання БВ";
    await saveConfig();
  }

  function show(obj){
    state.last = obj;
    const el = document.getElementById("fu-output");
    if (el) el.textContent = JSON.stringify(obj, null, 2);
  }

  function boot(){
    css();
    window.renderFunnelsNativeTab = render;

    const nativeRoot = document.getElementById(ROOT_ID);
    if (nativeRoot) return;

    if (!document.getElementById("funnels-floating-btn")) {
      const btn = document.createElement("button");
      btn.id = "funnels-floating-btn";
      btn.textContent = "Funnels";
      btn.style.cssText = "position:fixed;right:18px;bottom:82px;z-index:99999;border:0;border-radius:999px;padding:12px 16px;background:#111;color:#fff;box-shadow:0 10px 30px rgba(0,0,0,.22);cursor:pointer;font-weight:800";
      btn.onclick = render;
      document.body.appendChild(btn);
    }
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
  else boot();

  window.openFunnelsUiV1 = render;
})();
