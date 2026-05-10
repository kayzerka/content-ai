(function(){
  if (window.__FUNNEL_STEPS_EDITOR_V2__) return;
  window.__FUNNEL_STEPS_EDITOR_V2__ = true;

  async function apiJson(url, opts){
    const r = await fetch(url, opts || {});
    const t = await r.text();
    try { return JSON.parse(t); }
    catch(e){ return {ok:false, status:r.status, raw:t}; }
  }

  function esc(s){
    return String(s == null ? "" : s)
      .replaceAll("&","&amp;")
      .replaceAll("<","&lt;")
      .replaceAll(">","&gt;")
      .replaceAll('"',"&quot;");
  }

  function stepTypeOf(item){
    try {
      const sj = typeof item.settings_json === "string"
        ? JSON.parse(item.settings_json || "{}")
        : (item.settings_json || {});
      return sj.step_type || "send_message";
    } catch(e) {
      return "send_message";
    }
  }

  async function openFunnelStepEditor(funnelKey, stepKey){
    funnelKey = String(funnelKey || "").trim();
    stepKey = String(stepKey || "").trim();

    if (!funnelKey) return alert("Нема funnel_key");
    if (!stepKey) return alert("Нема step_key");

    const res = await apiJson(`/api/funnels/steps/list?funnel_key=${encodeURIComponent(funnelKey)}`);
    const items = res.items || [];
    const item = items.find(x => String(x.step_key) === stepKey);

    if (!item) {
      return alert("Крок не знайдено: " + stepKey);
    }

    const old = document.getElementById("funnel-step-editor-modal");
    if (old) old.remove();

    const modal = document.createElement("div");
    modal.id = "funnel-step-editor-modal";
    modal.style.cssText = "position:fixed;inset:0;z-index:999999;background:rgba(0,0,0,.45);display:flex;align-items:flex-start;justify-content:center;overflow:auto;padding:40px 16px;";

    modal.innerHTML = `
      <div style="background:#fff;width:min(760px,96vw);border-radius:18px;padding:20px;box-shadow:0 20px 60px rgba(0,0,0,.25);">
        <div style="display:flex;justify-content:space-between;gap:12px;align-items:center;margin-bottom:14px;">
          <div>
            <h2 style="margin:0;font-size:22px;">✏️ Редагувати крок: ${esc(stepKey)}</h2>
            <div style="color:#667085;font-size:13px;">funnel_key: <b>${esc(funnelKey)}</b></div>
          </div>
          <button id="fse-close" style="border:1px solid #ddd;border-radius:10px;padding:8px 12px;background:#fff;cursor:pointer;">×</button>
        </div>

        <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;">
          <label><b>step_key</b><input id="fse-step-key" value="${esc(item.step_key || "")}" readonly style="width:100%;padding:10px;border:1px solid #ddd;border-radius:10px;background:#f8fafc;"></label>
          <label><b>Тип кроку</b>
            <select id="fse-step-type" style="width:100%;padding:10px;border:1px solid #ddd;border-radius:10px;">
              ${["send_message","send_free_gift","send_ai_message","wait_delay"].map(t => `<option value="${t}" ${stepTypeOf(item)===t ? "selected" : ""}>${t}</option>`).join("")}
            </select>
          </label>
          <label><b>Порядок</b><input id="fse-step-order" type="number" value="${esc(item.step_order || 1)}" style="width:100%;padding:10px;border:1px solid #ddd;border-radius:10px;"></label>

          <label><b>Активний</b>
            <select id="fse-active" style="width:100%;padding:10px;border:1px solid #ddd;border-radius:10px;">
              <option value="1" ${Number(item.active ?? 1) ? "selected" : ""}>1</option>
              <option value="0" ${!Number(item.active ?? 1) ? "selected" : ""}>0</option>
            </select>
          </label>
          <label><b>trigger_stage</b><input id="fse-trigger-stage" value="${esc(item.trigger_stage || "")}" style="width:100%;padding:10px;border:1px solid #ddd;border-radius:10px;"></label>
          <label><b>next_stage</b><input id="fse-next-stage" value="${esc(item.next_stage || "")}" style="width:100%;padding:10px;border:1px solid #ddd;border-radius:10px;"></label>
        </div>

        <label style="display:block;margin-top:12px;"><b>message_text</b>
          <textarea id="fse-message-text" style="width:100%;min-height:150px;padding:10px;border:1px solid #ddd;border-radius:10px;">${esc(item.message_text || "")}</textarea>
        </label>

        <div style="display:grid;grid-template-columns:1fr 1fr 140px;gap:12px;margin-top:12px;">
          <label><b>button_text</b><input id="fse-button-text" value="${esc(item.button_text || "")}" style="width:100%;padding:10px;border:1px solid #ddd;border-radius:10px;"></label>
          <label><b>button_url</b><input id="fse-button-url" value="${esc(item.button_url || "")}" placeholder="https://t.me/..." style="width:100%;padding:10px;border:1px solid #ddd;border-radius:10px;"></label>
          <label><b>delay_minutes</b><input id="fse-delay" type="number" value="${esc(item.delay_minutes || 0)}" style="width:100%;padding:10px;border:1px solid #ddd;border-radius:10px;"></label>
        </div>

        <div style="display:flex;gap:10px;margin-top:16px;">
          <button id="fse-save" style="background:#111;color:#fff;border:0;border-radius:10px;padding:10px 16px;font-weight:700;cursor:pointer;">💾 Зберегти цей крок</button>
          <button id="fse-close2" style="border:1px solid #ddd;border-radius:10px;padding:10px 16px;background:#fff;cursor:pointer;">Закрити</button>
        </div>

        <pre id="fse-output" style="background:#f8fafc;border-radius:12px;padding:12px;max-height:180px;overflow:auto;margin-top:14px;">{}</pre>
      </div>
    `;

    document.body.appendChild(modal);

    const close = () => modal.remove();
    modal.querySelector("#fse-close").onclick = close;
    modal.querySelector("#fse-close2").onclick = close;

    modal.querySelector("#fse-save").onclick = async () => {
      const payload = {
        funnel_key: funnelKey,
        step_key: stepKey,
        step_order: Number(modal.querySelector("#fse-step-order").value || 1),
        active: Number(modal.querySelector("#fse-active").value || 1),
        trigger_stage: modal.querySelector("#fse-trigger-stage").value.trim(),
        next_stage: modal.querySelector("#fse-next-stage").value.trim(),
        message_text: modal.querySelector("#fse-message-text").value,
        button_text: modal.querySelector("#fse-button-text").value,
        button_url: modal.querySelector("#fse-button-url").value,
        delay_minutes: Number(modal.querySelector("#fse-delay").value || 0),
        settings_json: JSON.stringify({step_type: modal.querySelector("#fse-step-type").value})
      };

      const save = await apiJson("/api/funnels/steps/upsert", {
        method:"POST",
        headers:{"Content-Type":"application/json"},
        body:JSON.stringify(payload)
      });

      modal.querySelector("#fse-output").textContent = JSON.stringify(save, null, 2);

      if (save.ok && window.renderFunnelsNativeTab) {
        setTimeout(() => window.renderFunnelsNativeTab(), 300);
      }
    };
  }

  window.openFunnelStepEditor = openFunnelStepEditor;
})();
