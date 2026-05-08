// INSTAGRAM_REACTION_MODAL_V1
(function () {
  function closeModal() {
    document.getElementById("igReactionEngineModalOverlay")?.remove();
  }

  window.closeIgReactionEngineModal = closeModal;

  window.openIgReactionEngineModal = async function () {
    let overlay = document.getElementById("igReactionEngineModalOverlay");

    if (!overlay) {
      overlay = document.createElement("div");
      overlay.id = "igReactionEngineModalOverlay";
      overlay.className = "modal-overlay active";
      overlay.innerHTML = `
        <div class="modal-container" style="position:relative;max-width:1180px;width:94%;max-height:92vh;">
          <div class="modal-header">
            <h3>🤖 AI реакції Instagram</h3>
            <div style="display:flex;gap:10px;align-items:center;">
              <button class="modal-close" type="button" onclick="window.closeIgReactionEngineModal()">✕</button>
            </div>
          </div>
          <div class="modal-body">
            
            <div id="igReactionEngineModalBody"></div>

            <button
              id="igReactionFloatingSettingsBtn"
              type="button"
              onclick="window.openIgReactionSettingsPanel && window.openIgReactionSettingsPanel()"
              style="
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
              "
            >
              IG AI ⚙️
            </button>

          </div>
        </div>
      `;
      document.body.appendChild(overlay);

      overlay.addEventListener("click", function (e) {
        if (e.target === overlay) closeModal();
      });
    }

    const body = document.getElementById("igReactionEngineModalBody");
    if (!body) return;

    if (typeof window.igReactionEngineLoad !== "function") {
      body.innerHTML = `<div style="padding:18px;color:#991b1b;font-weight:700;">IG Reaction Engine не завантажився</div>`;
      return;
    }

    await window.igReactionEngineLoad();

    const box = document.getElementById("igReactionEngineBox");
    if (box && !body.contains(box)) {
      body.appendChild(box);
    }
  };
})();
