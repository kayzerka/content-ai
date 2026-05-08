(function TelegramAiSchedulerV1() {
  function findTelegramTextarea() {
    return Array.from(document.querySelectorAll("textarea")).find(t =>
      (t.placeholder || "").includes("Напиши текст") ||
      (t.placeholder || "").includes("згенеруй")
    );
  }

  function getTargetSelect() {
    return document.getElementById("telegram-target-chat-id");
  }

  function getText() {
    const t = findTelegramTextarea();
    return t ? t.value.trim() : "";
  }

  function setText(value) {
    const t = findTelegramTextarea();
    if (!t) return;
    t.value = value || "";
    t.dispatchEvent(new Event("input", {bubbles: true}));
  }

  function buildUi() {
    if (document.getElementById("telegram-ai-scheduler-v1")) return;

    const textarea = findTelegramTextarea();
    if (!textarea) return;

    const box = document.createElement("div");
    box.id = "telegram-ai-scheduler-v1";
    box.style.margin = "12px 0";
    box.style.padding = "12px";
    box.style.border = "1px solid #d1d5db";
    box.style.borderRadius = "12px";
    box.style.background = "#f8fafc";

    box.innerHTML = `
      <div style="font-weight:900;margin-bottom:8px;">🤖 AI повідомлення для обраної клієнтки</div>

      <textarea id="telegram-ai-prompt-v1"
        placeholder="Напиши задачу для AI: наприклад, зроби тепле повідомлення про технічні роботи / анонс сеансу / прогрів..."
        style="width:100%;min-height:80px;padding:10px;border:1px solid #d1d5db;border-radius:10px;"></textarea>

      <div style="display:flex;gap:10px;flex-wrap:wrap;margin-top:10px;">
        <button id="telegram-ai-generate-btn-v1" type="button"
          style="padding:10px 14px;border-radius:10px;border:0;background:#111827;color:white;font-weight:900;">
          ✨ Згенерувати AI
        </button>

        <input id="telegram-schedule-at-v1" type="datetime-local"
          style="padding:10px;border:1px solid #d1d5db;border-radius:10px;font-weight:700;">

        <button id="telegram-schedule-btn-v1" type="button"
          style="padding:10px 14px;border-radius:10px;border:1px solid #111827;background:white;font-weight:900;">
          🗓️ Запланувати в обраний чат
        </button>
      </div>

      <div id="telegram-ai-status-v1"
        style="margin-top:10px;font-size:13px;font-weight:700;color:#334155;"></div>
    `;

    textarea.parentNode.insertBefore(box, textarea);

    document.getElementById("telegram-ai-generate-btn-v1").onclick = generateAi;
    document.getElementById("telegram-schedule-btn-v1").onclick = scheduleMessage;
  }

  async function generateAi() {
    const status = document.getElementById("telegram-ai-status-v1");
    const prompt = document.getElementById("telegram-ai-prompt-v1").value.trim();
    const target = getTargetSelect();

    if (!target || !target.value) {
      alert("Спочатку обери групу або канал.");
      return;
    }

    if (!prompt) {
      alert("Напиши задачу для AI.");
      return;
    }

    status.textContent = "AI генерує повідомлення...";

    const res = await fetch("/api/telegram/ai_generate_message", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({
        prompt,
        target_chat_id: target.value
      })
    });

    const data = await res.json();

    if (!data.ok) {
      status.textContent = "AI помилка: " + (data.error || "unknown");
      return;
    }

    setText(data.text || data.result || "");
    status.textContent = "Готово. Текст вставлено в блок, можна редагувати.";
  }

  async function scheduleMessage() {
    const status = document.getElementById("telegram-ai-status-v1");
    const target = getTargetSelect();
    const scheduledAt = document.getElementById("telegram-schedule-at-v1").value;
    const text = getText();

    if (!target || !target.value) {
      alert("Оберіть групу або канал.");
      return;
    }

    if (!text) {
      alert("Немає тексту повідомлення.");
      return;
    }

    if (!scheduledAt) {
      alert("Оберіть дату і час.");
      return;
    }

    const res = await fetch("/api/telegram/schedule_safe", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({
        purpose: "client_funnel",
        target_chat_id: target.value,
        scheduled_at: scheduledAt,
        text
      })
    });

    const data = await res.json();

    if (!data.ok) {
      status.textContent = "Помилка планування: " + (data.error || "unknown");
      return;
    }

    status.textContent = "Заплановано. ID: " + data.schedule_id;
  }

  function run() {
    setTimeout(buildUi, 400);
  }

  document.addEventListener("DOMContentLoaded", run);
  document.addEventListener("click", run);

  new MutationObserver(run).observe(document.documentElement, {
    childList: true,
    subtree: true
  });
})();









