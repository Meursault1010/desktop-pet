(() => {
  const root = document.querySelector('.notification');
  const message = document.querySelector('#message');
  const close = () => window.yukiNotification?.close();
  document.querySelector('.close')?.addEventListener('click', close);
  window.yukiNotification?.onUpdate?.(value => {
    root.dataset.kind = value.kind || 'reminder';
    root.dataset.theme = value.theme || 'mist';
    message.textContent = value.text || 'Yuki 有一条新的提醒。';
    document.title = value.title || 'yuki · 小提醒';
    const track = document.querySelector('.notification-track i');
    if (track) { track.style.animation = 'none'; void track.offsetWidth; track.style.animation = 'expire 7s linear forwards'; }
  });
})();
