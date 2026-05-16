(function () {
  const API = "/api/courses";

  let courses = [];
  let currentCourseKey = null;
  let currentCourse = null;
  let currentLessonNo = 1;

  function el(id) {
    return document.getElementById(id);
  }

  function safeText(v) {
    return v == null ? "" : String(v);
  }

  async function apiGet(url) {
    const r = await fetch(url);
    const j = await r.json();
    if (!r.ok || j.ok === false) throw new Error(j.detail || j.error || "API error");
    return j;
  }

  async function apiPost(url, data) {
    const r = await fetch(url, {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(data || {})
    });
    const j = await r.json();
    if (!r.ok || j.ok === false) throw new Error(j.detail || j.error || "API error");
    return j;
  }

  function showStatus(msg, isError=false) {
    const box = el("courses-status");
    if (!box) return;
    box.textContent = msg || "";
    box.style.color = isError ? "#b91c1c" : "#166534";
  }

  async function loadCourses() {
    try {
      const data = await apiGet(API);
      courses = data.courses || [];
      renderCourseList();
      showStatus("Курси завантажено");
    } catch (e) {
      showStatus("Помилка завантаження курсів: " + e.message, true);
    }
  }

  function renderCourseList() {
    const list = el("courses-list");
    if (!list) return;

    if (!courses.length) {
      list.innerHTML = `<div class="muted">Курсів ще немає</div>`;
      return;
    }

    list.innerHTML = courses.map(c => `
      <button class="course-item ${c.course_key === currentCourseKey ? "active" : ""}"
              data-course-key="${c.course_key}">
        <b>${safeText(c.title)}</b>
        <span>${safeText(c.status || "draft")} · уроків: ${c.lessons_count || 0}</span>
      </button>
    `).join("");

    list.querySelectorAll("[data-course-key]").forEach(btn => {
      btn.addEventListener("click", () => openCourse(btn.dataset.courseKey));
    });
  }

  async function createCourse() {
    const title = prompt("Назва курсу?");
    if (!title) return;

    try {
      const data = await apiPost(API + "/create", {
        title,
        description: "",
        telegram_chat_id: "",
        telegram_channel_url: "",
        ai_system_prompt: "Пиши українською, структурно, глибоко, але зрозуміло."
      });
      currentCourseKey = data.course_key;
      await loadCourses();
      await openCourse(currentCourseKey);
      showStatus("Курс створено");
    } catch (e) {
      showStatus("Помилка створення курсу: " + e.message, true);
    }
  }

  async function openCourse(courseKey) {
    try {
      currentCourseKey = courseKey;
      const data = await apiGet(API + "/" + encodeURIComponent(courseKey));
      currentCourse = data;
      renderCourseList();
      renderCourseEditor();
      showStatus("Курс відкрито");
    } catch (e) {
      showStatus("Помилка відкриття курсу: " + e.message, true);
    }
  }

  function renderCourseEditor() {
    const wrap = el("course-editor");
    if (!wrap || !currentCourse) return;

    const c = currentCourse.course;
    const lessons = currentCourse.lessons || [];

    wrap.innerHTML = `
      <div class="course-card">
        <h2>Редактор курсу</h2>

        <label>Назва курсу</label>
        <input id="course-title" value="${escapeHtml(c.title)}">

        <label>Опис</label>
        <textarea id="course-description">${escapeHtml(c.description || "")}</textarea>

        <label>Telegram канал</label>
        <select id="course-telegram-chat-id">
          <option value="">-- вибрати Telegram канал --</option>
        </select>
        <div style="margin-top:6px;font-size:12px;color:#6b7280;">
          Поточний: ${escapeHtml(c.telegram_chat_id || "")}
        </div>

        <label>Telegram channel URL</label>
        <input id="course-telegram-url" value="${escapeHtml(c.telegram_channel_url || "")}">

        <label>AI system prompt</label>
        <textarea id="course-ai-system-prompt">${escapeHtml(c.ai_system_prompt || "")}</textarea>

        <div class="course-actions">
          <button id="course-save-btn">💾 Зберегти курс</button>
          <button id="course-backup-btn">🧷 Backup now</button>
          <button id="course-restore-btn">♻️ Restore backup</button>
        </div>
      </div>

      <div class="course-card">
        <div class="course-row">
          <h2>Уроки</h2>
          <button id="lesson-add-btn">+ Додати урок</button>
        </div>

        <div id="lessons-tabs">
          ${renderLessonsTabs(lessons)}
        </div>

        <div id="lesson-editor"></div>
      </div>
    `;

    loadTelegramTargets(c.telegram_chat_id || "");

    el("course-save-btn").addEventListener("click", saveCourse);
    el("course-backup-btn").addEventListener("click", backupNow);
    el("course-restore-btn").addEventListener("click", restoreBackup);
    el("lesson-add-btn").addEventListener("click", addLesson);

    const firstLesson = lessons[0];
    currentLessonNo = firstLesson ? Number(firstLesson.lesson_no) : 1;
    renderLessonEditor(currentLessonNo);

    document.querySelectorAll("[data-lesson-no]").forEach(btn => {
      btn.addEventListener("click", () => {
        currentLessonNo = Number(btn.dataset.lessonNo);
        renderLessonEditor(currentLessonNo);
      });
    });
  }

  function renderLessonsTabs(lessons) {
    if (!lessons.length) {
      return `<div class="muted">Уроків ще немає. Натисни “Додати урок”.</div>`;
    }

    return lessons.map(l => `
      <button class="lesson-tab ${Number(l.lesson_no) === currentLessonNo ? "active" : ""}"
              data-lesson-no="${l.lesson_no}">
        Урок ${l.lesson_no}
      </button>
    `).join("");
  }

  function getLesson(lessonNo) {
    const lessons = currentCourse?.lessons || [];
    return lessons.find(l => Number(l.lesson_no) === Number(lessonNo)) || {
      course_key: currentCourseKey,
      lesson_no: lessonNo,
      title: "",
      topic: "",
      ai_prompt: "",
      lecture_text: "",
      telegram_post_text: "",
      status: "draft"
    };
  }

  function renderLessonEditor(lessonNo) {
    const box = el("lesson-editor");
    if (!box || !currentCourse) return;

    const l = getLesson(lessonNo);

    box.innerHTML = `
      <div class="lesson-editor-box">
        <h3>Урок ${lessonNo}</h3>

        <label>Назва уроку</label>
        <input id="lesson-title" value="${escapeHtml(l.title || "")}">

        <label>Тема</label>
        <input id="lesson-topic" value="${escapeHtml(l.topic || "")}">

        <label>AI prompt для уроку</label>
        <textarea id="lesson-ai-prompt">${escapeHtml(l.ai_prompt || "")}</textarea>

        <label>Текст лекції</label>
        <textarea id="lesson-lecture" class="big-textarea">${escapeHtml(l.lecture_text || "")}</textarea>

        <label>Telegram пост</label>
        <textarea id="lesson-telegram-post" class="big-textarea">${escapeHtml(l.telegram_post_text || "")}</textarea>

        <label>Статус</label>
        <select id="lesson-status">
          <option value="draft" ${l.status === "draft" ? "selected" : ""}>draft</option>
          <option value="ready" ${l.status === "ready" ? "selected" : ""}>ready</option>
          <option value="published" ${l.status === "published" ? "selected" : ""}>published</option>
        </select>

        <div class="course-actions">
          <button id="lesson-save-btn">💾 Зберегти урок</button>
          <button id="lesson-publish-btn">🚀 Опублікувати у канал</button>
          <button id="lesson-excel-btn">📊 Створити Excel</button>
          <button id="lesson-tables-btn">📊 Таблиці уроку</button>
          <button id="lesson-upload-btn">📎 Upload файл</button>
          <button id="lesson-video-upload-btn">🎥 Upload відео</button>
          <input id="lesson-file-input" type="file" style="display:none" multiple>
          <input id="lesson-video-input" type="file" accept="video/*" style="display:none" multiple>
        </div>

        <div id="lesson-assets">
          ${renderAssets(lessonNo)}
        </div>
      </div>
    `;

    el("lesson-save-btn").addEventListener("click", saveLesson);
    el("lesson-publish-btn").addEventListener("click", publishLesson);
    el("lesson-excel-btn").addEventListener("click", createLessonExcel);
    el("lesson-tables-btn").addEventListener("click", openLessonTablesManager);
    el("lesson-upload-btn").addEventListener("click", () => el("lesson-file-input").click());
    el("lesson-file-input").addEventListener("change", uploadLessonFiles);
    el("lesson-video-upload-btn").addEventListener("click", () => el("lesson-video-input").click());
    el("lesson-video-input").addEventListener("change", uploadLessonVideos);
  }

  function renderAssets(lessonNo) {
    const assets = (currentCourse?.assets || []).filter(a => Number(a.lesson_no) === Number(lessonNo));
    if (!assets.length) return `<div class="muted">Файлів до уроку ще немає</div>`;

    return `
      <h4>Матеріали уроку</h4>
      <ul>
        ${assets.map(a => `
          <li>${safeText(a.asset_type)} · ${safeText(a.file_name)} · ${safeText(a.mime_type || "")} ${a.asset_type === "spreadsheet" ? `<button onclick="window.openExcelModal(${a.id})">📊 Відкрити</button>` : ""}</li>
        `).join("")}
      </ul>
    `;
  }


  async function loadTelegramTargets(selectedValue) {
    const select = el("course-telegram-chat-id");
    if (!select) return;

    try {
      const data = await apiGet(API + "/telegram/targets");
      const targets = data.targets || [];

      select.innerHTML = `<option value="">-- вибрати Telegram канал --</option>` + targets.map(t => {
        const label = [
          t.title || "",
          t.username ? ("@" + t.username) : "",
          t.chat_id || ""
        ].filter(Boolean).join(" · ");

        return `<option value="${escapeHtml(t.chat_id)}">${escapeHtml(label)}</option>`;
      }).join("");

      if (selectedValue) select.value = selectedValue;
    } catch (e) {
      console.error("[Courses] telegram targets load error", e);
    }
  }

  async function saveCourse() {
    try {
      await apiPost(API + "/save", {
        course_key: currentCourseKey,
        title: el("course-title").value,
        description: el("course-description").value,
        telegram_chat_id: el("course-telegram-chat-id").value,
        telegram_channel_url: el("course-telegram-url").value,
        ai_system_prompt: el("course-ai-system-prompt").value,
        status: "draft"
      });
      await loadCourses();
      await openCourse(currentCourseKey);
      showStatus("Курс збережено + backup оновлено");
    } catch (e) {
      showStatus("Помилка збереження курсу: " + e.message, true);
    }
  }

  async function saveLesson() {
    try {
      await apiPost(API + "/lesson/save", {
        course_key: currentCourseKey,
        lesson_no: currentLessonNo,
        title: el("lesson-title").value,
        topic: el("lesson-topic").value,
        ai_prompt: el("lesson-ai-prompt").value,
        lecture_text: el("lesson-lecture").value,
        telegram_post_text: el("lesson-telegram-post").value,
        status: el("lesson-status").value
      });
      await openCourse(currentCourseKey);
      showStatus("Урок збережено + backup оновлено");
    } catch (e) {
      showStatus("Помилка збереження уроку: " + e.message, true);
    }
  }

  async function addLesson() {
    if (!currentCourseKey) return;

    const lessons = currentCourse?.lessons || [];
    const nextNo = lessons.length ? Math.max(...lessons.map(l => Number(l.lesson_no))) + 1 : 1;
    currentLessonNo = nextNo;

    try {
      await apiPost(API + "/lesson/save", {
        course_key: currentCourseKey,
        lesson_no: nextNo,
        title: "Урок " + nextNo,
        topic: "",
        ai_prompt: "",
        lecture_text: "",
        telegram_post_text: "",
        status: "draft"
      });
      await openCourse(currentCourseKey);
      showStatus("Урок додано");
    } catch (e) {
      showStatus("Помилка додавання уроку: " + e.message, true);
    }
  }



  async function createLessonExcel() {
    if (!currentCourseKey || !currentLessonNo) return;

    try {
      await saveLesson();

      const data = await apiPost(API + "/lesson/create-excel", {
        course_key: currentCourseKey,
        lesson_no: currentLessonNo,
        file_name: "lesson_" + currentLessonNo + "_materials.xlsx"
      });

      await openCourse(currentCourseKey);
      showStatus("Excel створено: " + (data.file_name || ""));
    } catch (e) {
      showStatus("Помилка створення Excel: " + e.message, true);
      alert("Помилка Excel: " + e.message);
    }
  }

  async function publishLesson() {
    const chatId = el("course-telegram-chat-id") ? el("course-telegram-chat-id").value.trim() : "";

    if (!chatId) {
      alert("Спочатку вибери Telegram канал у налаштуваннях курсу і збережи курс.");
      return;
    }

    // no confirm

    try {
      await saveLesson();

      const data = await apiPost(API + "/publish/lesson", {
        course_key: currentCourseKey,
        lesson_no: currentLessonNo,
        telegram_chat_id: chatId
      });

      await openCourse(currentCourseKey);
      showStatus("Урок опубліковано у канал. message_id=" + (data.message_id || ""));
    } catch (e) {
      showStatus("Помилка публікації: " + e.message, true);
      alert("Помилка публікації: " + e.message);
    }
  }


  async function uploadLessonVideos(ev) {
    const files = Array.from(ev.target.files || []);
    if (!files.length) return;

    try {
      for (const file of files) {
        const fd = new FormData();
        fd.append("course_key", currentCourseKey);
        fd.append("lesson_no", currentLessonNo);
        fd.append("asset_type", "video");
        fd.append("file", file);

        const r = await fetch(API + "/assets/upload", {
          method: "POST",
          body: fd
        });

        const j = await r.json();
        if (!r.ok || j.ok === false) throw new Error(j.detail || j.error || "video upload error");
      }

      await openCourse(currentCourseKey);
      showStatus("Відео завантажено + backup оновлено");
    } catch (e) {
      showStatus("Помилка upload відео: " + e.message, true);
      alert("Помилка upload відео: " + e.message);
    }
  }


  async function uploadLessonFiles(ev) {
    const files = Array.from(ev.target.files || []);
    if (!files.length) return;

    try {
      for (const file of files) {
        const fd = new FormData();
        fd.append("course_key", currentCourseKey);
        fd.append("lesson_no", currentLessonNo);
        fd.append("asset_type", detectAssetType(file));
        fd.append("file", file);

        const r = await fetch(API + "/assets/upload", {
          method: "POST",
          body: fd
        });
        const j = await r.json();
        if (!r.ok || j.ok === false) throw new Error(j.detail || j.error || "upload error");
      }

      await openCourse(currentCourseKey);
      showStatus("Файли завантажено + backup оновлено");
    } catch (e) {
      showStatus("Помилка upload: " + e.message, true);
    }
  }

  function detectAssetType(file) {
    const name = (file.name || "").toLowerCase();
    const type = file.type || "";

    if (type.startsWith("image/")) return "image";
    if (type.startsWith("video/")) return "video";
    if (name.endsWith(".xlsx") || name.endsWith(".xls") || name.endsWith(".csv")) return "spreadsheet";
    if (name.endsWith(".pdf")) return "pdf";
    return "document";
  }

  async function backupNow() {
    try {
      const data = await apiPost(API + "/backup/auto_save_all", {});
      showStatus("Backup створено: " + JSON.stringify(data.counts || {}));
    } catch (e) {
      showStatus("Backup error: " + e.message, true);
    }
  }

  async function restoreBackup() {
    // no confirm

    try {
      await apiPost(API + "/restore/from_static_backup", {});
      await loadCourses();
      currentCourseKey = null;
      currentCourse = null;
      if (el("course-editor")) el("course-editor").innerHTML = "";
      showStatus("Courses відновлено з backup");
    } catch (e) {
      showStatus("Restore error: " + e.message, true);
    }
  }

  function escapeHtml(str) {
    return safeText(str)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;");
  }

  function initCoursesUI() {
    const section = document.getElementById("courses");
    if (section) {
      section.style.display = "block";
      section.hidden = false;
      section.classList.remove("hidden");
      section.classList.add("active");
    }

    const root = el("courses-root");
    if (!root) {
      console.warn("[Courses] courses-root not found");
      return;
    }

    console.log("[Courses] initCoursesUI render start");

    root.innerHTML = `
      <div class="courses-layout">
        <aside class="courses-sidebar">
          <div class="course-row">
            <h2>Courses</h2>
            <button id="course-create-btn">+ Курс</button>
          </div>

          <div class="course-actions" style="margin-bottom:12px;">
            <button id="courses-global-restore-btn">♻️ Відновити дані</button>
            <button id="courses-global-backup-btn">🧷 Backup</button>
          </div>

          <div id="courses-list"></div>
        </aside>

        <main class="courses-main">
          <div id="courses-status"></div>
          <div id="course-editor" class="muted">Обери курс або створи новий.</div>
        </main>
      </div>
    `;

    el("course-create-btn").addEventListener("click", createCourse);
    el("courses-global-restore-btn").addEventListener("click", restoreBackup);
    el("courses-global-backup-btn").addEventListener("click", backupNow);
    loadCourses();
  }



  function openLessonTablesManager() {
    const spreadsheets = (currentCourse?.assets || []).filter(a =>
      Number(a.lesson_no) === Number(currentLessonNo) && a.asset_type === "spreadsheet"
    );

    let modal = document.getElementById("tables-manager-modal");
    if (!modal) {
      modal = document.createElement("div");
      modal.id = "tables-manager-modal";
      modal.className = "excel-modal";
      document.body.appendChild(modal);
    }

    modal.style.display = "block";
    modal.style.left = modal.style.left || "120px";
    modal.style.top = modal.style.top || "100px";
    modal.style.width = modal.style.width || "760px";
    modal.style.height = modal.style.height || "440px";

    const listHtml = spreadsheets.length
      ? spreadsheets.map(a => `
          <div class="table-manager-row">
            <div>
              <b>${escapeHtml(a.file_name || "")}</b>
              <div style="font-size:12px;color:#6b7280;">asset_id=${a.id} · ${escapeHtml(a.file_path || "")}</div>
            </div>
            <div class="table-manager-actions">
              <button onclick="window.openExcelModal(${a.id})">📊 Редагувати</button>
              <button onclick="window.CoursesModule.deleteLessonTable(${a.id})">🗑 Видалити</button>
            </div>
          </div>
        `).join("")
      : `<div class="muted">У цьому уроці ще немає Excel-таблиць.</div>`;

    modal.innerHTML = `
      <div class="excel-modal-header" id="tables-manager-header">
        <b>📊 Таблиці уроку ${currentLessonNo}</b>
        <div>
          <button id="tables-manager-create-btn">+ Створити Excel</button>
          <button id="tables-manager-close-btn">✕</button>
        </div>
      </div>

      <div style="padding:12px;overflow:auto;height:calc(100% - 48px);">
        ${listHtml}
      </div>

      <div class="excel-resize-handle" id="tables-manager-resize"></div>
    `;

    document.getElementById("tables-manager-close-btn").onclick = () => {
      modal.style.display = "none";
    };

    document.getElementById("tables-manager-create-btn").onclick = async () => {
      await createLessonExcel();
      await openCourse(currentCourseKey);
      openLessonTablesManager();
    };

    makeTablesManagerDraggable(modal, "tables-manager-header");
    makeTablesManagerResizable(modal, "tables-manager-resize");
  }

  async function deleteLessonTable(assetId) {
    try {
      const data = await apiPost(API + "/assets/delete", { asset_id: assetId });
      await openCourse(currentCourseKey);
      openLessonTablesManager();
      showStatus("Таблицю видалено: " + assetId);
    } catch (e) {
      showStatus("Помилка видалення таблиці: " + e.message, true);
      alert("Delete error: " + e.message);
    }
  }

  function makeTablesManagerDraggable(modal, headerId) {
    const header = document.getElementById(headerId);
    if (!header) return;

    let dragging = false, sx = 0, sy = 0, sl = 0, st = 0;

    header.onmousedown = e => {
      if (e.target.tagName === "BUTTON") return;
      dragging = true;
      sx = e.clientX;
      sy = e.clientY;
      sl = parseInt(modal.style.left || "120", 10);
      st = parseInt(modal.style.top || "100", 10);
    };

    window.addEventListener("mousemove", e => {
      if (!dragging) return;
      modal.style.left = (sl + e.clientX - sx) + "px";
      modal.style.top = (st + e.clientY - sy) + "px";
    });

    window.addEventListener("mouseup", () => {
      dragging = false;
    });
  }

  function makeTablesManagerResizable(modal, handleId) {
    const handle = document.getElementById(handleId);
    if (!handle) return;

    let resizing = false, sx = 0, sy = 0, sw = 0, sh = 0;

    handle.onmousedown = e => {
      resizing = true;
      sx = e.clientX;
      sy = e.clientY;
      sw = modal.offsetWidth;
      sh = modal.offsetHeight;
      e.preventDefault();
    };

    window.addEventListener("mousemove", e => {
      if (!resizing) return;
      modal.style.width = Math.max(520, sw + e.clientX - sx) + "px";
      modal.style.height = Math.max(320, sh + e.clientY - sy) + "px";
    });

    window.addEventListener("mouseup", () => {
      resizing = false;
    });
  }


  window.CoursesModule = {
    init: initCoursesUI,
    load: loadCourses,
    deleteLessonTable: deleteLessonTable
  };

  document.addEventListener("DOMContentLoaded", initCoursesUI);
})();

