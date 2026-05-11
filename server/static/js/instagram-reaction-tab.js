(function(){
  function $(id){ return document.getElementById(id); }

  async function jget(url){
    const r = await fetch(url);
    return await r.json();
  }

  async function jpost(url, payload){
    const r = await fetch(url, {
      method:"POST",
      headers:{"Content-Type":"application/json"},
      body:JSON.stringify(payload || {})
    });
    return await r.json();
  }

  function esc(s){
    return String(s ?? "")
      .replaceAll("&","&amp;")
      .replaceAll("<","&lt;")
      .replaceAll(">","&gt;");
  }

  function findInstagramRoot(){
    const h = [...document.querySelectorAll("h1,h2,h3")].find(x =>
      (x.textContent || "").includes("Instagram-стрічка")
    );
    if(!h) return null;

    let cur = h;
    while(cur && cur.parentElement){
      if(cur.parentElement.children.length > 1) return cur.parentElement;
      cur = cur.parentElement;
    }
    return h.parentElement;
  }

  function ensureBox(){
    if($("igReactionEngineBox")) return $("igReactionEngineBox");

    const root = findInstagramRoot();
    if(!root) return null;

    const box = document.createElement("div");
    box.id = "igReactionEngineBox";
    box.style.cssText = `
      margin:18px 0;
      background:#fff;
      border-radius:18px;
      padding:18px;
      box-shadow:0 10px 30px rgba(0,0,0,.06);
      border:1px solid #eef0f4;
    `;

    box.innerHTML = `
      <div style="display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap">
        <div>
          <h3 style="margin:0;font-size:22px">🤖 AI реакції Instagram</h3>
          <p style="margin:6px 0 0;color:#6b7280">
            Автономний модуль: реакція → аналіз користувача → стиль → draft відповіді → воронка.
          </p>
        </div>
        <div style="display:flex;gap:8px;flex-wrap:wrap">
          <button id="igRxRefreshBtn" class="btn btn-dark">Оновити</button>
          <button id="igRxAutoDryRunBtn" class="btn btn-outline-success">Auto dry-run</button>
          <button id="igRxAutoRunBtn" class="btn btn-success">Auto run</button>
          <button id="igRxTestBtn" class="btn btn-outline-dark">Тест реакції</button>
          <button id="igRxSaveSettingsBtn" class="btn btn-primary">Зберегти налаштування</button>
        </div>
      </div>

      <div id="igRxStatus" style="margin-top:12px;color:#374151">Завантаження...</div>

      <div class="ig-auto-box">
        <label><input type="checkbox" id="igAutoProcess"> Auto process</label>
        <label><input type="checkbox" id="igAutoSend"> Auto send</label>
        <label><input type="checkbox" id="igApprovalRequired"> Approval required</label>
        <button id="igSaveAutoSettingsBtn" class="btn btn-sm btn-outline-primary">Зберегти auto</button>
        <div id="igAutoResult" class="ig-auto-result"></div>
      </div>

      <div style="display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-top:14px">
        <div>
          <h4 style="margin:0 0 8px">⚙️ Воронка / CTA</h4>

          <label>Головна ціль воронки</label>
          <textarea data-ig-setting="main_funnel_goal"></textarea>

          <label>Основний CTA</label>
          <textarea data-ig-setting="soft_redirect_cta"></textarea>

          <label>CTA cold</label>
          <textarea data-ig-setting="cold_user_cta"></textarea>

          <label>CTA warm</label>
          <textarea data-ig-setting="warm_user_cta"></textarea>

          <label>CTA hot</label>
          <textarea data-ig-setting="hot_user_cta"></textarea>

          <label>Офер</label>
          <input data-ig-setting="default_offer">

          <label>Ключові слова ліда</label>
          <input data-ig-setting="lead_keywords">
        </div>

        <div>
          <h4 style="margin:0 0 8px">🧠 Правила AI</h4>

          <label>Голос бренду</label>
          <textarea data-ig-setting="brand_voice"></textarea>

          <label>Що AI не має писати</label>
          <textarea data-ig-setting="forbidden_topics"></textarea>

          <label>Політика токсичних коментарів</label>
          <textarea data-ig-setting="toxic_policy"></textarea>

          <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px">
            <div>
              <label>Public min</label>
              <input data-ig-setting="public_reply_min_chars">
            </div>
            <div>
              <label>Public max</label>
              <input data-ig-setting="public_reply_max_chars">
            </div>
            <div>
              <label>Direct min</label>
              <input data-ig-setting="direct_reply_min_chars">
            </div>
            <div>
              <label>Direct max</label>
              <input data-ig-setting="direct_reply_max_chars">
            </div>
          </div>
        </div>
      </div>

      <div style="margin-top:18px">
        <h4 style="margin:0 0 8px">📥 Drafts відповідей</h4>
        <div id="igRxDrafts">Завантаження...</div>
      </div>

      <style>
        #igReactionEngineBox label {
          display:block;
          margin:9px 0 4px;
          font-weight:700;
          font-size:13px;
          color:#111827;
        }
        #igReactionEngineBox textarea,
        #igReactionEngineBox input {
          width:100%;
          border:1px solid #d1d5db;
          border-radius:10px;
          padding:9px 10px;
          font-size:14px;
          background:#fff;
        }
        #igReactionEngineBox textarea {
          min-height:56px;
          resize:vertical;
        }
        #igReactionEngineBox .ig-draft-card {
          border:1px solid #e5e7eb;
          border-radius:14px;
          padding:12px;
          margin:10px 0;
          background:#fafafa;
        }
        #igReactionEngineBox .ig-pill {
          display:inline-block;
          padding:3px 8px;
          border-radius:999px;
          background:#111;
          color:white;
          font-size:12px;
          margin-right:5px;
        }
      </style>
    `;

    const firstCard = root.querySelector(".card, .panel, .instagram-card") || root.children[1];
    if(firstCard && firstCard.parentNode){
      firstCard.parentNode.insertBefore(box, firstCard.nextSibling);
    } else {
      root.appendChild(box);
    }

    $("igRxRefreshBtn").onclick = loadAll;
    $("igRxSaveSettingsBtn").onclick = saveSettings;
    $("igRxTestBtn").onclick = testReaction;

    if($("igRxAutoDryRunBtn")) $("igRxAutoDryRunBtn").onclick = () => runAuto(true);
    if($("igRxAutoRunBtn")) $("igRxAutoRunBtn").onclick = () => runAuto(false);
    if($("igSaveAutoSettingsBtn")) $("igSaveAutoSettingsBtn").onclick = saveAutoSettings;

    return box;
  }

  async function loadSettings(){
    const data = await jget("/api/instagram/reactions/settings");
    const s = data.settings || {};
    document.querySelectorAll("#igReactionEngineBox [data-ig-setting]").forEach(el => {
      const k = el.getAttribute("data-ig-setting");
      el.value = s[k] || "";
    });
  }

  async function loadStatus(){
    const data = await jget("/api/instagram/reactions/status");
    const t = data.tables || {};
    $("igRxStatus").innerHTML = `
      <b>Статус:</b>
      reactions=${t.ig_reactions || 0},
      profiles=${t.ig_user_profiles || 0},
      drafts=${t.ig_ai_reply_drafts || 0},
      pending=${data.drafts_pending || 0}
    `;
  }

  async function loadDrafts(){
    const data = await jget("/api/instagram/replies/drafts?limit=20");
    const drafts = data.drafts || [];
    if(!drafts.length){
      $("igRxDrafts").innerHTML = `<div style="color:#6b7280">Drafts ще немає.</div>`;
      return;
    }

    $("igRxDrafts").innerHTML = drafts.map(d => `
      <div class="ig-draft-card">
        <div style="margin-bottom:8px">
          <span class="ig-pill">${esc(d.selected_prompt_mode)}</span>
          <span class="ig-pill">${esc(d.reply_strategy)}</span>
          <span class="ig-pill">${esc(d.channel)}</span>
          <b>@${esc(d.username || "user")}</b>
        </div>

        <div style="font-size:13px;color:#6b7280;margin-bottom:8px">
          Реакція: ${esc(d.reaction_text || "")}
        </div>

        <div style="margin-bottom:8px">
          <b>Public:</b><br>${esc(d.public_reply || "")}
        </div>

        ${d.direct_reply ? `<div style="margin-bottom:8px"><b>Direct:</b><br>${esc(d.direct_reply)}</div>` : ""}

        ${d.followup_question ? `<div style="margin-bottom:8px"><b>Follow-up:</b><br>${esc(d.followup_question)}</div>` : ""}

        <div style="font-size:12px;color:#6b7280">
          Note: ${esc(d.internal_note || "")}
        </div>
      </div>
    `).join("");
  }

  async function saveSettings(){
    const settings = {};
    document.querySelectorAll("#igReactionEngineBox [data-ig-setting]").forEach(el => {
      settings[el.getAttribute("data-ig-setting")] = el.value;
    });
    const res = await jpost("/api/instagram/reactions/settings", {settings});
    alert(res.status === "ok" ? "Налаштування збережено" : "Помилка збереження");
    await loadAll();
  }

  async function testReaction(){
    const text = prompt("Тестова реакція користувача:", "Я боюсь регресії, раптом побачу щось страшне?");
    if(!text) return;

    const res = await jpost("/api/instagram/reactions/manual-add", {
      username:"front_test_user",
      text,
      event_type:"comment"
    });

    console.log("IG test reaction:", res);
    await loadAll();
  }


  async function loadAutoSettings(){
    const data = await jget("/api/instagram/auto/settings");
    const st = data.settings || {};
    if($("igAutoProcess")) $("igAutoProcess").checked = String(st.auto_process || "1") === "1";
    if($("igAutoSend")) $("igAutoSend").checked = String(st.auto_send || "0") === "1";
    if($("igApprovalRequired")) $("igApprovalRequired").checked = String(st.approval_required || "1") === "1";
  }

  async function saveAutoSettings(){
    const payload = {
      auto_process: $("igAutoProcess")?.checked ? "1" : "0",
      auto_send: $("igAutoSend")?.checked ? "1" : "0",
      approval_required: $("igApprovalRequired")?.checked ? "1" : "0"
    };
    const res = await jpost("/api/instagram/auto/settings", payload);
    $("igAutoResult").textContent = res.status === "ok" ? "Auto settings saved" : JSON.stringify(res, null, 2);
  }

  async function runAuto(dryRun){
    const url = `/api/instagram/auto/run-once?limit_media=10&limit_comments=50&dry_run=${dryRun ? "true" : "false"}`;
    const res = await jpost(url, {});
    $("igAutoResult").textContent = JSON.stringify({
      dry_run: res.dry_run,
      auto_send: res.auto_send,
      approval_required: res.approval_required,
      comments_seen: res.comments_seen,
      skipped_already_replied: res.skipped_already_replied,
      skipped_existing: res.skipped_existing,
      drafts_created: res.drafts_created,
      sent: res.sent,
      errors: (res.errors || []).length
    }, null, 2);
    await loadAll();
  }


  async function loadAll(){
    ensureBox();
    await loadSettings();
    await loadAutoSettings();
    await loadStatus();
    await loadDrafts();
  }

  // IG_REACTION_ENGINE_NO_AUTOBOOT_V1
  // Do not render this block on Instagram tab start.
  // It must be loaded only by the modal opener.
  window.igReactionEngineLoad = loadAll;
})();