// ============================================================================
// STABLE TELEGRAM TARGET SELECT + STRICT SEND V5
// ============================================================================

(function StableTelegramTargetSelectV5() {
  if (window.__stableTelegramTargetSelectV5) return;
  window.__stableTelegramTargetSelectV5 = true;

  let targetsLoaded = false;

  function findAiBox() {
    return document.getElementById("telegram-ai-scheduler-v1");
  }

  function findMainTelegramTextarea() {
    const areas = Array.from(document.querySelectorAll("textarea"));
    return areas.find(t =>
      (t.placeholder || "").includes("Напиши текст") ||
      (t.placeholder || "").includes("згенеруй")
    );
  }

  async function loadTargetsOnce(force=false) {
    const sel = document.getElementById("telegram-target-chat-id");
    if (!sel) return;

    if (targetsLoaded && !force) return;

    const current = sel.value;

    const res = await fetch("/api/telegram/chats", { cache: "no-store" });
    const data = await res.json();

    const targets = (data.chats || []).filter(ch => {
      const role = String(ch.role || "");
      return Number(ch.enabled) === 1 && (
        role === "client_group" ||
        role === "client_channel" ||
        role === "topic" ||
        Number(ch.is_topic) === 1 ||
        String(ch.chat_id || "").includes(":")
      );
    });

    sel.innerHTML = '<option value="">Оберіть канал / групу / гілку</option>';

    targets.forEach(ch => {
      const opt = document.createElement("option");
      opt.value = String(ch.chat_id);

      const isTopic =
        ch.role === "topic" ||
        Number(ch.is_topic) === 1 ||
        String(ch.chat_id || "").includes(":");

      const icon = isTopic
        ? "🧵 Гілка"
        : (ch.role === "client_channel" ? "📣 Канал" : "👥 Група");

      opt.textContent = `${icon} — ${ch.title || ch.username || ch.chat_id}`;

      if (String(ch.chat_id) === String(current)) opt.selected = true;

      sel.appendChild(opt);
    });

    targetsLoaded = true;
    console.log("[telegram stable targets loaded]", targets);
  }

  function ensureSelectUi() {
    const aiBox = findAiBox();
    if (!aiBox) return;

    if (!document.getElementById("telegram-target-select-wrap-v5")) {
      const wrap = document.createElement("div");
      wrap.id = "telegram-target-select-wrap-v5";
      wrap.style.margin = "0 0 14px 0";

      wrap.innerHTML = `
        <label style="display:block;font-weight:900;margin-bottom:6px;">
          🎯 Куди постити
        </label>
        <select id="telegram-target-chat-id"
          style="width:100%;padding:10px;border:1px solid #d1d5db;border-radius:10px;font-weight:800;">
          <option value="">Завантажую...</option>
        </select>
      `;

      aiBox.insertBefore(wrap, aiBox.firstChild);
    }

    loadTargetsOnce(false);
  }

  async function strictSendSelected() {
    const sel = document.getElementById("telegram-target-chat-id");
    const textarea = findMainTelegramTextarea();

    if (!sel || !sel.value) {
      alert("Оберіть канал / групу / гілку.");
      return;
    }

    if (!textarea || !textarea.value.trim()) {
      alert("Немає тексту для відправки.");
      return;
    }

    const res = await fetch("/api/telegram/send_client_target", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({
        target_chat_id: sel.value,
        text: textarea.value.trim()
      })
    });

    const data = await res.json();
    console.log("[telegram strict selected send]", data);

    if (!data.ok) {
      alert("Помилка відправки: " + (data.error || "unknown"));
      return;
    }

    alert("✅ Відправлено в обраний канал / групу / гілку");
  }

  function patchSendButton() {
    Array.from(document.querySelectorAll("button")).forEach(btn => {
      const txt = btn.textContent || "";

      if (
        txt.includes("Відправити всім активним") ||
        txt.includes("Відправити в обраний")
      ) {
        btn.textContent = "🚀 Відправити в обраний канал/групу";
        btn.onclick = function(e) {
          e.preventDefault();
          e.stopPropagation();
          strictSendSelected();
          return false;
        };
      }
    });
  }

  window.reloadTelegramTargets = function() {
    targetsLoaded = false;
    return loadTargetsOnce(true);
  };

  function init() {
    ensureSelectUi();
    patchSendButton();
  }

  document.addEventListener("DOMContentLoaded", () => setTimeout(init, 600));
  setTimeout(init, 1000);
})();