window.openExcelModal = async function(assetId) {
  const API = "/api/courses";

  const r = await fetch(API + "/assets/excel/read", {
    method: "POST",
    headers: {"Content-Type":"application/json"},
    body: JSON.stringify({asset_id: assetId})
  });
  const data = await r.json();
  if (!r.ok || data.ok === false) {
    alert("Excel read error: " + (data.detail || data.error || "unknown"));
    return;
  }

  let sheets = data.sheets || [];
  let active = 0;

  let modal = document.getElementById("excel-modal");
  if (!modal) {
    modal = document.createElement("div");
    modal.id = "excel-modal";
    modal.className = "excel-modal";
    document.body.appendChild(modal);
  }

  modal.style.display = "block";
  modal.style.left = modal.style.left || "80px";
  modal.style.top = modal.style.top || "80px";
  modal.style.width = modal.style.width || "900px";
  modal.style.height = modal.style.height || "620px";

  function esc(v) {
    return String(v ?? "")
      .replaceAll("&","&amp;")
      .replaceAll("<","&lt;")
      .replaceAll(">","&gt;")
      .replaceAll('"',"&quot;");
  }

  function colName(i) {
    let s = "";
    let n = i + 1;
    while (n > 0) {
      let r = (n - 1) % 26;
      s = String.fromCharCode(65 + r) + s;
      n = Math.floor((n - 1) / 26);
    }
    return s;
  }

  function render() {
    const sheet = sheets[active] || {name:"Sheet", rows:[]};
    const rows = sheet.rows || [];
    const maxCols = Math.max(8, ...rows.map(r => (r || []).length));

    let tabs = sheets.map((s, i) =>
      `<button data-sheet="${i}" style="margin:6px;padding:6px;border-radius:8px;${i===active?'background:#eef2ff;border:1px solid #6366f1;':''}">${esc(s.name)}</button>`
    ).join("");

    let html = `
      <div class="excel-modal-header" id="excel-modal-header">
        <b>📊 ${esc(data.asset.file_name || "Excel")}</b>
        <div>
          <button id="excel-add-row">+ Row</button>
          <button id="excel-add-col">+ Col</button>
          <button id="excel-save">💾 Save XLSX</button>
          <button id="excel-close">✕</button>
        </div>
      </div>
      <div>${tabs}</div>
      <div class="excel-table-wrap">
        <table class="excel-grid"><thead><tr><th></th>`;

    for (let c = 0; c < maxCols; c++) html += `<th>${colName(c)}</th>`;
    html += `</tr></thead><tbody>`;

    for (let r = 0; r < rows.length; r++) {
      html += `<tr><th>${r+1}</th>`;
      for (let c = 0; c < maxCols; c++) {
        html += `<td contenteditable="true" data-r="${r}" data-c="${c}">${esc(rows[r]?.[c] ?? "")}</td>`;
      }
      html += `</tr>`;
    }

    html += `</tbody></table></div><div class="excel-resize-handle" id="excel-resize-handle"></div>`;
    modal.innerHTML = html;

    modal.querySelectorAll("[data-sheet]").forEach(btn => {
      btn.onclick = () => { active = Number(btn.dataset.sheet); render(); };
    });

    modal.querySelectorAll("td[contenteditable]").forEach(td => {
      td.oninput = () => {
        const r = Number(td.dataset.r), c = Number(td.dataset.c);
        if (!sheets[active].rows[r]) sheets[active].rows[r] = [];
        sheets[active].rows[r][c] = td.innerText;
      };
    });

    document.getElementById("excel-close").onclick = () => modal.style.display = "none";
    document.getElementById("excel-add-row").onclick = () => {
      const maxCols = Math.max(8, ...rows.map(r => (r || []).length));
      sheets[active].rows.push(Array(maxCols).fill(""));
      render();
    };
    document.getElementById("excel-add-col").onclick = () => {
      sheets[active].rows.forEach(r => r.push(""));
      render();
    };
    document.getElementById("excel-save").onclick = save;

    enableDrag();
    enableResize();
  }

  async function save() {
    const r = await fetch(API + "/assets/excel/save", {
      method: "POST",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify({asset_id: assetId, sheets})
    });
    const j = await r.json();
    if (!r.ok || j.ok === false) {
      alert("Excel save error: " + (j.detail || j.error || "unknown"));
      return;
    }
    alert("Excel збережено");
  }

  function enableDrag() {
    const header = document.getElementById("excel-modal-header");
    let dragging = false, sx=0, sy=0, sl=0, st=0;
    header.onmousedown = e => {
      if (e.target.tagName === "BUTTON") return;
      dragging = true; sx=e.clientX; sy=e.clientY;
      sl=parseInt(modal.style.left || "80",10); st=parseInt(modal.style.top || "80",10);
    };
    window.onmousemove = e => {
      if (!dragging) return;
      modal.style.left = (sl + e.clientX - sx) + "px";
      modal.style.top = (st + e.clientY - sy) + "px";
    };
    window.onmouseup = () => dragging = false;
  }

  function enableResize() {
    const handle = document.getElementById("excel-resize-handle");
    let resizing = false, sx=0, sy=0, sw=0, sh=0;
    handle.onmousedown = e => {
      resizing = true; sx=e.clientX; sy=e.clientY; sw=modal.offsetWidth; sh=modal.offsetHeight;
      e.preventDefault();
    };
    window.addEventListener("mousemove", e => {
      if (!resizing) return;
      modal.style.width = Math.max(520, sw + e.clientX - sx) + "px";
      modal.style.height = Math.max(360, sh + e.clientY - sy) + "px";
    });
    window.addEventListener("mouseup", () => resizing = false);
  }

  render();
};

