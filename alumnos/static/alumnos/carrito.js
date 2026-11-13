/* Mejora progresiva: los formularios también funcionan sin JavaScript. */
(() => {
  document.querySelectorAll('[data-foto-comida]').forEach(image => {
    const ocultar = () => { image.hidden = true; };
    image.addEventListener('error', ocultar);
    if (image.complete && image.naturalWidth === 0) ocultar();
  });
  const forms = [...document.querySelectorAll('[data-agregar-carrito]')];
  const aviso = document.querySelector('[data-carrito-aviso]');
  let enviando = false;
  let temporizadorAviso;
  forms.forEach(form => form.addEventListener('submit', async event => {
    event.preventDefault();
    if (enviando) return;
    enviando = true;
    clearTimeout(temporizadorAviso);
    const button = form.querySelector('button');
    const original = button.innerHTML;
    forms.forEach(f => { f.querySelector('button').disabled = true; });
    button.textContent = 'Agregando…';
    button.setAttribute('aria-busy', 'true');
    aviso.hidden = true;
    try {
      const response = await fetch(form.action, {method:'POST', body:new FormData(form), headers:{Accept:'application/json'}, credentials:'same-origin'});
      if (response.redirected) { window.location.assign(response.url); return; }
      const data = await response.json();
      if (typeof data.cantidad_carrito !== 'number') throw new Error('Respuesta inválida');
      document.querySelectorAll('[data-carrito-contador]').forEach(el => { el.textContent = data.cantidad_carrito; });
      document.querySelectorAll('[data-carrito-total]').forEach(el => { el.textContent = Number(data.total).toFixed(2); });
      const selected = document.querySelector(`[data-seleccion="${form.dataset.comida}"]`);
      if (selected) selected.textContent = `${data.cantidad} en tu carrito`;
      form.closest('.producto')?.classList.toggle('tiene-seleccion', data.cantidad > 0);
      aviso.textContent = data.mensaje;
      aviso.classList.toggle('es-error', !response.ok);
    } catch (error) {
      aviso.textContent = 'No pudimos confirmar el cambio. Abre el carrito para revisar tu selección antes de intentar de nuevo.';
      aviso.classList.add('es-error');
    } finally {
      enviando = false;
      button.innerHTML = original;
      button.removeAttribute('aria-busy');
      forms.forEach(f => { f.querySelector('button').disabled = false; });
      aviso.hidden = false;
      if (!aviso.classList.contains('es-error')) {
        temporizadorAviso = setTimeout(() => { aviso.hidden = true; }, 3000);
      }
    }
  }));
})();