// ============================================================================
// /STABLE TELEGRAM TARGET SELECT + STRICT SEND V5
// ============================================================================

// ============================================================================
// FORCE AI OUTPUT INTO EDITABLE POST TEXTAREA V2
// ============================================================================

(function ForceAiOutputIntoEditableTextareaV2() {
  if (window.__forceAiOutputIntoEditableTextareaV2) return;
  window.__forceAiOutputIntoEditableTextareaV2 = true;

  function findPostTextarea() {
    const areas = Array.from(document.querySelectorAll("textarea"));

    // головний textarea поста — не AI prompt
    return areas.find(t => {
      const ph = t.placeholder || "";
      const id = t.id || "";
      return (
        ph.includes("Напиши текст або згенеруй") &&
        !id.includes("prompt") &&
        !id.includes("ai")
      );
    }) || areas.find(t => {
      const ph = t.placeholder || "";
      const id = t.id || "";
      return ph.includes("Напиши текст") && !id.includes("prompt") && !id.includes("ai");
    });
  }

  function setPostTextareaText(text) {
    const textarea = findPostTextarea();

    if (!textarea) {
      console.warn("[AI output] post textarea not found");
      return false;
    }

    textarea.value = text || "";
    textarea.dispatchEvent(new Event("input", {bubbles: true}));
    textarea.dispatchEvent(new Event("change", {bubbles: true}));
    textarea.focus();

    return true;
  }

  function removeReadonlyPreviewBlocks() {
    Array.from(document.querySelectorAll("#telegram-ai-editable-wrap-v1, #telegram-ai-editable-result-v1")).forEach(x => {
      try { x.remove(); } catch(e) {}
    });
  }

  const originalFetch = window.fetch;

  window.fetch = async function(input, init) {
    const res = await originalFetch(input, init);

    try {
      const url = String(input || "");

      if (url.includes("/api/telegram/ai_generate_message")) {
        const clone = res.clone();
        const data = await clone.json();

        const text = data.text || data.result || "";

        if (data.ok && text) {
          setTimeout(() => {
            removeReadonlyPreviewBlocks();
            setPostTextareaText(text);
          }, 50);
        }
      }
    } catch (e) {
      console.warn("[AI output textarea patch failed]", e);
    }

    return res;
  };

  // кнопка ручної синхронізації, якщо старий код все ж намалював preview
  window.forceAiResultToPostTextarea = function() {
    const preview = document.getElementById("telegram-ai-editable-result-v1");
    if (preview && preview.value) {
      return setPostTextareaText(preview.value);
    }

    const blocks = Array.from(document.querySelectorAll("pre, div"));
    const b = blocks.find(x => {
      const txt = x.innerText || "";
      return txt.length > 80 && (
        txt.includes("CTA") ||
        txt.includes("Привіт") ||
        txt.includes("Дорогі") ||
        txt.includes("сьогодні")
      );
    });

    if (b) {
      return setPostTextareaText((b.innerText || "").trim());
    }

    return false;
  };

  console.log("[AI output] editable textarea bridge loaded");
})();

// ============================================================================
// /FORCE AI OUTPUT INTO EDITABLE POST TEXTAREA V2
// ============================================================================

// ============================================================================
// CTA STRATEGY BRIDGE TO AI PROMPT V1
// ============================================================================

