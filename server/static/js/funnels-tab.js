(function(){
  const ROOT_ID = "funnels-native-root";
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
    const leads = await api("/api/funnels/runtime/leads?limit=50");
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
        <button id="fu-backup">💾 Backup</button>
        <button id="fu-backup">💾 Backup</button>
      </div>

      ${state.view === "edit" ? editorHtml() : ""}
      ${state.view === "steps" ? stepsHtml() : ""}
      ${state.view === "leads" ? leadsHtml() : ""}
      ${state.view === "sessions" ? sessionsHtml() : ""}
      ${state.view === "backup" ? backupHtml() : ""}
      ${state.view === "backup" ? backupHtml() : ""}
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
        <table class="fu-table">
          <thead><tr><th>Дата</th><th>Джерело</th><th>User</th><th>Текст</th><th>Matched</th><th>Запуск</th></tr></thead>
          <tbody>
            ${state.leads.map(l => `
              <tr>
                <td>${esc(l.created_at || "")}</td>
                <td>${esc(l.source_table || "")}</td>
                <td>${esc(l.source_user_id || "")}<br><span class="fu-muted">${esc(l.username || "")}</span></td>
                <td>${esc((l.text || "").slice(0,140))}</td>
                <td>${esc(l.matched_plan_key || "")}</td>
                <td>
                  <select data-funnel-select="${esc(l.source_user_id || "")}">
                    ${state.funnels.map(f => `<option value="${esc(f.funnel_key)}" ${f.funnel_key === l.matched_plan_key ? "selected" : ""}>${esc(f.funnel_name || f.funnel_key)}</option>`).join("")}
                  </select>
                  <button class="primary" data-start-lead="${esc(l.source_user_id || "")}" data-lead-text="${esc(l.text || "")}" data-lead-user="${esc(l.username || "")}">Запустити</button>
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

  
  function backupHtml(){
    return `
      <div class="fu-card">
        <h4>💾 Backup / Restore воронок</h4>
        <div class="fu-muted">
          Export зберігає всі funnel_configs і funnel_steps_dynamic у JSON.
          Після Render deploy можна вставити JSON сюди й відновити воронки.
        </div>

        <div class="fu-row">
          <button class="primary" id="fu-export-backup">⬇️ Export backup</button>
          <button id="fu-download-backup">💽 Download JSON</button>
          <button class="good" id="fu-import-backup">⬆️ Import / Restore</button>
        </div>

        <textarea id="fu-backup-json" style="min-height:320px" placeholder="Тут буде backup JSON або встав сюди JSON для restore"></textarea>
      </div>
    `;
  }

  async function exportBackup(){
    const res = await api("/api/funnels/backup/export");
    show(res);
    const el = document.getElementById("fu-backup-json");
    if (el) el.value = JSON.stringify(res, null, 2);
    return res;
  }

  async function downloadBackup(){
    const res = await exportBackup();
    const blob = new Blob([JSON.stringify(res, null, 2)], {type:"application/json"});
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    const ts = new Date().toISOString().replace(/[:.]/g,"-");
    a.href = url;
    a.download = `funnels-backup-${ts}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }

  async function importBackup(){
    const raw = document.getElementById("fu-backup-json")?.value || "";
    if (!raw.trim()) return show({ok:false, error:"backup JSON is empty"});

    let payload;
    try { payload = JSON.parse(raw); }
    catch(e){ return show({ok:false, error:"invalid JSON", details:String(e)}); }

    const res = await api("/api/funnels/backup/import", {
      method:"POST",
      headers:{"Content-Type":"application/json"},
      body:JSON.stringify(payload)
    });

    show(res);
    await autoBackupFunnels("after_save_funnel");
    state.view = "list";
    await render();
  }


  
  function backupHtml(){
    return `
      <div class="fu-card">
        <h4>💾 Backup / Restore</h4>
        <div class="fu-muted">
          Backup включає: воронки, кроки, sessions, ліди, AI drafts, webhook messages.
          Автобекап тригериться після збереження воронки/кроку/ручного запуску ліда.
        </div>

        <div class="fu-row">
          <button class="primary" id="fu-export-backup">⬇️ Export JSON</button>
          <button id="fu-download-backup">💽 Download</button>
          <button class="good" id="fu-snapshot-backup">📩 Send backup to Telegram</button>
          <button class="good" id="fu-import-backup">⬆️ Restore from JSON</button>
        </div>

        <textarea id="fu-backup-json" style="min-height:320px" placeholder="Тут буде backup JSON або встав JSON для restore"></textarea>
      </div>
    `;
  }

  async function exportBackup(){
    const res = await api("/api/funnels/backup/export");
    show(res);
    const el = document.getElementById("fu-backup-json");
    if (el) el.value = JSON.stringify(res, null, 2);
    try {
      localStorage.setItem("funnels_last_backup_json", JSON.stringify(res));
      localStorage.setItem("funnels_last_backup_at", new Date().toISOString());
    } catch(e){}
    return res;
  }

  async function downloadBackup(){
    const res = await exportBackup();
    const blob = new Blob([JSON.stringify(res, null, 2)], {type:"application/json"});
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    const ts = new Date().toISOString().replace(/[:.]/g,"-");
    a.href = url;
    a.download = `funnels-backup-${ts}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }

  async function snapshotBackup(reason){
    const res = await api("/api/funnels/backup/snapshot", {
      method:"POST",
      headers:{"Content-Type":"application/json"},
      body:JSON.stringify({reason: reason || "manual"})
    });
    show(res);
    return res;
  }

  async function autoBackupFunnels(reason){
    try {
      const res = await api("/api/funnels/backup/snapshot", {
        method:"POST",
        headers:{"Content-Type":"application/json"},
        body:JSON.stringify({reason: reason || "auto"})
      });
      console.log("[funnels auto backup]", reason, res);
      return res;
    } catch(e) {
      console.warn("[funnels auto backup failed]", reason, e);
      return {ok:false, error:String(e)};
    }
  }

  async function importBackup(){
    const raw = document.getElementById("fu-backup-json")?.value || "";
    if (!raw.trim()) return show({ok:false, error:"backup JSON is empty"});

    let payload;
    try { payload = JSON.parse(raw); }
    catch(e){ return show({ok:false, error:"invalid JSON", details:String(e)}); }

    const res = await api("/api/funnels/backup/import", {
      method:"POST",
      headers:{"Content-Type":"application/json"},
      body:JSON.stringify(payload)
    });

    show(res);
    await autoBackupFunnels("after_import_restore");
    state.view = "list";
    await render();
  }


  function show(x){
    state.last = x;
    const el = document.getElementById("fu-output");
    if (el) el.textContent = JSON.stringify(x, null, 2);
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
    const res = await api(`/api/funnels/configs/${encodeURIComponent(key)}/steps/upsert`, {
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
    const backupBtn = document.getElementById("fu-backup");
    if (backupBtn) backupBtn.onclick = async () => { state.view = "backup"; await render(); };

    const exportBtn = document.getElementById("fu-export-backup");
    if (exportBtn) exportBtn.onclick = exportBackup;

    const downloadBtn = document.getElementById("fu-download-backup");
    if (downloadBtn) downloadBtn.onclick = downloadBackup;

    const snapshotBtn = document.getElementById("fu-snapshot-backup");
    if (snapshotBtn) snapshotBtn.onclick = () => snapshotBackup("manual_button");

    const importBtn = document.getElementById("fu-import-backup");
    if (importBtn) importBtn.onclick = importBackup;
    document.getElementById("fu-backup").onclick = async () => { state.view = "backup"; await render(); };

    const exportBtn = document.getElementById("fu-export-backup");
    if (exportBtn) exportBtn.onclick = exportBackup;

    const downloadBtn = document.getElementById("fu-download-backup");
    if (downloadBtn) downloadBtn.onclick = downloadBackup;

    const importBtn = document.getElementById("fu-import-backup");
    if (importBtn) importBtn.onclick = importBackup;

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
