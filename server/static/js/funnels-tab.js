
(function(){
  const PANEL_ID = "funnels-ui-v1-panel";
  const BTN_ID = "funnels-ui-v1-btn";

  async function api(path, opts){
    const r = await fetch(path, opts || {});
    const text = await r.text();
    try { return JSON.parse(text); }
    catch(e){ return {ok:false, error:"bad_json", status:r.status, body:text}; }
  }

  function esc(s){
    return String(s == null ? "" : s)
      .replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
  }

  function val(id){ return document.getElementById(id)?.value || ""; }

  function css(){
    if (document.getElementById("funnels-ui-v1-style")) return;
    const st = document.createElement("style");
    st.id = "funnels-ui-v1-style";
    st.textContent = `
      #${BTN_ID}{
        position:fixed;right:18px;bottom:82px;z-index:99999;
        border:0;border-radius:999px;padding:12px 16px;
        background:#111;color:#fff;box-shadow:0 10px 30px rgba(0,0,0,.22);
        cursor:pointer;font-weight:800;
      }
      #${PANEL_ID}{
        position:fixed;right:18px;bottom:138px;width:760px;max-width:calc(100vw - 36px);
        max-height:78vh;overflow:auto;z-index:99999;background:#fff;color:#111;
        border:1px solid #ddd;border-radius:18px;box-shadow:0 20px 70px rgba(0,0,0,.32);
        padding:16px;font-family:system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
      }
      #funnels-native-root{
        position:relative;width:100%;max-width:none;max-height:none;overflow:visible;
        background:#fff;color:#111;border:0;border-radius:0;box-shadow:none;
        padding:16px;font-family:system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
      }
      #${PANEL_ID} h3{margin:0 0 8px;font-size:20px}
      #${PANEL_ID} h4{margin:16px 0 8px;font-size:15px}
      #${PANEL_ID} .muted{color:#666;font-size:12px}
      #${PANEL_ID} .grid{display:grid;grid-template-columns:1fr 1fr;gap:10px}
      #${PANEL_ID} .grid3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px}
      #${PANEL_ID} .row{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin:8px 0}
      #${PANEL_ID} .card{border:1px solid #eee;border-radius:14px;padding:12px;margin:10px 0;background:#fafafa}
      #${PANEL_ID} input,#${PANEL_ID} textarea,#${PANEL_ID} select{
        width:100%;box-sizing:border-box;border:1px solid #ddd;border-radius:10px;
        padding:9px;margin:4px 0;background:#fff;color:#111;font:inherit;
      }
      #${PANEL_ID} textarea{min-height:82px;resize:vertical;font-size:13px}
      #${PANEL_ID} button{
        border:1px solid #ddd;border-radius:10px;background:#f7f7f7;
        padding:8px 10px;cursor:pointer;font-weight:650;
      }
      #${PANEL_ID} button.primary{background:#111;color:#fff;border-color:#111}
      #${PANEL_ID} button.danger{background:#fff2f2;color:#900;border-color:#f0caca}
      #${PANEL_ID} pre{
        white-space:pre-wrap;background:#f6f6f6;border-radius:12px;padding:10px;font-size:12px;
        max-height:260px;overflow:auto;
      }
      #${PANEL_ID} .step-head{display:flex;justify-content:space-between;gap:8px;align-items:center}
      #${PANEL_ID} .pill{display:inline-block;border:1px solid #ddd;border-radius:999px;padding:2px 8px;font-size:12px;background:#fff}
      #${PANEL_ID} .ok{color:#087b2f}.bad{color:#a00000}
    `;
    document.head.appendChild(st);
  }

  let state = {
    funnelId: 1,
    funnel: null,
    debug: null,
    last: null
  };

  async function render(){
    css();

    let nativeRoot = document.getElementById("funnels-native-root");
    let panel = nativeRoot || document.getElementById(PANEL_ID);
    if (!panel) {
      panel = document.createElement("div");
      panel.id = PANEL_ID;
      document.body.appendChild(panel);
    }
    if (nativeRoot) {
      panel.id = "funnels-native-root";
    }

    panel.innerHTML = `
      <div class="step-head">
        <div>
          <h3>🧲 Funnels UI v1</h3>
          <div class="muted">Builder / Telegram bridge / AI warmup / test runner</div>
        </div>
        <button id="fu-close">×</button>
      </div>

      <div class="card">
        <h4>Funnel</h4>
        <div class="grid3">
          <label>Funnel ID<input id="fu-funnel-id" value="${esc(state.funnelId)}"></label>
          <label>Test external_user_id<input id="fu-user-id" value="ui_safe_test_user"></label>
          <label>Bot username<input id="fu-bot" value="content_ai_planner_bot"></label>
        </div>
        <div class="row">
          <button class="primary" data-act="load">Load funnel</button>
          <button data-act="create">Create default</button>
          <button data-act="stats">Analytics</button>
          <button data-act="jobs">Run due jobs</button>
        </div>
      </div>

      <div id="fu-funnel-box"></div>

      <div class="card">
        <h4>Telegram start-link</h4>
        <div class="row">
          <button class="primary" data-act="startlink">Generate link</button>
          <button data-act="bindme">Bind test user to my Telegram</button>
        </div>
        <pre id="fu-link-out">—</pre>
      </div>

      <div class="card">
        <h4>Test runner</h4>
        <div class="row">
          <button class="primary" data-act="event">Start event</button>
          <button data-act="next">Run next step</button>
          <button data-act="debug">Debug contact</button>
          <button data-act="forcejob">Force pending job due</button>
          <button data-act="jobs">Run due jobs</button>
        </div>
        <pre id="fu-test-out">—</pre>
      </div>

      <div id="fu-steps-box"></div>

      <div class="card">
        <h4>Raw output</h4>
        <pre id="fu-output">${esc(JSON.stringify(state.last || {}, null, 2))}</pre>
      </div>
    `;

    document.getElementById("fu-close").onclick = () => {
      if (document.getElementById("funnels-native-root")) {
        panel.innerHTML = "";
      } else {
        panel.remove();
      }
    };

    panel.querySelectorAll("button[data-act]").forEach(btn => {
      btn.onclick = () => handle(btn.getAttribute("data-act"));
    });

    await loadFunnel(false);
  }

  async function handle(act){
    state.funnelId = Number(val("fu-funnel-id") || state.funnelId || 1);
    const userId = val("fu-user-id") || "ui_safe_test_user";

    try {
      if (act === "load") return await loadFunnel(true);

      if (act === "create") {
        const res = await api("/api/funnels/default", {
          method:"POST", headers:{"Content-Type":"application/json"},
          body:JSON.stringify({name:"New UI Funnel"})
        });
        state.last = res;
        if (res.funnel_id) state.funnelId = res.funnel_id;
        document.getElementById("fu-funnel-id").value = state.funnelId;
        await loadFunnel(true);
        return;
      }

      if (act === "stats") {
        const res = await api("/api/funnels/analytics/summary");
        return show("fu-output", res);
      }

      if (act === "jobs") {
        const res = await api("/api/funnels/jobs/run-due", {method:"POST"});
        return show("fu-test-out", res);
      }

      if (act === "startlink") {
        const res = await api("/api/funnels/telegram/start-link", {
          method:"POST", headers:{"Content-Type":"application/json"},
          body:JSON.stringify({
            funnel_id: state.funnelId,
            external_user_id: userId,
            bot_username: val("fu-bot") || "content_ai_planner_bot"
          })
        });
        return show("fu-link-out", res);
      }

      if (act === "bindme") {
        const res = await api("/api/funnels/contact/bind-telegram", {
          method:"POST", headers:{"Content-Type":"application/json"},
          body:JSON.stringify({
            funnel_id: state.funnelId,
            platform:"instagram",
            external_user_id:userId,
            username:userId,
            telegram_chat_id:"330800472"
          })
        });
        return show("fu-link-out", res);
      }

      if (act === "event") {
        const res = await api("/api/funnels/event", {
          method:"POST", headers:{"Content-Type":"application/json"},
          body:JSON.stringify({
            funnel_id: state.funnelId,
            platform:"instagram",
            external_user_id:userId,
            username:userId,
            event_type:"comment_keyword",
            payload:{keyword:"ХОЧУ", source:"funnels_ui_v1"}
          })
        });
        return show("fu-test-out", res);
      }

      if (act === "next") {
        const res = await api("/api/funnels/contact/run-next", {
          method:"POST", headers:{"Content-Type":"application/json"},
          body:JSON.stringify({
            funnel_id: state.funnelId,
            platform:"instagram",
            external_user_id:userId
          })
        });
        return show("fu-test-out", res);
      }

      if (act === "debug") {
        const res = await api(`/api/funnels/contact/debug?funnel_id=${state.funnelId}&platform=instagram&external_user_id=${encodeURIComponent(userId)}`);
        state.debug = res;
        return show("fu-test-out", res);
      }

      if (act === "forcejob") {
        const res = await api("/api/funnels/jobs/run-due", {method:"POST"});
        show("fu-test-out", {
          note:"Backend has no force-due endpoint yet. Use sqlite command for now, then Run due jobs.",
          sqlite:`UPDATE funnel_jobs SET execute_at = strftime('%s','now') WHERE contact_id=(SELECT id FROM funnel_contacts WHERE external_user_id='${userId}') AND status='pending';`,
          run_due_result:res
        });
        return;
      }

    } catch(e) {
      show("fu-output", {ok:false, error:e.message || String(e)});
    }
  }

  async function loadFunnel(showRaw){
    state.funnelId = Number(val("fu-funnel-id") || state.funnelId || 1);
    const res = await api(`/api/funnels/${state.funnelId}`);
    state.last = res;
    state.funnel = res.item || null;

    renderFunnel();
    renderSteps();

    if (showRaw) show("fu-output", res);
  }

  function renderFunnel(){
    const box = document.getElementById("fu-funnel-box");
    const f = state.funnel;
    if (!box) return;

    if (!f) {
      box.innerHTML = `<div class="card bad">Funnel not found</div>`;
      return;
    }

    box.innerHTML = `
      <div class="card">
        <h4>Funnel settings</h4>
        <div class="grid">
          <label>Name<input id="fu-name" value="${esc(f.name)}"></label>
          <label>Status<input id="fu-status" value="${esc(f.status)}"></label>
          <label>Trigger type<input id="fu-trigger-type" value="${esc(f.trigger_type)}"></label>
          <label>Trigger value<input id="fu-trigger-value" value="${esc(f.trigger_value)}"></label>
          <label>Output type<input id="fu-output-type" value="${esc(f.output_type)}"></label>
          <label>Output target<input id="fu-output-target" value="${esc(f.output_target)}"></label>
        </div>
        <div class="row">
          <button class="primary" id="fu-save-funnel">Save funnel settings</button>
        </div>
      </div>
    `;

    document.getElementById("fu-save-funnel").onclick = saveFunnel;
  }

  async function saveFunnel(){
    const payload = {
      name: val("fu-name"),
      status: val("fu-status"),
      trigger_type: val("fu-trigger-type"),
      trigger_value: val("fu-trigger-value"),
      output_type: val("fu-output-type"),
      output_target: val("fu-output-target")
    };

    const res = await api(`/api/funnels/${state.funnelId}`, {
      method:"PATCH", headers:{"Content-Type":"application/json"},
      body:JSON.stringify(payload)
    });

    show("fu-output", res);
    await loadFunnel(false);
  }

  function renderSteps(){
    const box = document.getElementById("fu-steps-box");
    const f = state.funnel;
    if (!box || !f) return;

    const steps = f.steps || [];
    box.innerHTML = `
      <div class="card">
        <h4>Steps editor</h4>
        <div class="muted">Редагуй config JSON. Для AI step важливі system/prompt/delivery/auto_send.</div>
        ${steps.map(stepHtml).join("")}
        <div class="card">
          <h4>Add / replace step</h4>
          <div class="grid3">
            <input id="new-step-order" placeholder="step_order" value="${steps.length + 1}">
            <input id="new-step-type" placeholder="step_type" value="send_message">
            <input id="new-step-name" placeholder="step_name" value="New step">
          </div>
          <textarea id="new-step-config">{ "text": "Нове повідомлення" }</textarea>
          <button class="primary" id="new-step-save">Save new step</button>
        </div>
      </div>
    `;

    steps.forEach(st => {
      const btn = document.getElementById(`save-step-${st.step_order}`);
      if (btn) btn.onclick = () => saveStep(st.step_order);

      const del = document.getElementById(`delete-step-${st.step_order}`);
      if (del) del.onclick = () => deleteStep(st.step_order);
    });

    document.getElementById("new-step-save").onclick = async () => {
      await saveStep(null, true);
    };
  }

  function stepHtml(st){
    return `
      <div class="card">
        <div class="step-head">
          <div>
            <b>Step ${esc(st.step_order)} — ${esc(st.step_name)}</b>
            <span class="pill">${esc(st.step_type)}</span>
          </div>
          <div class="row">
            <button class="primary" id="save-step-${esc(st.step_order)}">Save</button>
            <button class="danger" id="delete-step-${esc(st.step_order)}">Delete</button>
          </div>
        </div>
        <div class="grid3">
          <label>Order<input id="step-order-${esc(st.step_order)}" value="${esc(st.step_order)}"></label>
          <label>Type<input id="step-type-${esc(st.step_order)}" value="${esc(st.step_type)}"></label>
          <label>Name<input id="step-name-${esc(st.step_order)}" value="${esc(st.step_name)}"></label>
        </div>
        <textarea id="step-config-${esc(st.step_order)}">${esc(JSON.stringify(st.config || {}, null, 2))}</textarea>
      </div>
    `;
  }

  async function saveStep(order, isNew){
    const prefix = isNew ? "new-step" : `step`;
    let stepOrder, stepType, stepName, cfgText;

    if (isNew) {
      stepOrder = Number(val("new-step-order"));
      stepType = val("new-step-type");
      stepName = val("new-step-name");
      cfgText = val("new-step-config");
    } else {
      stepOrder = Number(val(`step-order-${order}`));
      stepType = val(`step-type-${order}`);
      stepName = val(`step-name-${order}`);
      cfgText = val(`step-config-${order}`);
    }

    let config = {};
    try { config = JSON.parse(cfgText || "{}"); }
    catch(e) {
      show("fu-output", {ok:false, error:"Bad config JSON", detail:e.message});
      return;
    }

    const res = await api("/api/funnels/steps/upsert", {
      method:"POST", headers:{"Content-Type":"application/json"},
      body:JSON.stringify({
        funnel_id: state.funnelId,
        step_order: stepOrder,
        step_type: stepType,
        step_name: stepName,
        config
      })
    });

    show("fu-output", res);
    await loadFunnel(false);
  }

  async function deleteStep(order){
    const res = await api("/api/funnels/steps/delete", {
      method:"POST", headers:{"Content-Type":"application/json"},
      body:JSON.stringify({
        funnel_id: state.funnelId,
        step_order: Number(order)
      })
    });
    show("fu-output", res);
    await loadFunnel(false);
  }

  function show(id, obj){
    state.last = obj;
    const el = document.getElementById(id);
    if (el) el.textContent = JSON.stringify(obj, null, 2);
    const raw = document.getElementById("fu-output");
    if (raw && id !== "fu-output") raw.textContent = JSON.stringify(obj, null, 2);
  }

  function boot(){
    css();

    const nativeRoot = document.getElementById("funnels-native-root");
    const nativeTab = document.querySelector('[data-tab="funnels"], [onclick*="funnels"]');

    if (nativeRoot) {
      window.renderFunnelsNativeTab = render;

      if (nativeTab && !nativeTab.dataset.funnelsBound) {
        nativeTab.dataset.funnelsBound = "1";
        nativeTab.addEventListener("click", function(){
          setTimeout(render, 50);
        });
      }

      // If page already opened funnels tab by hash/manual state
      if (location.hash === "#funnels") setTimeout(render, 50);
      return;
    }

    // Debug fallback only if native tab is absent
    if (!document.getElementById(BTN_ID)) {
      const btn = document.createElement("button");
      btn.id = BTN_ID;
      btn.textContent = "Funnels";
      btn.onclick = () => {
        const p = document.getElementById(PANEL_ID);
        if (p) p.remove();
        else render();
      };
      document.body.appendChild(btn);
    }
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
  else boot();

  window.openFunnelsUiV1 = render;
  window.renderFunnelsNativeTab = render;
})();