window.openLessonTablesManager = function() {
  const spreadsheets = (currentCourse?.assets || []).filter(a =>
    Number(a.lesson_no) === Number(currentLessonNo) && a.asset_type === "spreadsheet"
  );

  let modal = document.getElementById("tables-manager-modal");
  if (!modal) {
    modal = document.createElement("div");
    modal.id = "tables-manager-modal";
    modal.className = "excel-modal";
    document.body.appendChild(modal);
  }

  modal.style.display = "block";
  modal.style.left = modal.style.left || "120px";
  modal.style.top = modal.style.top || "100px";
  modal.style.width = modal.style.width || "720px";
  modal.style.height = modal.style.height || "420px";

  const listHtml = spreadsheets.length
    ? spreadsheets.map(a => `
        <div class="table-manager-row">
          <div>
            <b>${String(a.file_name || "")}</b>
            <div style="font-size:12px;color:#6b7280;">asset_id=${a.id} · ${a.file_path || ""}</div>
          </div>
          <div class="table-manager-actions">
            <button onclick="window.openExcelModal(${a.id})">📊 Редагувати</button>
            <button onclick="window.deleteLessonTable(${a.id})">🗑 Видалити</button>
          </div>
        </div>
      `).join("")
    : `<div class="muted">У цьому уроці ще немає Excel-таблиць.</div>`;

  modal.innerHTML = `
    <div class="excel-modal-header" id="tables-manager-header">
      <b>📊 Таблиці уроку ${currentLessonNo}</b>
      <div>
        <button onclick="window.createTableFromManager()">+ Створити Excel</button>
        <button onclick="document.getElementById('tables-manager-modal').style.display='none'">✕</button>
      </div>
    </div>

    <div style="padding:12px;overflow:auto;height:calc(100% - 48px);">
      ${listHtml}
    </div>

    <div class="excel-resize-handle" id="tables-manager-resize"></div>
  `;

  makeSimpleModalDraggable(modal, "tables-manager-header");
  makeSimpleModalResizable(modal, "tables-manager-resize");
};