// INSTAGRAM_AI_TO_FUNNELS_BUTTON_V1
(function(){
  if (window.__igAiToFunnelsButtonV1) return;
  window.__igAiToFunnelsButtonV1 = true;

  async function igAiToFunnelsApi(path, opts){
    const r = await fetch(path, opts || {});
    const text = await r.text();
    try { return JSON.parse(text); }
    catch(e){ return {ok:false, status:r.status, error:"bad_json", body:text}; }
  }

  function ensureStyle(){
    if (document.getElementById("ig-ai-to-funnels-style")) return;

    const st = document.createElement("style");
    st.id = "ig-ai-to-funnels-style";
    st.textContent = `
      #ig-ai-to-funnels-btn{
        border:1px solid #111;
        background:#111;
        color:#fff;
        border-radius:12px;
        padding:10px 14px;
        font-weight:800;
        cursor:pointer;
        margin:6px;
      }
      #ig-ai-to-funnels-btn[disabled]{
        opacity:.65;
        cursor:wait;
      }
    `;
    document.head.appendChild(st);
  }

  function findInstagramReactionMount(){
    const candidates = [
      document.getElementById("instagram-reaction-root"),
      document.getElementById("instagram-reactions-root"),
      document.getElementById("instagram-reaction-tab"),
      document.getElementById("instagram-tab"),
      document.querySelector("[data-tab='instagram']"),
      document.querySelector("#instagram-content"),
      document.querySelector(".instagram-content"),
    ].filter(Boolean);

    if (candidates.length) return candidates[0];

    const buttons = Array.from(document.querySelectorAll("button"));
    const reactionBtn = buttons.find(b => /Direct Reaction AI|AI Reaction|Reaction AI|Instagram AI/i.test(b.textContent || ""));
    if (reactionBtn) return reactionBtn.parentElement || reactionBtn.closest("div");

    return null;
  }

  function inject(){
    ensureStyle();

    if (document.getElementById("ig-ai-to-funnels-btn")) return;

    const mount = findInstagramReactionMount();
    if (!mount) return;

    const btn = document.createElement("button");
    btn.id = "ig-ai-to-funnels-btn";
    btn.type = "button";
    btn.textContent = "🧲 AI reactions → Funnel leads";

    btn.addEventListener("click", async ()=>{
      const old = btn.textContent;
      btn.disabled = true;
      btn.textContent = "⏳ Запускаю воронки...";

      try{
        const res = await igAiToFunnelsApi("/api/funnels/runtime/instagram-ai-sync-and-start", {
          method:"POST",
          headers:{"Content-Type":"application/json"},
          body:JSON.stringify({
            limit:100,
            mode:"send"
          })
        });

        console.log("[Instagram AI → Funnels]", res);

        alert(
          "Instagram AI → Funnels\n\n" +
          "Started: " + (res.started || 0) +
          "\nSkipped: " + (res.skipped || 0) +
          "\nErrors: " + ((res.errors || []).length)
        );
      }catch(e){
        alert("Instagram AI → Funnels failed: " + e);
      }finally{
        btn.disabled = false;
        btn.textContent = old;
      }
    });

    mount.prepend(btn);
  }

  document.addEventListener("DOMContentLoaded", inject);
  setTimeout(inject, 500);
  setTimeout(inject, 1500);
  setTimeout(inject, 3000);

  const obs = new MutationObserver(inject);
  obs.observe(document.documentElement, {childList:true, subtree:true});
})();