(function CtaStrategyBridgeToAiPromptV1() {
  if (window.__ctaStrategyBridgeToAiPromptV1) return;
  window.__ctaStrategyBridgeToAiPromptV1 = true;

  function fieldValueByLabel(labelText) {
    const labels = Array.from(document.querySelectorAll("label, div, h4, h3, strong"));
    const label = labels.find(x => (x.textContent || "").trim().includes(labelText));
    if (!label) return "";

    let el = label.nextElementSibling;

    for (let i = 0; i < 5 && el; i++, el = el.nextElementSibling) {
      if (["TEXTAREA", "INPUT", "SELECT"].includes(el.tagName)) {
        return (el.value || "").trim();
      }

      const inner = el.querySelector && el.querySelector("textarea,input,select");
      if (inner) return (inner.value || "").trim();
    }

    return "";
  }

  function buildCtaInstruction() {
    const main = fieldValueByLabel("Основний м’який CTA");
    const cold = fieldValueByLabel("CTA для холодного користувача");
    const warm = fieldValueByLabel("CTA для теплого користувача");
    const hot = fieldValueByLabel("CTA для гарячого користувача");
    const offer = fieldValueByLabel("Офер / куди ведемо");
    const redirect = fieldValueByLabel("Канал редиректу");
    const keywords = fieldValueByLabel("Ключові слова ліда");

    return `
ВИКОРИСТОВУЙ CTA ТІЛЬКИ З ЦЬОГО КОНСТРУКТОРА.

Основний мʼякий CTA:
${main}

CTA для холодного користувача:
${cold}

CTA для теплого користувача:
${warm}

CTA для гарячого користувача:
${hot}

Офер / куди ведемо:
${offer}

Канал редиректу:
${redirect}

Ключові слова ліда:
${keywords}

ЗАБОРОНЕНО:
- вигадувати інший CTA;
- писати "натисни дзвіночок", якщо цього немає в CTA-конструкторі;
- писати "залишайся з нами", якщо цього немає в CTA-конструкторі;
- додавати CTA не по стратегії.

Якщо CTA не підходить до поста — використовуй наймʼякший варіант.
`.trim();
  }

  const originalFetch = window.fetch;

  window.fetch = async function(input, init) {
    const url = String(input || "");

    if (url.includes("/api/telegram/ai_generate_message") && init && init.body) {
      try {
        const payload = JSON.parse(init.body);

        
payload.cta_custom_instruction =
  buildCtaInstruction() +
  "\n\n" +
  (window.buildMultiPlatformCtaInstruction
    ? window.buildMultiPlatformCtaInstruction()
    : "");

        payload.cta_type = "custom";
        payload.cta_style = "soft";
        payload.cta_position = "soft_end";

        init.body = JSON.stringify(payload);

        console.log("[CTA strategy injected]", payload.cta_custom_instruction);
      } catch (e) {
        console.warn("[CTA bridge failed]", e);
      }
    }

    return originalFetch(input, init);
  };
})();

// ============================================================================
// /CTA STRATEGY BRIDGE TO AI PROMPT V1
// ============================================================================

// ============================================================================
// MULTI PLATFORM CTA PROMPT BRIDGE V1
// ============================================================================

(function MultiPlatformCtaPromptBridgeV1() {
  if (window.__multiPlatformCtaPromptBridgeV1) return;
  window.__multiPlatformCtaPromptBridgeV1 = true;

  function val(id) {
    const el = document.getElementById(id);
    return el ? (el.value || "").trim() : "";
  }

  window.buildMultiPlatformCtaInstruction = function() {
    return `
ПЛАТФОРМА CTA:
${val("cta-platform-mode")}

TELEGRAM CTA:
${val("telegram-cta-text")}

TELEGRAM KEYWORDS:
${val("telegram-cta-keywords")}

INSTAGRAM CTA:
${val("instagram-cta-text")}

INSTAGRAM GOAL:
${val("instagram-cta-goal")}

AI МАЄ:
- використовувати CTA тільки з цього конструктора;
- не вигадувати CTA поза правилами;
- адаптувати CTA під платформу;
- для Instagram уникати telegram-style CTA;
- для Telegram уникати instagram-style CTA.
`.trim();
  };

  console.log("[multi platform CTA bridge ready]");
})();

// ============================================================================
// /MULTI PLATFORM CTA PROMPT BRIDGE V1
// ============================================================================
