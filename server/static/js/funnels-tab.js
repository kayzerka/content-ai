(function(){
  const ROOT_ID = "funnels-native-root";

  // LOCAL_AUTO_BACKUP_FUNNELS_V1
  async function autoBackupFunnels(reason){
    try{
      const r = await fetch("/api/funnels/backup/auto_save_all", {
        method: "POST",
        headers: {"Content-Type":"application/json"},
        body: JSON.stringify({reason: reason || "funnels_save"})
      });

      const j = await r.json().catch(()=>({ok:false}));
      console.log("[funnels auto backup]", reason, j);
      return j;
    }catch(e){
      console.error("[funnels auto backup failed]", e);
      return {ok:false,error:String(e)};
    }
  }


  const PANEL_ID = "funnels-ui-v2-panel";

  let state = {
    view: "list",
    selectedKey: "",
    funnels: [],
    current: null,
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


  function show(x){
    const el = document.getElementById("fu-raw");
    const text = JSON.stringify(x || {}, null, 2);
    if (el) el.textContent = text;
    else console.log("[funnels show]", x);
  }

  function esc(s){
    return String(s == null ? "" : s)
      .replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
  }

  function val(id){ return document.getElementById(id)?.value || ""; }

  function css(){
    if (document.getElementById("funnels-v2-style")) return;
    const st = document.createElement("style");
    st.id = "funnels-v2-style";
    st.textContent = `
      #${ROOT_ID}, #${PANEL_ID}{background:#fff;color:#111;font-family:system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
      #${ROOT_ID}{padding:16px}
      #${PANEL_ID}{
        position:fixed;right:18px;bottom:100px;width:980px;max-width:calc(100vw - 36px);
        max-height:84vh;overflow:auto;z-index:99999;border:1px solid #ddd;border-radius:18px;
        box-shadow:0 20px 70px rgba(0,0,0,.32);padding:16px;
      }
      .fu-head{display:flex;justify-content:space-between;align-items:flex-start;gap:12px;margin-bottom:12px}
      .fu-card{border:1px solid #eee;border-radius:14px;padding:12px;margin:10px 0;background:#fafafa}
      .fu-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px}
      .fu-grid3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px}
      .fu-row{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin:8px 0}
      .fu-muted{color:#666;font-size:12px}
      .fu-pill{display:inline-block;border:1px solid #ddd;border-radius:999px;padding:2px 8px;font-size:12px;background:#fff}
      .fu-on{background:#eafff1;border-color:#b8e8c7;color:#087b2f}
      .fu-off{background:#fff0f0;border-color:#f0caca;color:#9b0000}
      input,textarea,select{
        box-sizing:border-box;border:1px solid #ddd;border-radius:10px;padding:9px;margin:4px 0;
        background:#fff;color:#111;font:inherit;width:100%;
      }
      textarea{min-height:72px;resize:vertical;font-size:13px}
      button{border:1px solid #ddd;border-radius:10px;background:#f7f7f7;padding:8px 10px;cursor:pointer;font-weight:700}
      button.primary{background:#111;color:#fff;border-color:#111}
      button.danger{background:#fff2f2;color:#900;border-color:#f0caca}
      button.good{background:#eafff1;color:#087b2f;border-color:#b8e8c7}
      .fu-table{width:100%;border-collapse:collapse;font-size:13px}
      .fu-table th,.fu-table td{border-bottom:1px solid #eee;padding:8px;text-align:left;vertical-align:top}
      pre{white-space:pre-wrap;background:#f6f6f6;border-radius:12px;padding:10px;font-size:12px;max-height:220px;overflow:auto}
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

  async function loadAll(){
    const funnels = await api("/api/funnels/configs/list");
    state.funnels = funnels.items || [];
    await api("/api/funnels/leads/ingest", {
      method:"POST",
      headers:{"Content-Type":"application/json"},
      body:JSON.stringify({limit:500})
    });
    const leads = await api("/api/funnels/leads/list_safe?limit=100");
    state.leads = leads.items || [];
    const sessions = await api("/api/funnels/runtime/sessions?limit=50");
    state.sessions = sessions.items || [];
  }

  async function loadOne(key){
    if (!key) return;
    const res = await api(`/api/funnels/configs/by-key/${encodeURIComponent(key)}`);
    state.current = res.item || null;
    state.steps = res.steps || [];
    state.selectedKey = key;
  }

  async function render(){
    css();
    await loadAll();

    const r = root();
    r.innerHTML = `
      <div class="fu-head">
        <div>
          <h3 style="margin:0">🧲 Конструктор воронок</h3>
          <div class="fu-muted">Створення з нуля, редагування, статус, кроки, ручний запуск лідів.</div>
        </div>
        <button id="fu-close">×</button>
      </div>

      <div class="fu-row">
        <button class="primary" id="fu-new">➕ Нова воронка</button>
        <button id="fu-list">📋 Всі воронки</button>
        <button id="fu-leads">👥 Ліди</button>
        <button id="fu-sessions">🧾 Sessions</button>
        <button id="fu-status">Status</button>
      </div>

      ${state.view === "edit" ? editorHtml() : ""}
      ${state.view === "steps" ? stepsHtml() : ""}
      ${state.view === "leads" ? leadsHtml() : ""}
      ${state.view === "sessions" ? sessionsHtml() : ""}

      ${state.view === "list" ? listHtml() : ""}

      <div class="fu-card">
        <h4>Raw output</h4>
        <pre id="fu-output">${esc(JSON.stringify(state.last || {}, null, 2))}</pre>
      </div>
    `;

    bind();
  }

  function listHtml(){
    return `
      <div class="fu-card">
        <h4>Всі створені воронки</h4>
        <table class="fu-table">
          <thead>
            <tr>
              <th>Статус</th>
              <th>Назва</th>
              <th>funnel_key</th>
              <th>Тригери</th>
              <th>Дія</th>
            </tr>
          </thead>
          <tbody>
            ${state.funnels.map(f => `
              <tr>
                <td><span class="fu-pill ${Number(f.active) ? "fu-on" : "fu-off"}">${Number(f.active) ? "active" : "inactive"}</span></td>
                <td><b>${esc(f.funnel_name || "")}</b></td>
                <td><code>${esc(f.funnel_key || "")}</code></td>
                <td>${esc((f.trigger_keywords || "").slice(0,120))}</td>
                <td>
                  <button data-edit="${esc(f.funnel_key)}">Редагувати</button>
                  <button data-steps="${esc(f.funnel_key)}">Кроки</button>
                  <button data-toggle="${esc(f.funnel_key)}" data-active="${Number(f.active) ? 0 : 1}">
                    ${Number(f.active) ? "Деактивувати" : "Активувати"}
                  </button>
                </td>
              </tr>
            `).join("") || `<tr><td colspan="5" class="fu-muted">Ще немає створених воронок.</td></tr>`}
          </tbody>
        </table>
      </div>
    `;
  }

  function editorHtml(){
    const f = state.current || {};
    return `
      <div class="fu-card">
        <h4>${f.funnel_key ? "Редагувати воронку" : "Створити нову воронку з нуля"}</h4>

        <div class="fu-grid3">
          <label>funnel_key<input id="fu-key" value="${esc(f.funnel_key || "")}" placeholder="naprklad_bv_intro"></label>
          <label>Назва<input id="fu-name" value="${esc(f.funnel_name || "")}" placeholder="Назва воронки"></label>
          <label>Активна<select id="fu-active"><option value="1" ${String(f.active ?? 1)==="1"?"selected":""}>1</option><option value="0" ${String(f.active)==="0"?"selected":""}>0</option></select></label>
        </div>

        <div class="fu-grid3">
          <label>Пріоритет<input id="fu-priority" value="${esc(f.priority || 100)}"></label>
          <label>Платформа<input id="fu-source" value="${esc(f.source_platform || "instagram")}"></label>
          <label>Telegram bot username<input id="fu-bot" value="${esc(f.telegram_bot_username || "")}" placeholder="без @"></label>
        </div>

        <label>Trigger keywords<textarea id="fu-triggers" placeholder="слова, які запускають воронку">${esc(f.trigger_keywords || "")}</textarea></label>
        <label>Content keywords<textarea id="fu-content-keywords">${esc(f.content_keywords || "")}</textarea></label>

        <div class="fu-grid">
          <label>Telegram channel URL<input id="fu-channel" value="${esc(f.telegram_channel_url || "")}"></label>
          <label>Next funnel key<input id="fu-next" value="${esc(f.next_funnel_key || "")}"></label>
        </div>

        <label>DM template <span class="fu-muted">{{funnel_name}}, {{telegram_deeplink}}, {{source_user_id}}, {{source_message}}</span>
          <textarea id="fu-dm">${esc(f.dm_template || "")}</textarea>
        </label>

        <label>Intro text<textarea id="fu-intro">${esc(f.intro_text || "")}</textarea></label>
        <label>Notes<textarea id="fu-notes">${esc(f.notes || "")}</textarea></label>

        <div class="fu-row">
          <button class="primary" id="fu-save">💾 Зберегти</button>
          <button id="fu-cancel">Назад</button>
        </div>
      </div>
    `;
  }

  function stepsHtml(){
    const f = state.current || {};
    return `
      <div class="fu-card">
        <h4>Кроки: ${esc(f.funnel_name || f.funnel_key || "")}</h4>
        <div class="fu-muted">Кроки зберігаються окремо в БД і редагуються після створення воронки.</div>

        ${state.steps.map(st => `
          <div class="fu-card">
            <div class="fu-row">
              <b>${esc(st.step_order)}. ${esc(st.step_key)}</b>
              <span class="fu-pill">${esc(st.trigger_stage)} → ${esc(st.next_stage)}</span>
              <button data-edit-step="${esc(st.step_key)}">Редагувати</button>
              <button class="danger" data-delete-step="${esc(st.step_key)}">Видалити</button>
            </div>
            <div>${esc((st.message_text || "").slice(0,240))}</div>
            <div class="fu-muted">${esc(st.button_text || "")} ${st.button_url ? "→ " + esc(st.button_url) : ""}</div>
          </div>
        `).join("") || `<div class="fu-muted">Кроків ще немає.</div>`}

        <div class="fu-card">
          <h4>Додати / оновити крок</h4>
          <div class="fu-grid3">
            <label>step_key<input id="st-key" placeholder="intro"></label>
            <label>Порядок<input id="st-order" value="${state.steps.length + 1}"></label>
            <label>Активний<select id="st-active"><option value="1">1</option><option value="0">0</option></select></label>
          </div>
          <div class="fu-grid">
            <label>trigger_stage<input id="st-trigger" placeholder="tg_started"></label>
            <label>next_stage<input id="st-next" placeholder="intro_sent"></label>
          </div>
          <label>message_text<textarea id="st-message"></textarea></label>
          <div class="fu-grid">
            <label>button_text<input id="st-button"></label>
            <label>button_url<input id="st-url"></label>
          </div>
          <label>delay_minutes<input id="st-delay" value="0"></label>
          <div class="fu-row">
            <button class="primary" id="st-save">💾 Зберегти крок</button>
            <button id="st-back">Назад</button>
          </div>
        </div>
      </div>
    `;
  }

  function leadsHtml(){
    return `
      <div class="fu-card">
        <h4>Ліди</h4>
        <div class="fu-row">
          <button class="primary" id="fu-ingest-leads">🔄 Оновити ліди з Instagram</button>
        </div>
        <table class="fu-table">
          <thead><tr><th>Дата</th><th>Джерело</th><th>User</th><th>Текст</th><th>Matched</th><th>Запуск</th></tr></thead>
          <tbody>
            ${state.leads.map(l => `
              <tr>
                <td>${esc(l.created_at || "")}</td>
                <td>${esc(l.source_table || "")}</td>
                <td>${esc(l.source_user_id || l.external_user_id || "")}<br><span class="fu-muted">${esc(l.username || "")}</span></td>
                <td>${esc((l.text || "").slice(0,140))}</td>
                <td>${esc(l.matched_plan_key || l.matched_funnel_key || "")}</td>
                <td>
                  <select data-funnel-select="${esc(l.source_user_id || l.external_user_id || "")}">
                    ${state.funnels.map(f => `<option value="${esc(f.funnel_key)}" ${f.funnel_key === l.matched_plan_key ? "selected" : ""}>${esc(f.funnel_name || f.funnel_key)}</option>`).join("")}
                  </select>
                  <button class="primary" data-start-lead="${esc(l.source_user_id || l.external_user_id || "")}" data-lead-text="${esc(l.text || "")}" data-lead-user="${esc(l.username || "")}">Запустити</button>
                </td>
              </tr>
            `).join("") || `<tr><td colspan="6" class="fu-muted">Лідів не знайдено.</td></tr>`}
          </tbody>
        </table>
      </div>
    `;
  }

  function sessionsHtml(){
    return `
      <div class="fu-card">
        <h4>Sessions</h4>
        <table class="fu-table">
          <thead><tr><th>ID</th><th>Воронка</th><th>User</th><th>Status</th><th>DM</th></tr></thead>
          <tbody>
            ${state.sessions.map(s => `
              <tr>
                <td>${esc(s.id)}</td>
                <td>${esc(s.funnel_key)}<br><span class="fu-muted">${esc(s.funnel_name)}</span></td>
                <td>${esc(s.source_user_id)}</td>
                <td>${esc(s.status)}<br><span class="fu-muted">${esc(s.stage)}</span></td>
                <td><button data-copy="${esc(s.dm_text || "")}">Copy DM</button><br><span class="fu-muted">${esc(s.telegram_deeplink || "")}</span></td>
              </tr>
            `).join("") || `<tr><td colspan="5" class="fu-muted">Sessions ще немає.</td></tr>`}
          </tbody>
        </table>
      </div>
    `;
  }

  function backupHtml(){ return ""; }

  async function exportBackup(){
    return show({ok:true, skipped:true, reason:"backup_ui_disabled"});
  }

  async function downloadBackup(){
    return show({ok:true, skipped:true, reason:"backup_download_disabled"});
  }

  async function snapshotBackup(reason){
    return show({ok:true, skipped:true, reason:"telegram_snapshot_disabled"});
  }

  async function autoSnapshotBackup(reason){
    return {ok:true, skipped:true, reason:"auto_backup_disabled"};
  }

  async function importBackup(){
    return show({ok:true, skipped:true, reason:"manual_import_disabled"});
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
      method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(payload)
    });
    show(res);

    if (res && res.ok) {
      await autoBackupFunnels("after_save_config");
    }

    state.view = "list";
    state.current = null;
    await render();
  }

  async function toggleFunnel(key, active){
    const one = await api(`/api/funnels/configs/by-key/${encodeURIComponent(key)}`);
    const f = one.item || {};
    f.active = Number(active);
    const res = await api("/api/funnels/configs/upsert", {
      method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(f)
    });
    show(res);
    await autoBackupFunnels("after_toggle_funnel");
    await render();
  }

  async function saveStep(){
    const key = state.selectedKey;
    const payload = {
      funnel_key: key,
      step_key: val("st-key"),
      step_order: Number(val("st-order") || 100),
      active: Number(val("st-active") || 1),
      trigger_stage: val("st-trigger"),
      next_stage: val("st-next"),
      message_text: val("st-message"),
      button_text: val("st-button"),
      button_url: val("st-url"),
      delay_minutes: Number(val("st-delay") || 0),
      settings_json: "{}"
    };
    const res = await api(`/api/funnels/steps/upsert`, {
      method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(payload)
    });
    show(res);
    await autoBackupFunnels("after_save_step");
    await loadOne(key);
    await render();
  }

  function bind(){
    const close = document.getElementById("fu-close");
    if (close) close.onclick = () => {
      const r = root();
      if (r.id === ROOT_ID) r.innerHTML = "";
      else r.remove();
    };

    document.getElementById("fu-new").onclick = async () => {
      state.view = "edit";
      state.current = {};
      await render();
    };

    document.getElementById("fu-list").onclick = async () => { state.view = "list"; await render(); };
    document.getElementById("fu-leads").onclick = async () => { state.view = "leads"; await render(); };
    document.getElementById("fu-sessions").onclick = async () => { state.view = "sessions"; await render(); };
    document.getElementById("fu-status").onclick = async () => show(await api("/api/funnels/runtime/status"));
    var ingestLeadsBtn = document.getElementById("fu-ingest-leads");
    if (ingestLeadsBtn) ingestLeadsBtn.onclick = async () => {
      const res = await api("/api/funnels/leads/ingest", {
        method:"POST",
        headers:{"Content-Type":"application/json"},
        body:JSON.stringify({limit:1000})
      });
      show(res);
      await render();
    };

    document.querySelectorAll("[data-edit]").forEach(b => {
      b.onclick = async () => {
        await loadOne(b.getAttribute("data-edit"));
        state.view = "edit";
        await render();
      };
    });

    document.querySelectorAll("[data-steps]").forEach(b => {
      b.onclick = async () => {
        await loadOne(b.getAttribute("data-steps"));
        state.view = "steps";
        await render();
      };
    });

    document.querySelectorAll("[data-toggle]").forEach(b => {
      b.onclick = async () => toggleFunnel(b.getAttribute("data-toggle"), b.getAttribute("data-active"));
    });

    const save = document.getElementById("fu-save");
    if (save) save.onclick = saveConfig;

    const cancel = document.getElementById("fu-cancel");
    if (cancel) cancel.onclick = async () => { state.view = "list"; await render(); };

    const stBack = document.getElementById("st-back");
    if (stBack) stBack.onclick = async () => { state.view = "list"; await render(); };

    const stSave = document.getElementById("st-save");
    if (stSave) stSave.onclick = saveStep;

    document.querySelectorAll("[data-edit-step]").forEach(b => {
      b.onclick = () => {
        const step = state.steps.find(x => x.step_key === b.getAttribute("data-edit-step"));
        if (!step) return;
        document.getElementById("st-key").value = step.step_key || "";
        document.getElementById("st-order").value = step.step_order || 100;
        document.getElementById("st-active").value = String(step.active ?? 1);
        document.getElementById("st-trigger").value = step.trigger_stage || "";
        document.getElementById("st-next").value = step.next_stage || "";
        document.getElementById("st-message").value = step.message_text || "";
        document.getElementById("st-button").value = step.button_text || "";
        document.getElementById("st-url").value = step.button_url || "";
        document.getElementById("st-delay").value = step.delay_minutes || 0;
      };
    });

    document.querySelectorAll("[data-delete-step]").forEach(b => {
      b.onclick = async () => {
        const step_key = b.getAttribute("data-delete-step");
        const res = await api(`/api/funnels/configs/${encodeURIComponent(state.selectedKey)}/steps/delete`, {
          method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({step_key})
        });
        show(res);
        await loadOne(state.selectedKey);
        await render();
      };
    });

    document.querySelectorAll("[data-start-lead]").forEach(b => {
      b.onclick = async () => {
        const user = b.getAttribute("data-start-lead");
        const select = document.querySelector(`[data-funnel-select="${CSS.escape(user)}"]`);
        const funnel_key = select?.value || "";
        const res = await api("/api/funnels/runtime/manual-start", {
          method:"POST", headers:{"Content-Type":"application/json"},
          body:JSON.stringify({
            funnel_key,
            source_platform:"instagram",
            source_user_id:user,
            source_username:b.getAttribute("data-lead-user") || "",
            source_message:b.getAttribute("data-lead-text") || "",
            mode:"draft"
          })
        });
        show(res);
        await autoBackupFunnels("after_manual_start_lead");
        state.view = "sessions";
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
})();

// === FUNNEL STEPS BUILDER UI V1 ===
(function(){
  if (window.__FUNNEL_STEPS_BUILDER_UI_V1__) return;
  window.__FUNNEL_STEPS_BUILDER_UI_V1__ = true;

  function apiJson(url, opts){
    return fetch(url, opts || {}).then(async r => {
      const t = await r.text();
      try { return JSON.parse(t); } catch(e){ return {ok:false, raw:t, status:r.status}; }
    });
  }

  function esc(s){
    return String(s == null ? "" : s)
      .replaceAll("&","&amp;")
      .replaceAll("<","&lt;")
      .replaceAll(">","&gt;")
      .replaceAll('"',"&quot;");
  }

  function getFunnelKeyFromStepsButton(btn){
    const tr = btn.closest("tr");

    if (tr) {
      const cells = Array.from(tr.querySelectorAll("td"));
      // у таблиці: статус | назва | funnel_key | тригери | дії
      if (cells[2]) {
        const key = (cells[2].textContent || "").trim();
        if (key && key !== "active") return key;
      }

      const txt = tr.innerText || "";
      const matches = txt.match(/\b[a-z][a-z0-9_]{2,}\b/g) || [];
      const bad = new Set(["active","inactive","edit","status","button"]);
      const good = matches.find(x => x.includes("_") && !bad.has(x.toLowerCase()));
      if (good) return good;
    }

    const row = btn.closest("[data-funnel-key]");
    if (row) return row.getAttribute("data-funnel-key");

    return prompt("Введи funnel_key", "shudnennia_bv") || "";
  }

  async function openStepsBuilder(funnelKey){
    funnelKey = String(funnelKey || "").trim();
    if (!funnelKey) return;

    let res = await apiJson(`/api/funnels/steps/list?funnel_key=${encodeURIComponent(funnelKey)}`);
    let items = res.items || res.steps || [];

    const old = document.getElementById("funnel-steps-builder-modal");
    if (old) old.remove();

    const modal = document.createElement("div");
    modal.id = "funnel-steps-builder-modal";
    modal.style.cssText = `
      position:fixed; inset:0; z-index:99999; background:rgba(0,0,0,.45);
      display:flex; align-items:flex-start; justify-content:center; overflow:auto; padding:40px 16px;
    `;

    modal.innerHTML = `
      <div style="background:#fff;width:min(980px,96vw);border-radius:18px;padding:20px;box-shadow:0 20px 60px rgba(0,0,0,.25);">
        <div style="display:flex;justify-content:space-between;gap:12px;align-items:center;margin-bottom:14px;">
          <div>
            <h2 style="margin:0;font-size:22px;">🧩 Кроки воронки</h2>
            <div style="color:#667085;font-size:13px;">funnel_key: <b>${esc(funnelKey)}</b></div>
          </div>
          <button id="fsb-close" style="border:1px solid #ddd;border-radius:10px;padding:8px 12px;background:#fff;cursor:pointer;">×</button>
        </div>

        <div style="background:#f8fafc;border:1px solid #e5e7eb;border-radius:14px;padding:14px;margin-bottom:16px;">
          <h3 style="margin:0 0 10px;">Створити / редагувати крок</h3>

          <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;">
            <label><b>step_key</b><input id="fsb-step-key" value="start" style="width:100%;padding:10px;border:1px solid #ddd;border-radius:10px;"></label>
            <label><b>Тип кроку</b>
              <select id="fsb-step-type" style="width:100%;padding:10px;border:1px solid #ddd;border-radius:10px;">
                <option value="send_message">send_message</option>
                <option value="send_free_gift">send_free_gift</option>
                <option value="send_ai_message">send_ai_message</option>
                <option value="wait_delay">wait_delay</option>
              </select>
            </label>
            <label><b>Порядок</b><input id="fsb-step-order" value="1" type="number" style="width:100%;padding:10px;border:1px solid #ddd;border-radius:10px;"></label>

            <label><b>Активний</b>
              <select id="fsb-active" style="width:100%;padding:10px;border:1px solid #ddd;border-radius:10px;">
                <option value="1">1</option>
                <option value="0">0</option>
              </select>
            </label>
            <label><b>trigger_stage</b><input id="fsb-trigger-stage" value="tg_started" style="width:100%;padding:10px;border:1px solid #ddd;border-radius:10px;"></label>
            <label><b>next_stage</b><input id="fsb-next-stage" value="intro_video_sent" style="width:100%;padding:10px;border:1px solid #ddd;border-radius:10px;"></label>
          </div>

          <label style="display:block;margin-top:12px;"><b>message_text</b>
            <textarea id="fsb-message-text" style="width:100%;min-height:120px;padding:10px;border:1px solid #ddd;border-radius:10px;">🌿 Вітаю тебе у просторі «Схуднення БВ».

Перед тим як перейти до сеансу — подивись коротке пояснення методу БВ.</textarea>
          </label>

          <div style="display:grid;grid-template-columns:1fr 1fr 140px;gap:12px;margin-top:12px;">
            <label><b>button_text</b><input id="fsb-button-text" value="🎥 Дивитися пояснення" style="width:100%;padding:10px;border:1px solid #ddd;border-radius:10px;"></label>
            <label><b>button_url</b><input id="fsb-button-url" placeholder="https://t.me/..." style="width:100%;padding:10px;border:1px solid #ddd;border-radius:10px;"></label>
            <label><b>delay_minutes</b><input id="fsb-delay" value="0" type="number" style="width:100%;padding:10px;border:1px solid #ddd;border-radius:10px;"></label>
          </div>

          <div style="display:flex;gap:10px;margin-top:14px;">
            <button id="fsb-save" style="background:#111;color:#fff;border:0;border-radius:10px;padding:10px 16px;font-weight:700;cursor:pointer;">💾 Зберегти крок</button>\n            <button id="fsb-add-new" style="background:#16a34a;color:#fff;border:0;border-radius:10px;padding:10px 16px;font-weight:700;cursor:pointer;">➕ Додати крок</button>
            <button id="fsb-preset-1" style="border:1px solid #ddd;border-radius:10px;padding:10px;background:#fff;cursor:pointer;">Preset STEP 1</button>
            <button id="fsb-preset-2" style="border:1px solid #ddd;border-radius:10px;padding:10px;background:#fff;cursor:pointer;">Preset STEP 2</button>
            <button id="fsb-preset-3" style="border:1px solid #ddd;border-radius:10px;padding:10px;background:#fff;cursor:pointer;">Preset STEP 3</button>
          </div>
        </div>

        <h3>Існуючі кроки</h3>
        <div id="fsb-list">
          ${items.length ? items.map(x => `
            <div style="border:1px solid #e5e7eb;border-radius:12px;padding:12px;margin-bottom:8px;">
              <b>${esc(x.step_order)}. ${esc(x.step_key)}</b>
              <span style="color:#667085;">trigger: ${esc(x.trigger_stage)} → next: ${esc(x.next_stage)}</span>
              <div style="white-space:pre-wrap;margin-top:6px;">${esc((x.message_text || "").slice(0,300))}</div>
            </div>
          `).join("") : `<div style="color:#667085;">Кроків ще нема.</div>`}
        </div>

        <pre id="fsb-output" style="background:#f8fafc;border-radius:12px;padding:12px;max-height:220px;overflow:auto;margin-top:14px;">{}</pre>
      </div>
    `;

    document.body.appendChild(modal);

    modal.querySelector("#fsb-close").onclick = () => modal.remove();

    function fillPreset(n){
      if (n === 1) {
        modal.querySelector("#fsb-step-key").value = "start";
        modal.querySelector("#fsb-step-type").value = "send_message";
        modal.querySelector("#fsb-step-order").value = "1";
        modal.querySelector("#fsb-trigger-stage").value = "tg_started";
        modal.querySelector("#fsb-next-stage").value = "intro_video_sent";
        modal.querySelector("#fsb-message-text").value = "🌿 Вітаю тебе у просторі «Схуднення БВ».\n\nПеред тим як перейти до сеансу — подивись коротке пояснення методу БВ.\n\nУ цьому відео ти зрозумієш:\n• чому тіло може тримати вагу\n• як нервова система впливає на вагу\n• чому проблема може бути глибшою за їжу";
        modal.querySelector("#fsb-button-text").value = "🎥 Дивитися пояснення";
        modal.querySelector("#fsb-button-url").value = "";
        modal.querySelector("#fsb-delay").value = "0";
      }
      if (n === 2) {
        modal.querySelector("#fsb-step-key").value = "free_session";
        modal.querySelector("#fsb-step-type").value = "send_free_gift";
        modal.querySelector("#fsb-step-order").value = "2";
        modal.querySelector("#fsb-trigger-stage").value = "intro_video_sent";
        modal.querySelector("#fsb-next-stage").value = "free_session_sent";
        modal.querySelector("#fsb-message-text").value = "🌿 Тепер переходь до безкоштовного ознайомчого сеансу БВ.\n\nПід час перегляду просто спостерігай за тілом:\n• що відгукується\n• де є напруга\n• які думки або емоції піднімаються";
        modal.querySelector("#fsb-button-text").value = "🌿 Перейти до сеансу";
        modal.querySelector("#fsb-button-url").value = "";
        modal.querySelector("#fsb-delay").value = "0";
      }
      if (n === 3) {
        modal.querySelector("#fsb-step-key").value = "prelearning";
        modal.querySelector("#fsb-step-type").value = "send_message";
        modal.querySelector("#fsb-step-order").value = "3";
        modal.querySelector("#fsb-trigger-stage").value = "free_session_sent";
        modal.querySelector("#fsb-next-stage").value = "prelearning_sent";
        modal.querySelector("#fsb-message-text").value = "🌿 Якщо тобі відгукнувся цей шлях — я запрошую тебе в простір переднавчання БВ.\n\nТам ми глибше працюємо з тілом, реакціями нервової системи і внутрішніми причинами ваги.\n\n👇 Переходь у переднавчання БВ";
        modal.querySelector("#fsb-button-text").value = "🔓 Перейти в переднавчання";
        modal.querySelector("#fsb-button-url").value = "";
        modal.querySelector("#fsb-delay").value = "0";
      }
    }

    
    modal.querySelector("#fsb-add-new").onclick = () => {
      const maxOrder = Math.max(0, ...items.map(x => Number(x.step_order || 0)));
      const nextOrder = maxOrder + 1;

      modal.querySelector("#fsb-step-key").value = `step_${nextOrder}`;
      modal.querySelector("#fsb-step-type").value = "send_message";
      modal.querySelector("#fsb-step-order").value = String(nextOrder);
      modal.querySelector("#fsb-active").value = "1";
      modal.querySelector("#fsb-trigger-stage").value = nextOrder === 1 ? "tg_started" : `step_${nextOrder-1}_sent`;
      modal.querySelector("#fsb-next-stage").value = `step_${nextOrder}_sent`;
      modal.querySelector("#fsb-message-text").value = "";
      modal.querySelector("#fsb-button-text").value = "";
      modal.querySelector("#fsb-button-url").value = "";
      modal.querySelector("#fsb-delay").value = "0";
    };


    modal.querySelector("#fsb-preset-1").onclick = () => fillPreset(1);
    modal.querySelector("#fsb-preset-2").onclick = () => fillPreset(2);
    modal.querySelector("#fsb-preset-3").onclick = () => fillPreset(3);

    modal.querySelector("#fsb-save").onclick = async () => {
      const stepType = modal.querySelector("#fsb-step-type").value;
      const payload = {
        funnel_key: funnelKey,
        step_key: modal.querySelector("#fsb-step-key").value.trim(),
        step_order: Number(modal.querySelector("#fsb-step-order").value || 1),
        active: Number(modal.querySelector("#fsb-active").value || 1),
        trigger_stage: modal.querySelector("#fsb-trigger-stage").value.trim(),
        next_stage: modal.querySelector("#fsb-next-stage").value.trim(),
        message_text: modal.querySelector("#fsb-message-text").value,
        button_text: modal.querySelector("#fsb-button-text").value,
        button_url: modal.querySelector("#fsb-button-url").value,
        delay_minutes: Number(modal.querySelector("#fsb-delay").value || 0),
        settings_json: JSON.stringify({step_type: stepType})
      };

      const save = await apiJson("/api/funnels/steps/upsert", {
        method:"POST",
        headers:{"Content-Type":"application/json"},
        body:JSON.stringify(payload)
      });

      modal.querySelector("#fsb-output").textContent = JSON.stringify(save, null, 2);

      if (save.ok && save.item) {
        const item = save.item;
        modal.querySelector("#fsb-step-key").value = item.step_key || payload.step_key || "";
        modal.querySelector("#fsb-step-order").value = item.step_order || payload.step_order || 1;
        modal.querySelector("#fsb-active").value = item.active ?? payload.active ?? 1;
        modal.querySelector("#fsb-trigger-stage").value = item.trigger_stage || payload.trigger_stage || "";
        modal.querySelector("#fsb-next-stage").value = item.next_stage || payload.next_stage || "";
        modal.querySelector("#fsb-message-text").value = item.message_text || payload.message_text || "";
        modal.querySelector("#fsb-button-text").value = item.button_text || payload.button_text || "";
        modal.querySelector("#fsb-button-url").value = item.button_url || payload.button_url || "";
        modal.querySelector("#fsb-delay").value = item.delay_minutes ?? payload.delay_minutes ?? 0;
      }

      if (save.ok) {
        await refresh();
      }
    };

    fillPreset(1);
  }

  document.addEventListener("click", function(e){
    const btn = e.target.closest("button");
    if (!btn) return;
    const txt = (btn.textContent || "").trim().toLowerCase();

    if (txt === "кроки" || txt.includes("кроки")) {
      e.preventDefault();
      e.stopPropagation();
      const key = getFunnelKeyFromStepsButton(btn);
      openStepsBuilder(key);
    }
  }, true);

  window.openFunnelStepsBuilderV1 = openStepsBuilder;
})();