window.createTableFromManager = async function() {
  if (typeof createLessonExcel === "function") {
    await createLessonExcel();
  } else {
    alert("createLessonExcel не знайдено");
  }
  setTimeout(() => window.openLessonTablesManager(), 300);
};

window.deleteLessonTable = async function(assetId) {
  try {
    const r = await fetch("/api/courses/assets/delete", {
      method: "POST",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify({asset_id: assetId})
    });
    const j = await r.json();

    if (!r.ok || j.ok === false) {
      alert("Delete error: " + (j.detail || j.error || "unknown"));
      return;
    }

    await openCourse(currentCourseKey);
    window.openLessonTablesManager();
  } catch (e) {
    alert("Delete error: " + e.message);
  }
};

function makeSimpleModalDraggable(modal, headerId) {
  const header = document.getElementById(headerId);
  if (!header) return;

  let dragging = false, sx = 0, sy = 0, sl = 0, st = 0;

  header.onmousedown = e => {
    if (e.target.tagName === "BUTTON") return;
    dragging = true;
    sx = e.clientX;
    sy = e.clientY;
    sl = parseInt(modal.style.left || "120", 10);
    st = parseInt(modal.style.top || "100", 10);
  };

  window.addEventListener("mousemove", e => {
    if (!dragging) return;
    modal.style.left = (sl + e.clientX - sx) + "px";
    modal.style.top = (st + e.clientY - sy) + "px";
  });

  window.addEventListener("mouseup", () => {
    dragging = false;
  });
}

function makeSimpleModalResizable(modal, handleId) {
  const handle = document.getElementById(handleId);
  if (!handle) return;

  let resizing = false, sx = 0, sy = 0, sw = 0, sh = 0;

  handle.onmousedown = e => {
    resizing = true;
    sx = e.clientX;
    sy = e.clientY;
    sw = modal.offsetWidth;
    sh = modal.offsetHeight;
    e.preventDefault();
  };

  window.addEventListener("mousemove", e => {
    if (!resizing) return;
    modal.style.width = Math.max(520, sw + e.clientX - sx) + "px";
    modal.style.height = Math.max(320, sh + e.clientY - sy) + "px";
  });

  window.addEventListener("mouseup", () => {
    resizing = false;
  });
}
