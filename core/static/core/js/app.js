(() => {
  'use strict';
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];
  const CSRF = $('meta[name=csrf]')?.content || '';
  const post = (url, data) => fetch(url, {
    method: 'POST', credentials: 'same-origin',
    headers: {'Content-Type': 'application/json', 'X-CSRFToken': CSRF},
    body: JSON.stringify(data || {}),
  }).then(r => r.json());
  const esc = s => s.replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));

  /* ---------- тосты ---------- */
  function toast(text, cls = '', withBtn = false) {
    const el = document.createElement('div');
    el.className = 'toast ' + cls;
    el.innerHTML = `<div>${esc(text)}</div>`;
    if (withBtn) addCta(el);
    $('#toasts').appendChild(el);
    setTimeout(() => el.remove(), withBtn ? 15000 : 6000);
  }
  function addCta(el) {
    if (NOTIF.on()) return;
    const b = document.createElement('button');
    b.className = 'btn btn-mint btn-sm'; b.type = 'button'; b.textContent = 'Включить уведомления';
    b.onclick = () => { NOTIF.toggle(); el.remove(); };
    el.appendChild(b);
  }

  /* ---------- уведомления ---------- */
  const body = document.body, authed = body.dataset.auth === '1';
  const FLAG = 'notif-pref', supported = 'Notification' in window;
  const NOTIF = {
    on: () => supported && Notification.permission === 'granted' && localStorage.getItem(FLAG) !== 'off',
    async toggle() {
      if (!supported) return toast('Этот браузер не поддерживает уведомления.');
      if (NOTIF.on()) { localStorage.setItem(FLAG, 'off'); NOTIF.render(); return toast('Уведомления выключены.'); }
      let perm = Notification.permission;
      if (perm === 'denied') return toast('Браузер блокирует уведомления для этого сайта. Разрешите их в настройках сайта и нажмите снова.', 'error');
      if (perm !== 'granted') perm = await Notification.requestPermission();
      if (perm === 'granted') { localStorage.setItem(FLAG, 'on'); registerSW(); toast('Уведомления включены.', 'success'); }
      NOTIF.render();
    },
    render() {
      const b = $('#notif-toggle'); if (!b) return;
      const on = NOTIF.on();
      b.classList.toggle('is-on', on);
      b.setAttribute('aria-pressed', on);
      b.title = on ? 'Уведомления включены. Нажмите, чтобы выключить' : 'Уведомления выключены. Нажмите, чтобы включить';
    },
  };
  const registerSW = () => 'serviceWorker' in navigator && navigator.serviceWorker.register('/sw.js').catch(() => {});

  async function showPopup(it) {
    const opts = {body: it.text, data: {url: it.url}, tag: 'fh-' + it.id};
    try { (await navigator.serviceWorker.ready).showNotification(it.title, opts); }
    catch (e) { const n = new Notification(it.title, opts); n.onclick = () => { window.focus(); location.href = it.url; }; }
  }
  function setCount(n, hue) {
    const el = $('#bell-count'); if (!el) return;
    el.textContent = n > 99 ? '99+' : n;
    el.closest('.bell').style.setProperty('--h', hue);
  }

  $$('.toast').forEach(t => { if (t.classList.contains('cta')) addCta(t); setTimeout(() => t.remove(), t.classList.contains('cta') ? 15000 : 6000); });
  $('#notif-toggle')?.addEventListener('click', NOTIF.toggle);
  NOTIF.render();

  /* Keep browser password managers from moving focus into profile password fields. */
  const passwordForm = $('[data-password-form]');
  const clearPasswordFocus = () => {
    if (passwordForm?.contains(document.activeElement)) document.activeElement.blur();
  };
  clearPasswordFocus();
  window.addEventListener('pageshow', clearPasswordFocus);
  setTimeout(clearPasswordFocus, 350);

  /* ---------- горизонтальная лента новостей ---------- */
  $$('[data-news-carousel]').forEach(carousel => {
    const viewport = $('[data-news-viewport]', carousel);
    const slides = $$('[data-news-slide]', carousel);
    const prev = $('[data-news-prev]', carousel), next = $('[data-news-next]', carousel);
    const current = $('[data-news-current]', carousel), progress = $('[data-news-progress]', carousel);
    if (!viewport || !slides.length) return;
    let index = 0, frame = 0;
    const go = direction => {
      const style = getComputedStyle(track);
      const gap = parseFloat(style.columnGap) || 0;
      const distance = slides[0].getBoundingClientRect().width + gap;
      viewport.scrollTo({left: viewport.scrollLeft + direction * distance, behavior: 'smooth'});
    };
    const track = $('[data-news-track]', carousel);
    if (!track) return;
    const update = () => {
      const viewLeft = viewport.getBoundingClientRect().left;
      let nearest = 0, distance = Infinity;
      slides.forEach((slide, i) => {
        const d = Math.abs(slide.getBoundingClientRect().left - viewLeft);
        if (d < distance) { distance = d; nearest = i; }
      });
      index = nearest;
      if (current) current.textContent = String(index + 1);
      const maxScroll = Math.max(0, viewport.scrollWidth - viewport.clientWidth);
      if (progress) progress.style.width = `${viewport.scrollWidth ? ((viewport.scrollLeft + viewport.clientWidth) / viewport.scrollWidth) * 100 : 100}%`;
      if (prev) prev.disabled = viewport.scrollLeft <= 2;
      if (next) next.disabled = viewport.scrollLeft >= maxScroll - 2;
    };
    prev?.addEventListener('click', () => go(-1));
    next?.addEventListener('click', () => go(1));
    viewport.addEventListener('scroll', () => {
      if (frame) cancelAnimationFrame(frame);
      frame = requestAnimationFrame(update);
    }, {passive: true});
    viewport.addEventListener('keydown', event => {
      if (event.key === 'ArrowLeft') { event.preventDefault(); go(-1); }
      if (event.key === 'ArrowRight') { event.preventDefault(); go(1); }
      if (event.key === 'Home') { event.preventDefault(); viewport.scrollTo({left: 0, behavior: 'smooth'}); }
      if (event.key === 'End') { event.preventDefault(); viewport.scrollTo({left: viewport.scrollWidth, behavior: 'smooth'}); }
    });
    window.addEventListener('resize', update, {passive: true});
    update();
  });

  if (authed) {
    registerSW();
    const key = 'notif-last-' + body.dataset.uid;
    let last = Number(localStorage.getItem(key) ?? body.dataset.maxId);
    const poll = async () => {
      try {
        const r = await fetch(`${body.dataset.poll}?after=${last}`, {credentials: 'same-origin'});
        if (!r.ok) return;
        const d = await r.json();
        setCount(d.count, d.hue);
        if (NOTIF.on()) for (const it of d.items) await showPopup(it);
        last = Math.max(last, d.max_id); localStorage.setItem(key, last);
      } catch (e) { /* нет сети — попробуем в следующий раз */ }
    };
    setInterval(poll, 15000); poll();
  }

  /* ---------- круговая обрезка аватара ---------- */
  $$('input[data-avatar-crop]').forEach(input => {
    const dialog = $('[data-avatar-crop-dialog]'), canvas = $('[data-avatar-canvas]', dialog);
    const ctx = canvas.getContext('2d'), zoomControl = $('[data-avatar-zoom]', dialog);
    const preview = $(input.dataset.preview), size = 280;
    let photo = null, offsetX = 0, offsetY = 0, zoom = 1, pointer = null, objectUrl = null;
    const dimensions = () => { const scale = Math.max(size / photo.width, size / photo.height) * zoom; return {w: photo.width * scale, h: photo.height * scale}; };
    const clamp = () => { const d = dimensions(); offsetX = Math.min(0, Math.max(size - d.w, offsetX)); offsetY = Math.min(0, Math.max(size - d.h, offsetY)); };
    const paint = () => {
      if (!photo) return;
      clamp(); ctx.clearRect(0, 0, size, size); ctx.save(); ctx.beginPath(); ctx.arc(size/2,size/2,size/2,0,Math.PI*2); ctx.clip();
      const d = dimensions(); ctx.drawImage(photo, (size-d.w)/2+offsetX, (size-d.h)/2+offsetY, d.w, d.h); ctx.restore();
    };
    const close = () => { dialog.hidden = true; photo = null; if (objectUrl) URL.revokeObjectURL(objectUrl); objectUrl = null; };
    input.addEventListener('change', () => {
      const file = input.files?.[0]; if (!file) return;
      const max = Number(input.dataset.maxMb || 2) * 1048576;
      if (file.size > max) { toast(`Файл больше ${input.dataset.maxMb} МБ — выберите поменьше.`, 'error'); input.value = ''; return; }
      input.value = '';
      objectUrl = URL.createObjectURL(file); photo = new Image();
      photo.onload = () => { offsetX = 0; offsetY = 0; zoom = 1; zoomControl.value = '1'; paint(); dialog.hidden = false; $('[data-avatar-apply]', dialog).focus(); };
      photo.onerror = () => { toast('Не удалось открыть это изображение.', 'error'); close(); };
      photo.src = objectUrl;
    });
    zoomControl.addEventListener('input', () => { zoom = Number(zoomControl.value); paint(); });
    canvas.addEventListener('pointerdown', e => { pointer = {x:e.clientX,y:e.clientY}; canvas.setPointerCapture(e.pointerId); });
    canvas.addEventListener('pointermove', e => { if (!pointer) return; offsetX += e.clientX-pointer.x; offsetY += e.clientY-pointer.y; pointer={x:e.clientX,y:e.clientY}; paint(); });
    canvas.addEventListener('pointerup', () => { pointer = null; });
    canvas.addEventListener('pointercancel', () => { pointer = null; });
    $('[data-avatar-cancel]', dialog).addEventListener('click', close);
    $('[data-avatar-apply]', dialog).addEventListener('click', () => {
      const output = document.createElement('canvas'); output.width = output.height = 512;
      const out = output.getContext('2d'), d = dimensions(), ratio = 512/size;
      out.drawImage(photo, ((size-d.w)/2+offsetX)*ratio, ((size-d.h)/2+offsetY)*ratio, d.w*ratio, d.h*ratio);
      output.toBlob(blob => {
        if (!blob) { toast('Не удалось подготовить фотографию.', 'error'); return; }
        const cropped = new File([blob], 'avatar-crop.jpg', {type:'image/jpeg'}), transfer = new DataTransfer();
        transfer.items.add(cropped); input.files = transfer.files;
        if (preview) preview.src = URL.createObjectURL(blob);
        close();
      }, 'image/jpeg', .9);
    });
  });

  /* ---------- загрузка файлов: проверка размера и превью ---------- */
  $$('input[type=file][data-max-mb]').forEach(i => i.addEventListener('change', () => {
    const f = i.files[0]; if (!f) return;
    if (f.size > i.dataset.maxMb * 1048576) { toast(`Файл больше ${i.dataset.maxMb} МБ — выберите поменьше.`, 'error'); i.value = ''; return; }
    const pv = $(i.dataset.preview || '#none'); if (pv) pv.src = URL.createObjectURL(f);
  }));

  /* ---------- задачи ---------- */
  document.addEventListener('change', async e => {
    const cb = e.target.closest('input[data-sub-url]'); if (!cb) return;
    const want = cb.checked; cb.disabled = true;
    try {
      const d = await post(cb.dataset.subUrl);
      if (d.error) throw new Error(d.error);
      cb.checked = d.done; cb.closest('.sub').classList.toggle('done', d.done);
      const card = cb.closest('.task'); card.classList.toggle('done', d.task_done);
      $('.bar i', card).style.width = d.percent + '%';
      $('.count', card).textContent = `${d.sub_done} из ${d.sub_total}`;
    } catch (err) { cb.checked = !want; toast(err.message || 'Не удалось сохранить.', 'error'); }
    cb.disabled = false;
  });
  document.addEventListener('click', async e => {
    const b = e.target.closest('[data-done-url]'); if (!b) return;
    const d = await post(b.dataset.doneUrl);
    d.error ? toast(d.error, 'error') : location.reload();
  });

  /* ---------- чат ---------- */
  /* ---------- просмотр фотографий новости ---------- */
  $$('[data-photo-reader]').forEach(reader => {
    const photos = $$('[data-photo-reader] .news-reader-photo');
    const current = $('[data-photo-current]', reader);
    let index = 0;
    const show = next => {
      if (!photos.length) return;
      index = (next + photos.length) % photos.length;
      photos.forEach((photo, i) => { photo.hidden = i !== index; photo.classList.toggle('is-active', i === index); });
      if (current) current.textContent = String(index + 1);
    };
    $('[data-photo-prev]', reader)?.addEventListener('click', () => show(index - 1));
    $('[data-photo-next]', reader)?.addEventListener('click', () => show(index + 1));
    reader.addEventListener('keydown', e => { if (e.key === 'ArrowLeft') show(index - 1); if (e.key === 'ArrowRight') show(index + 1); });
  });

  /* ---------- загрузка и сортировка фотографий новости ---------- */
  $$('[data-photo-editor]').forEach(editor => {
    const input = $('[data-news-files]', editor), list = $('[data-photo-previews]', editor), order = $('[data-photo-order]', editor);
    if (!input || !list || !order) return;
    const files = new Map(); let serial = 0, dragged = null;
    const addFiles = incoming => [...incoming].filter(file => file.type.startsWith('image/')).forEach(file => {
      const token = `f${serial++}`; files.set(token, file);
      const tile = document.createElement('div'); tile.className = 'news-photo-thumb'; tile.draggable = true; tile.dataset.fileToken = token;
      const img = document.createElement('img'); img.src = URL.createObjectURL(file); img.alt = file.name;
      const remove = document.createElement('button'); remove.type = 'button'; remove.dataset.removePhoto = ''; remove.setAttribute('aria-label', 'Удалить фото'); remove.textContent = '×';
      const caption = document.createElement('small'); caption.textContent = file.name;
      tile.append(img, remove, caption); list.append(tile);
    });
    input.addEventListener('change', () => addFiles(input.files));
    const zone = $('.news-dropzone', editor);
    zone?.addEventListener('dragover', e => { e.preventDefault(); zone.classList.add('is-dragging'); });
    zone?.addEventListener('dragleave', () => zone.classList.remove('is-dragging'));
    zone?.addEventListener('drop', e => { e.preventDefault(); zone.classList.remove('is-dragging'); addFiles(e.dataTransfer.files); });
    list.addEventListener('click', e => {
      const button = e.target.closest('[data-remove-photo]'); if (!button) return;
      const tile = button.closest('.news-photo-thumb');
      if (tile.dataset.fileToken) files.delete(tile.dataset.fileToken);
      tile.remove();
    });
    list.addEventListener('dragstart', e => { dragged = e.target.closest('.news-photo-thumb'); if (dragged) { e.dataTransfer.effectAllowed = 'move'; dragged.classList.add('is-dragging'); } });
    list.addEventListener('dragend', () => { list.querySelectorAll('.is-dragging').forEach(el => el.classList.remove('is-dragging')); dragged = null; });
    list.addEventListener('dragover', e => {
      e.preventDefault(); const target = e.target.closest('.news-photo-thumb');
      if (dragged && target && target !== dragged) { const r = target.getBoundingClientRect(); list.insertBefore(dragged, e.clientY < r.top + r.height / 2 ? target : target.nextSibling); }
    });
    editor.closest('form').addEventListener('submit', () => {
      const transfer = new DataTransfer(), tokens = []; let newIndex = 0;
      list.querySelectorAll('.news-photo-thumb').forEach(tile => {
        if (tile.dataset.photoId) tokens.push(`id:${tile.dataset.photoId}`);
        else if (files.has(tile.dataset.fileToken)) { tokens.push(`new:${newIndex++}`); transfer.items.add(files.get(tile.dataset.fileToken)); }
      });
      input.files = transfer.files; order.value = JSON.stringify(tokens);
    });
  });

  const root = $('#chat'); if (!root) return;
  const cfg = JSON.parse($('#chat-cfg').textContent);
  const box = $('#chat-scroll'), input = $('#msg'), list = $('#mention-list');
  const colors = ['#d9480f', '#0b7285', '#862e9c', '#2b8a3e', '#c2255c', '#1864ab', '#e67700'];
  const mentionRe = /(^|[^\p{L}\p{N}_])(@все\s+в\s+отделе|@все\s+в\s+чате|@[\p{L}\p{N}_-]+)/giu;
  let lastId = 0, lastDay = '', lastUid = null, muted = cfg.muted, initial = true;

  const fmt = t => esc(t).replace(mentionRe, (m, pre, mention) => {
    const normalized = mention.slice(1).toLowerCase().replace(/\s+/g, ' ');
    const mine = cfg.me.includes(normalized) || normalized === 'все в отделе' || normalized === 'все в чате';
    return `${pre}<span class="mention${mine ? ' me' : ''}">${mention}</span>`;
  }).replace(/\n/g, '<br>');

  function render(msgs) {
    const near = box.scrollHeight - box.scrollTop - box.clientHeight < 140;
    let mineSent = false;
    if (msgs.length) $('.chat-empty', box)?.remove();
    for (const m of msgs) {
      if (m.day !== lastDay) { box.insertAdjacentHTML('beforeend', `<div class="day">${m.day}</div>`); lastDay = m.day; lastUid = null; }
      const mine = m.uid === cfg.myId, first = m.uid !== lastUid;
      box.insertAdjacentHTML('beforeend', `
        <div class="msg${mine ? ' mine' : ''}${first ? ' first' : ''}" data-id="${m.id}">
          ${mine ? '' : `<img class="msg-ava${first ? '' : ' ghost'}" src="${esc(m.avatar)}" alt="">`}
          <div class="bubble">
            ${first && !mine ? `<div class="msg-name" style="color:${colors[m.uid % colors.length]}">${esc(m.author)}</div>` : ''}
            <span class="msg-text">${fmt(m.text)}</span><span class="msg-time">${m.time}</span>
            ${m.can_delete ? `<button class="msg-delete" type="button" data-delete-message="${m.id}" aria-label="Удалить сообщение" title="Удалить сообщение">×</button>` : ''}
          </div>
        </div>`);
      lastUid = m.uid; lastId = Math.max(lastId, m.id); mineSent ||= mine;
    }
    if (msgs.length) { if (initial || near || mineSent) box.scrollTop = box.scrollHeight; initial = false; }
  }

  async function load() {
    if (document.hidden) return;
    try {
      const r = await fetch(`${root.dataset.messages}?after=${lastId}`, {credentials: 'same-origin'});
      if (r.ok) render((await r.json()).messages);
    } catch (e) {}
  }
  box.innerHTML = '<div class="chat-empty">Пока тишина. Напишите первое сообщение.</div>';
  load(); setInterval(load, 3000);
  document.addEventListener('visibilitychange', load);

  box.addEventListener('click', async e => {
    const button = e.target.closest('[data-delete-message]');
    if (!button || !confirm('Удалить это сообщение?')) return;
    button.disabled = true;
    const row = button.closest('.msg');
    try {
      const response = await fetch(`${root.dataset.delete}${button.dataset.deleteMessage}/delete/`, {
        method: 'POST', credentials: 'same-origin', headers: {'X-CSRFToken': CSRF}
      });
      const result = await response.json();
      if (!response.ok || result.error) throw new Error(result.error || 'Не удалось удалить сообщение.');
      row?.remove();
    } catch (error) { button.disabled = false; toast(error.message || 'Ошибка удаления.', 'error'); }
  });

  async function send() {
    const text = input.value.trim(); if (!text) return;
    input.value = ''; autosize(); closeList();
    const d = await post(root.dataset.send, {text});
    if (d.error) toast(d.error, 'error');
    await load(); box.scrollTop = box.scrollHeight;
  }
  const autosize = () => { input.style.height = 'auto'; input.style.height = Math.min(input.scrollHeight, 140) + 'px'; };
  $('#composer').addEventListener('submit', e => { e.preventDefault(); send(); });

  /* подсказки @ */
  let items = [], sel = 0;
  const tokenAt = () => /(^|\s)@([\p{L}\p{N}_-]*)$/u.exec(input.value.slice(0, input.selectionStart));
  const closeList = () => { list.style.display = 'none'; items = []; };
  function openList() {
    const t = tokenAt(); if (!t) return closeList();
    const q = t[2].toLowerCase();
    items = [
      {handle: 'все в отделе', name: 'Упомянуть всех участников отдела', avatar: ''},
      {handle: 'все в чате', name: 'Упомянуть участников этого чата', avatar: ''},
      ...cfg.members,
    ]
      .filter(m => m.handle.toLowerCase().startsWith(q) || m.name.toLowerCase().startsWith(q)).slice(0, 8);
    if (!items.length) return closeList();
    sel = Math.min(sel, items.length - 1);
    list.innerHTML = items.map((m, i) => `<button type="button" data-i="${i}" class="${i === sel ? 'sel' : ''}">
      ${m.avatar ? `<img src="${esc(m.avatar)}" alt="">` : '<img alt="" src="data:image/svg+xml,%3Csvg xmlns=%27http://www.w3.org/2000/svg%27/%3E">'}
      <span>${esc(m.name)}${m.name.toLowerCase() !== m.handle.toLowerCase() ? `<small>@${esc(m.handle)}</small>` : ''}</span></button>`).join('');
    list.style.display = 'block';
  }
  function pick(i) {
    const m = items[i]; if (!m) return;
    const pos = input.selectionStart, before = input.value.slice(0, pos).replace(/@([\p{L}\p{N}_-]*)$/u, `@${m.handle} `);
    input.value = before + input.value.slice(pos); input.selectionStart = input.selectionEnd = before.length;
    closeList(); input.focus(); autosize();
  }
  list.addEventListener('mousedown', e => { const b = e.target.closest('button'); if (b) { e.preventDefault(); pick(+b.dataset.i); } });
  input.addEventListener('input', () => { sel = 0; autosize(); openList(); });
  input.addEventListener('keydown', e => {
    if (list.style.display === 'block' && items.length) {
      if (e.key === 'ArrowDown' || e.key === 'ArrowUp') { e.preventDefault(); sel = (sel + (e.key === 'ArrowDown' ? 1 : items.length - 1)) % items.length; return openList(); }
      if (e.key === 'Enter' || e.key === 'Tab') { e.preventDefault(); return pick(sel); }
      if (e.key === 'Escape') return closeList();
    }
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); }
  });
  input.addEventListener('blur', () => setTimeout(closeList, 120));

  /* мут */
  const muteBtn = $('#mute-btn'), pop = $('#mute-pop');
  const paintMute = label => { muted = !!label; muteBtn.textContent = label || 'Заглушить чат'; muteBtn.classList.toggle('btn-ghost', !label); };
  paintMute(cfg.label);
  muteBtn.addEventListener('click', e => { e.stopPropagation(); pop.classList.toggle('open'); });
  document.addEventListener('click', () => pop.classList.remove('open'));
  pop.addEventListener('click', async e => {
    const b = e.target.closest('button'); if (!b) return;
    const d = await post(root.dataset.mute, {minutes: +b.dataset.minutes});
    paintMute(d.label); toast(d.muted ? d.label + '. Личные отметки всё равно придут.' : 'Звук чата включён.', 'success');
  });
})();
