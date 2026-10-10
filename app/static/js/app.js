/* ── Toast notification system ─────────────────────────────────────────── */
function showToast(msg, type) {
  var container = document.getElementById('toastContainer');
  if (!container) return;
  var toast = document.createElement('div');
  toast.className = 'toast' + (type === 'warn' ? ' toast-warn' : type === 'ok' ? ' toast-ok' : '');
  toast.textContent = msg;
  container.appendChild(toast);
  setTimeout(function() {
    toast.style.opacity = '0';
    toast.style.transition = 'opacity .3s';
    setTimeout(function() { container.removeChild(toast); }, 350);
  }, 2200);
}

/* ── Sidebar mobile toggle ──────────────────────────────────────────────── */
(function() {
  var toggle = document.getElementById('sidebarToggle');
  var topbarToggle = document.getElementById('topbarToggle');
  var nav = document.querySelector('.sidebar-nav');
  function toggleNav() {
    if (nav) nav.classList.toggle('open');
  }
  if (toggle) toggle.addEventListener('click', toggleNav);
  if (topbarToggle) topbarToggle.addEventListener('click', toggleNav);
})();

/* ── Character counter (main generate form) ─────────────────────────────── */
(function () {
  var ta = document.getElementById('source_content');
  var counter = document.getElementById('charCounter');
  if (ta && counter) {
    function update() {
      var len = ta.value.length;
      counter.textContent = len + ' / 5000';
      counter.classList.toggle('over', len > 5000);
    }
    ta.addEventListener('input', update);
    update();
  }

  /* ── Generate form loading state ─────────────────────────────────────── */
  var form = document.getElementById('generateForm');
  var btn = document.getElementById('generateBtn');
  if (form && btn) {
    form.addEventListener('submit', function (e) {
      var val = ta ? ta.value.trim() : '';
      if (!val) { e.preventDefault(); return; }
      var btnText = btn.querySelector('.btn-text');
      var btnLoad = btn.querySelector('.btn-loading');
      if (btnText && btnLoad) {
        btnText.classList.add('hidden');
        btnLoad.classList.remove('hidden');
      }
      btn.disabled = true;
    });
  }

  /* ── Copy to clipboard ────────────────────────────────────────────────── */
  var notification = document.getElementById('copyNotification');

  function showNotification(msg) {
    if (!notification) return;
    notification.textContent = msg || 'Copied to clipboard!';
    notification.classList.remove('hidden');
    clearTimeout(notification._timer);
    notification._timer = setTimeout(function() { notification.classList.add('hidden'); }, 2000);
  }

  function copyText(text, copyBtn) {
    navigator.clipboard.writeText(text).then(function() {
      showToast('Copied to clipboard!', 'ok');
      showNotification('Copied to clipboard!');
      if (copyBtn) {
        var orig = copyBtn.textContent;
        copyBtn.textContent = '✓ Copied';
        copyBtn.classList.add('copied');
        setTimeout(function() { copyBtn.textContent = orig; copyBtn.classList.remove('copied'); }, 2000);
      }
    }).catch(function() {
      var el = document.createElement('textarea');
      el.value = text;
      el.style.position = 'fixed';
      el.style.opacity = '0';
      document.body.appendChild(el);
      el.select();
      document.execCommand('copy');
      document.body.removeChild(el);
      showToast('Copied!', 'ok');
      showNotification('Copied!');
    });
  }

  document.addEventListener('click', function (e) {
    /* Single copy button */
    if (e.target.classList.contains('btn-copy') && e.target.dataset.target) {
      var el = document.getElementById(e.target.dataset.target);
      if (el) copyText(el.textContent.trim(), e.target);
    }

    /* Copy-all for X thread */
    if (e.target.classList.contains('btn-copy-all') && e.target.dataset.thread) {
      var posts = document.querySelectorAll('.thread-text');
      var all = Array.from(posts).map(function(p, i) { return (i + 1) + '/ ' + p.textContent.trim(); }).join('\n\n');
      copyText(all, e.target);
    }
  });

  /* ── Markdown download ────────────────────────────────────────────────── */
  var dlBtn = document.getElementById('downloadBtn');
  if (dlBtn && typeof EXPORT_DATA !== 'undefined') {
    dlBtn.addEventListener('click', function() {
      var d = EXPORT_DATA;
      var tags = d.tags.map(function(t) { return '#' + t.replace(/\s+/g, ''); }).join(' ');
      var thread = d.x_thread.map(function(p, i) { return '### Post ' + (i+1) + '\n' + p; }).join('\n\n');
      var md = '# ' + d.title + '\n\n**Hashtags:** ' + tags + '\n\n---\n\n## LinkedIn\n\n' + d.linkedin +
        '\n\n---\n\n## X / Twitter Thread\n\n' + thread +
        '\n\n---\n\n## Instagram\n\n' + d.instagram +
        '\n\n---\n\n## Newsletter\n\n' + d.newsletter + '\n';
      var blob = new Blob([md], { type: 'text/markdown' });
      var url = URL.createObjectURL(blob);
      var a = document.createElement('a');
      a.href = url;
      a.download = 'repurposekit-export.md';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    });
  }
})();
