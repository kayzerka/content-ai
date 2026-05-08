const PlatformPostingSettings = (function() {
  function getHtml() {
    return `
      <div class="card">
        <h3>⚙️ Налаштування постингу по платформах</h3>

        <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap:16px;">

          <div class="card" style="box-shadow:none; border:1px solid #e5e7eb;">
            <h3>📸 Instagram</h3>
            <label>Тип публікації</label>
            <select id="post_ig_type">
              <option value="image">Image Post</option>
              <option value="reel">Reel</option>
              <option value="carousel">Carousel</option>
              <option value="story">Story</option>
            </select>

            <label>Локація / геомітка</label>
            <input id="post_ig_location" placeholder="Наприклад: Wesel, Germany" />

            <label>Alt text</label>
            <input id="post_ig_alt_text" placeholder="Опис зображення для доступності" />

            <label>Коментар після публікації</label>
            <textarea id="post_ig_first_comment" rows="3" placeholder="Перший коментар / хештеги"></textarea>

            <label>
              <input id="post_ig_share_to_feed" type="checkbox" checked style="width:auto;" />
              Показувати Reel у стрічці
            </label>
          </div>

          <div class="card" style="box-shadow:none; border:1px solid #e5e7eb;">
            <h3>▶️ YouTube</h3>

            <label>Доступ до відео</label>
            <select id="post_yt_privacy">
              <option value="private">Private</option>
              <option value="unlisted">Unlisted</option>
              <option value="public">Public</option>
            </select>

            <label>Тип</label>
            <select id="post_yt_type">
              <option value="shorts">Shorts</option>
              <option value="video">Long Video</option>
            </select>

            <label>Категорія</label>
            <select id="post_yt_category">
              <option value="22">People & Blogs</option>
              <option value="24">Entertainment</option>
              <option value="27">Education</option>
              <option value="26">Howto & Style</option>
            </select>

            <label>Made for kids?</label>
            <select id="post_yt_made_for_kids">
              <option value="false">Ні</option>
              <option value="true">Так</option>
            </select>

            <label>Теги YouTube</label>
            <input id="post_yt_tags" placeholder="регресія, карма, духовність" />

            <label>Thumbnail path / URL</label>
            <input id="post_yt_thumbnail" placeholder="/path/to/thumb.jpg або URL" />
          </div>

          <div class="card" style="box-shadow:none; border:1px solid #e5e7eb;">
            <h3>🎵 TikTok</h3>

            <label>Privacy</label>
            <select id="post_tt_privacy">
              <option value="PUBLIC_TO_EVERYONE">Public</option>
              <option value="MUTUAL_FOLLOW_FRIENDS">Friends</option>
              <option value="SELF_ONLY">Private</option>
            </select>

            <label>
              <input id="post_tt_allow_comments" type="checkbox" checked style="width:auto;" />
              Дозволити коментарі
            </label>

            <label>
              <input id="post_tt_allow_duet" type="checkbox" style="width:auto;" />
              Дозволити Duet
            </label>

            <label>
              <input id="post_tt_allow_stitch" type="checkbox" style="width:auto;" />
              Дозволити Stitch
            </label>
          </div>

          <div class="card" style="box-shadow:none; border:1px solid #e5e7eb;">
            <h3>📘 Facebook</h3>

            <label>Privacy</label>
            <select id="post_fb_privacy">
              <option value="public">Public</option>
              <option value="friends">Friends</option>
              <option value="only_me">Only me</option>
            </select>

            <label>Локація</label>
            <input id="post_fb_location" placeholder="Місто / місце" />

            <label>
              <input id="post_fb_crosspost" type="checkbox" checked style="width:auto;" />
              Crosspost з Instagram, якщо доступно
            </label>
          </div>

        </div>

        <div class="card" style="box-shadow:none; border:1px solid #e5e7eb;">
          <h3>⏰ Відкладений постинг</h3>

          <label>
            <input id="post_schedule_enabled" type="checkbox" style="width:auto;" />
            Запланувати публікацію
          </label>

          <label>Дата і час</label>
          <input id="post_scheduled_at" type="datetime-local" />

          <div class="toolbar">
            <button class="btn" onclick="CalendarModal.open()">📅 Відкрити календар</button>
            <button class="btn primary" onclick="PlatformPostingSettings.collect()">💾 Зібрати налаштування</button>
          </div>

          <pre id="post_settings_preview">Налаштування ще не зібрані.</pre>
        </div>
      </div>
    `;
  }

  function collect() {
    const data = {
      instagram: {
        type: document.getElementById('post_ig_type')?.value,
        location: document.getElementById('post_ig_location')?.value,
        alt_text: document.getElementById('post_ig_alt_text')?.value,
        first_comment: document.getElementById('post_ig_first_comment')?.value,
        share_to_feed: document.getElementById('post_ig_share_to_feed')?.checked
      },
      youtube: {
        privacy_status: document.getElementById('post_yt_privacy')?.value,
        type: document.getElementById('post_yt_type')?.value,
        category_id: document.getElementById('post_yt_category')?.value,
        made_for_kids: document.getElementById('post_yt_made_for_kids')?.value === 'true',
        tags: document.getElementById('post_yt_tags')?.value,
        thumbnail: document.getElementById('post_yt_thumbnail')?.value
      },
      tiktok: {
        privacy: document.getElementById('post_tt_privacy')?.value,
        allow_comments: document.getElementById('post_tt_allow_comments')?.checked,
        allow_duet: document.getElementById('post_tt_allow_duet')?.checked,
        allow_stitch: document.getElementById('post_tt_allow_stitch')?.checked
      },
      facebook: {
        privacy: document.getElementById('post_fb_privacy')?.value,
        location: document.getElementById('post_fb_location')?.value,
        crosspost: document.getElementById('post_fb_crosspost')?.checked
      },
      schedule: {
        enabled: document.getElementById('post_schedule_enabled')?.checked,
        scheduled_at: document.getElementById('post_scheduled_at')?.value
      }
    };

    const out = document.getElementById('post_settings_preview');
    if (out) out.textContent = JSON.stringify(data, null, 2);

    return data;
  }

  function mount(targetId = 'platform_posting_settings') {
    const el = document.getElementById(targetId);
    if (el) el.innerHTML = getHtml();
  }

  return { mount, collect };
})();

window.PlatformPostingSettings = PlatformPostingSettings;
