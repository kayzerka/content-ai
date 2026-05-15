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
          <button id="lesson-upload-btn">📎 Upload файл</button>
          <input id="lesson-file-input" type="file" style="display:none" multiple>
        </div>

        <div id="lesson-assets">
          ${renderAssets(lessonNo)}
        </div>
      </div>
    `;

    el("lesson-save-btn").addEventListener("click", saveLesson);
    el("lesson-upload-btn").addEventListener("click", () => el("lesson-file-input").click());
    el("lesson-file-input").addEventListener("change", uploadLessonFiles);
  }

  function renderAssets(lessonNo) {
    const assets = (currentCourse?.assets || []).filter(a => Number(a.lesson_no) === Number(lessonNo));
    if (!assets.length) return `<div class="muted">Файлів до уроку ще немає</div>`;

    return `
      <h4>Матеріали уроку</h4>
      <ul>
        ${assets.map(a => `
          <li>${safeText(a.asset_type)} · ${safeText(a.file_name)} · ${safeText(a.mime_type || "")}</li>
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
    if (!confirm("Відновити Courses з backups/courses/courses-latest.json? Поточні course таблиці будуть перезаписані.")) return;

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

  window.CoursesModule = {
    init: initCoursesUI,
    load: loadCourses
  };

  document.addEventListener("DOMContentLoaded", initCoursesUI);
})();
