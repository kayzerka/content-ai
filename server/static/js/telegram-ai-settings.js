// TELEGRAM_AI_SETTINGS_MODAL_V1
(function () {
  const KEY = "telegram_ai_settings_v1";

  const DEFAULT_SETTINGS = {
    main_funnel_goal:
`Плавно перевести людину з Telegram-спілкування до запису на консультацію або ознайомчий сеанс.`,

    tone:
`Тепло, спокійно, людяно.
Без тиску.
Без агресивних продажів.
Створювати відчуття безпеки та довіри.`,

    soft_cta:
`Якщо хочеш — можу пояснити детальніше або допомогти розібрати саме твою ситуацію 🌿`,

    forbidden:
`Не тиснути.
Не маніпулювати страхом.
Не використовувати токсичний sales-tone.
Не сперечатись з людиною.
Не обіцяти магічний результат.`,

    system_prompt:
`Ти AI-асистент Telegram-комунікації.

Твоє завдання:
— відповідати тепло і природно;
— підтримувати діалог;
— аналізувати контекст повідомлення;
— визначати рівень зацікавленості;
— мʼяко переводити людину до консультації;
— не виглядати як бот.

Відповіді мають бути:
— короткими;
— живими;
— людяними;
— без перевантаження текстом.

Якщо людина холодна:
— не продавати;
— спочатку дати користь або пояснення.

Якщо людина тепла:
— можна мʼяко переводити до запису.

Якщо людина готова:
— дати чіткий CTA на запис.`

  };

  function loadSettings() {
    try {
      return {
        ...DEFAULT_SETTINGS,
        ...(JSON.parse(localStorage.getItem(KEY) || "{}"))
      };
    } catch {
      return DEFAULT_SETTINGS;
    }
  }

  function saveSettings(settings) {
    localStorage.setItem(KEY, JSON.stringify(settings || {}));
  }

  function field(name, label, value, rows = 3) {
    return `
      <label>${label}</label>
      <textarea data-tg-ai-setting="${name}" rows="${rows}">${value || ""}</textarea>
    `;
  }

  window.openTelegramAiSettingsPanel = function () {
    document.getElementById("tgAiSettingsPanel")?.remove();

    const s = loadSettings();

    const overlay = document.createElement("div");
    overlay.id = "tgAiSettingsPanel";
    overlay.className = "modal-overlay active";
    overlay.innerHTML = `
      <div class="modal-container" style="max-width:900px;width:92%;max-height:90vh;">
        <div class="modal-header">
          <h3>🤖 TG AI налаштування</h3>
          <button class="modal-close" type="button" onclick="document.getElementById('tgAiSettingsPanel')?.remove()">✕</button>
        </div>
        <div class="modal-body">
          ${field("main_funnel_goal", "Головна ціль Telegram-прогріву", s.main_funnel_goal)}
          ${field("tone", "Тон відповіді", s.tone || "тепло, людяно, без тиску")}
          ${field("soft_cta", "Мʼякий CTA", s.soft_cta)}
          ${field("forbidden", "Що не писати / заборонені формулювання", s.forbidden)}
          ${field("system_prompt", "Системний промт TG AI", s.system_prompt, 7)}
          <pre id="tgAiSettingsResult">Готово до збереження.</pre>
        </div>
        <div class="modal-footer">
          <button class="btn" type="button" onclick="document.getElementById('tgAiSettingsPanel')?.remove()">Закрити</button>
          <button class="btn primary" type="button" id="tgAiSaveBtn">💾 Зберегти TG AI</button>
        </div>
      </div>
    `;

    document.body.appendChild(overlay);

    overlay.querySelector("#tgAiSaveBtn").onclick = function () {
      const settings = {};
      overlay.querySelectorAll("[data-tg-ai-setting]").forEach(el => {
        settings[el.dataset.tgAiSetting] = el.value || "";
      });
      saveSettings(settings);
      overlay.querySelector("#tgAiSettingsResult").textContent = "✅ TG AI налаштування збережено локально";
    };
  };

  window.injectTelegramAiFloatingButton = function () {
    const modal = document.querySelector("#telegramGroupsModal, #tgGroupsModal, .modal-overlay.active");
    if (!modal) return;

    if (modal.querySelector("#tgAiFloatingSettingsBtn")) return;

    const btn = document.createElement("button");
    btn.id = "tgAiFloatingSettingsBtn";
    btn.type = "button";
    btn.textContent = "TG AI ⚙️";
    btn.onclick = () => window.openTelegramAiSettingsPanel();

    btn.style.cssText = `
      position:absolute;
      right:24px;
      bottom:24px;
      z-index:9999;
      border:0;
      border-radius:999px;
      background:#111;
      color:#fff;
      padding:12px 16px;
      font-weight:700;
      box-shadow:0 8px 24px rgba(0,0,0,.25);
      cursor:pointer;
    `;

    const container = modal.querySelector(".modal-container") || modal;
    container.style.position = container.style.position || "relative";
    container.appendChild(btn);
  };
})();
