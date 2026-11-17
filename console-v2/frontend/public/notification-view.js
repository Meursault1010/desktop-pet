(() => {
  const root = document.querySelector('.notification');
  const message = document.querySelector('#message');
  const close = () => window.yukiNotification?.close();
  document.querySelector('.close')?.addEventListener('click', close);
  window.yukiNotification?.onUpdate?.(value => {
    root.dataset.kind = value.kind || 'reminder';
    const theme = ['light','mist','dark'].includes(value.theme) ? value.theme : 'mist';
    root.dataset.theme = theme;
    document.documentElement.dataset.theme = theme;
    message.textContent = value.text || '有一条新提醒。';
    document.title = value.title || 'Yuki · 提醒';
    document.querySelector('h1').textContent = value.title || '桌面提醒';
    const track = document.querySelector('.notification-track i');
    if (track) { track.style.animation = 'none'; void track.offsetWidth; track.style.animation = ''; }
  });
})();
