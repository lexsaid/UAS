(() => {
  const input = document.querySelector('#id_comprobante');
  const nombre = document.querySelector('[data-archivo-nombre]');
  const previa = document.querySelector('[data-comprobante-previa]');
  let url;
  const form = document.querySelector('#confirmar-compra');
  const enviar = document.querySelector('[form="confirmar-compra"]');
  const avisoHorario = document.querySelector('[data-horario-aviso]');
  let horarioAbierto = avisoHorario.dataset.abierto === 'true';

  function actualizarHorario(abierto, mensaje) {
    horarioAbierto = abierto;
    avisoHorario.dataset.abierto = String(abierto);
    avisoHorario.hidden = abierto;
    enviar.disabled = !abierto;
    if (mensaje) {
      avisoHorario.textContent = mensaje;
      avisoHorario.hidden = false;
    } else if (!abierto) {
      avisoHorario.textContent = 'El horario para finalizar pedidos está cerrado. Tu carrito se conserva; regresa durante el horario de pedidos para confirmar tu compra.';
    }
  }

  async function sincronizarHorario() {
    try {
      const respuesta = await fetch(avisoHorario.dataset.url, {
        credentials: 'same-origin',
        cache: 'no-store',
      });
      if (!respuesta.ok || respuesta.redirected) throw new Error('Horario no disponible');
      const estado = await respuesta.json();
      if (typeof estado.abierto !== 'boolean') throw new Error('Horario inválido');
      actualizarHorario(estado.abierto);
    } catch {
      actualizarHorario(false, 'No pudimos verificar el horario. El botón está bloqueado; revisa tu conexión e inténtalo de nuevo.');
    }
  }

  form.addEventListener('submit', event => {
    if (!horarioAbierto) {
      event.preventDefault();
      return;
    }
    enviar.disabled = true;
    enviar.textContent = 'Guardando…';
  });
  window.addEventListener('pageshow', () => {
    enviar.textContent = 'Confirmar Pedido →';
    enviar.disabled = !horarioAbierto;
  });
  sincronizarHorario();
  setInterval(sincronizarHorario, 30000);
  document.addEventListener('visibilitychange', () => {
    if (!document.hidden) sincronizarHorario();
  });
  input.addEventListener('change', () => {
    if (url) URL.revokeObjectURL(url);
    previa.hidden = true;
    previa.removeAttribute('src');
    input.setCustomValidity('');
    const archivo = input.files[0];
    nombre.textContent = archivo ? archivo.name : 'Aún no has seleccionado un comprobante.';
    if (!archivo) return;
    if (archivo.size > 5 * 1024 * 1024) {
      input.setCustomValidity('El comprobante no puede superar 5 MB.');
      input.reportValidity();
      return;
    }
    if (['image/jpeg', 'image/png', 'image/webp'].includes(archivo.type)) {
      url = URL.createObjectURL(archivo);
      previa.src = url;
      previa.hidden = false;
    }
  });
})();
