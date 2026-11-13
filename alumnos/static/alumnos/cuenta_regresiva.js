(() => {
  const panel = document.querySelector('[data-cuenta-pedidos]');
  if (!panel) return;
  const titulo = panel.querySelector('[data-cuenta-titulo]');
  const descripcion = panel.querySelector('[data-cuenta-descripcion]');
  const reloj = panel.querySelector('[data-cuenta-reloj]');
  const aviso = panel.querySelector('[data-cuenta-estado]');
  let estado = JSON.parse(document.getElementById('estado-horario').textContent);
  let recibido = Date.now();
  let sincronizando = false;
  let vencido = false;
  let fallo = false;

  function mostrar() {
    if (fallo) return;
    const hastaCambio = Math.max(0, Math.ceil((Date.parse(estado.cambio) - Date.parse(estado.servidor) - (Date.now() - recibido)) / 1000));
    const restante = estado.abierto ? hastaCambio : 0;
    const horas = Math.floor(restante / 3600);
    const minutos = Math.floor(restante % 3600 / 60);
    reloj.textContent = [horas, minutos, restante % 60].map(n => String(n).padStart(2, '0')).join(':');
    if (hastaCambio === 0 && !vencido) {
      vencido = true;
      // Al cerrar se detienen el reloj y la animación, incluso si falla la conexión.
      if (estado.abierto) {
        estado.abierto = false;
        mostrarEstado();
        aviso.textContent = 'El tiempo para pedir terminó.';
      }
      sincronizar();
    }
  }

  function mostrarEstado() {
    panel.classList.toggle('esta-cerrado', !estado.abierto);
    titulo.textContent = estado.abierto ? 'Aún estás a tiempo' : 'El tiempo para pedir terminó';
    descripcion.textContent = estado.abierto ? 'Te queda este tiempo para confirmar tu pedido.' : 'El registro está cerrado. Podrás confirmar tu pedido en el siguiente horario de apertura.';
    reloj.setAttribute('aria-label', estado.abierto ? 'Tiempo para confirmar' : 'Registro cerrado. Sin tiempo disponible para pedir');
  }

  async function sincronizar() {
    if (sincronizando) return;
    sincronizando = true;
    try {
      const respuesta = await fetch(panel.dataset.url, {credentials:'same-origin', cache:'no-store', signal:AbortSignal.timeout(10000)});
      if (!respuesta.ok || respuesta.redirected) throw new Error('Horario no disponible');
      const nuevo = await respuesta.json();
      if (typeof nuevo.abierto !== 'boolean' || !Number.isFinite(Date.parse(nuevo.servidor)) || !Number.isFinite(Date.parse(nuevo.cambio))) throw new Error('Horario inválido');
      const cambio = estado.abierto !== nuevo.abierto;
      estado = nuevo;
      recibido = Date.now();
      vencido = false;
      fallo = false;
      mostrarEstado();
      if (cambio) aviso.textContent = estado.abierto ? 'El registro de pedidos está abierto.' : 'El tiempo para pedir terminó.';
      mostrar();
    } catch {
      fallo = true;
      reloj.textContent = estado.abierto ? '--:--:--' : '00:00:00';
      descripcion.textContent = 'No pudimos actualizar el tiempo. Revisa tu conexión; volveremos a intentarlo.';
    } finally {
      sincronizando = false;
    }
  }
  mostrar();
  sincronizar();
  setInterval(mostrar, 1000);
  setInterval(() => { if (!document.hidden) sincronizar(); }, 60000);
  document.addEventListener('visibilitychange', () => { if (!document.hidden) sincronizar(); });
})();
