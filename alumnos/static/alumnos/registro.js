/* Vista previa opcional; el servidor valida siempre el archivo. */
(() => {
  const input = document.getElementById('id_foto');
  const preview = document.querySelector('[data-previa-foto]');
  if (!input || !preview) return;
  let url;
  input.addEventListener('change', () => {
    if (url) URL.revokeObjectURL(url);
    preview.hidden = true;
    preview.removeAttribute('src');
    const file = input.files[0];
    if (!file || !['image/jpeg', 'image/png', 'image/webp'].includes(file.type) || file.size > 5 * 1024 * 1024) return;
    url = URL.createObjectURL(file);
    preview.src = url;
    preview.hidden = false;
  });
})();
