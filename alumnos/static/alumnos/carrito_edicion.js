/* Mantiene el carrito y sus totales sincronizados con el servidor, sin navegar. */
(() => {
  const region = document.querySelector('[data-carrito-contenido]');
  const aviso = document.querySelector('[data-edicion-aviso]');
  if (!region) return;
  let ocupado = false;
  let temporizador;
  region.addEventListener('click', event => {
    if (ocupado && event.target.closest('a')) event.preventDefault();
  });
  region.addEventListener('submit', async event => {
    const form = event.target.closest('[data-editar-carrito]');
    if (!form) return;
    event.preventDefault();
    if (ocupado) return;
    ocupado = true;
    clearTimeout(temporizador);
    aviso.hidden = true;
    const action = form.action;
    const posicion = window.scrollY;
    const controles = [...region.querySelectorAll('button')].map(button => [button, button.disabled]);
    controles.forEach(([button]) => { button.disabled = true; });
    region.setAttribute('aria-busy', 'true');
    try {
      const response = await fetch(action, {method:'POST', body:new FormData(form), headers:{Accept:'application/json'}, credentials:'same-origin'});
      if (response.redirected) {
        window.location.assign(response.url);
        return;
      }
      if (!response.ok) throw new Error('No se pudo actualizar');
      const data = await response.json();
      if (typeof data.html !== 'string') throw new Error('Respuesta inválida');
      region.innerHTML = data.html;
      region.querySelectorAll('[data-foto-comida]').forEach(image => {
        image.addEventListener('error', () => { image.hidden = true; });
        if (image.complete && image.naturalWidth === 0) image.hidden = true;
      });
      const nuevoForm = [...region.querySelectorAll('[data-editar-carrito]')].find(f => f.action === action);
      let foco = nuevoForm?.querySelector('button:not(:disabled)');
      if (!foco && nuevoForm) foco = nuevoForm.closest('.seleccion-item').querySelector('button:not(:disabled)');
      (foco || region.querySelector('#seleccion-titulo, .carrito-vacio'))?.focus({preventScroll:true});
      window.scrollTo({top:posicion, behavior:'instant'});
      aviso.textContent = data.mensaje;
      aviso.classList.remove('es-error');
      temporizador = setTimeout(() => { aviso.hidden = true; }, 3000);
    } catch (error) {
      aviso.textContent = 'No pudimos confirmar el cambio. Recarga el carrito para revisar tu selección antes de intentar de nuevo.';
      aviso.classList.add('es-error');
    } finally {
      controles.forEach(([button, disabled]) => { if (button.isConnected) button.disabled = disabled; });
      region.removeAttribute('aria-busy');
      ocupado = false;
      aviso.hidden = false;
    }
  });
})();
