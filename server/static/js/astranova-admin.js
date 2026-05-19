(function () {
  function show(data) {
    const out = document.getElementById('astranova_output');
    if (!out) return;
    out.textContent = typeof data === 'string' ? data : JSON.stringify(data, null, 2);
  }

  async function api(path, opts = {}) {
    const res = await fetch(path, opts);
    const txt = await res.text();
    try {
      return JSON.parse(txt);
    } catch (e) {
      return { ok: false, status: res.status, raw: txt };
    }
  }

  window.loadAstraNovaCounts = async function () {
    show('Loading counts...');
    const data = await api('/api/astranova/backup/counts');
    show(data);
  };

  window.exportAstraNovaBackup = async function () {
    show('Exporting backup...');
    const data = await api('/api/astranova/backup/export');
    show(data);

    if (data && data.data) {
      const blob = new Blob([JSON.stringify(data.data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'astranova-users-latest.json';
      a.click();
      URL.revokeObjectURL(url);
    }

    alert('Backup exported: ' + (data.count || 0) + ' users');
  };

  window.restoreAstraNovaBackup = async function () {
    if (!confirm('Restore AstraNova users from server backup file?')) return;

    show('Restoring from server backup...');
    const data = await api('/api/astranova/backup/restore-from-file', {
      method: 'POST'
    });

    show(data);
    alert('Restored: ' + (data.restored || 0));
    await window.loadAstraNovaCounts();
  };

  window.restoreAstraNovaBackupFromFile = async function () {
    const input = document.getElementById('astranova_restore_file');

    if (!input || !input.files || !input.files[0]) {
      alert('Оберіть JSON backup файл');
      return;
    }

    if (!confirm('Restore AstraNova users from selected JSON file?')) return;

    const text = await input.files[0].text();
    const payload = JSON.parse(text);

    show('Restoring from local JSON...');
    const data = await api('/api/astranova/backup/restore', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    show(data);
    alert('Restored from local JSON: ' + (data.restored || 0));
    await window.loadAstraNovaCounts();
  };

  console.log('[AstraNova] admin JS loaded');
})();
