/* Login del comedor: saludo según la hora, mostrar contraseña,
   aviso de mayúsculas y estado del botón al entrar. */
(function () {
  'use strict';

  var form = document.querySelector('.login-form');
  if (!form) { return; }

  // Saludo según la hora
  var saludo = document.querySelector('[data-saludo]');
  if (saludo) {
    var hora = new Date().getHours();
    saludo.textContent = hora < 12 ? 'Buenos días' : (hora < 19 ? 'Buenas tardes' : 'Buenas noches');
  }

  var clave = document.querySelector('#id_password');
  var ver = document.querySelector('[data-ver-clave]');
  var aviso = document.querySelector('[data-aviso-mayusculas]');
  var entrar = document.querySelector('[data-entrar]');

  // Mostrar u ocultar la contraseña
  if (ver && clave) {
    ver.addEventListener('click', function () {
      var visible = clave.type === 'password';
      clave.type = visible ? 'text' : 'password';
      ver.textContent = visible ? 'Ocultar' : 'Mostrar';
      ver.setAttribute('aria-pressed', visible ? 'true' : 'false');
      clave.focus();
    });
  }

  // Aviso de mayúsculas activadas
  if (clave && aviso) {
    var revisar = function (e) {
      aviso.hidden = !(e.getModifierState && e.getModifierState('CapsLock'));
    };
    clave.addEventListener('keydown', revisar);
    clave.addEventListener('keyup', revisar);
    clave.addEventListener('blur', function () { aviso.hidden = true; });
  }

  // Estado del botón mientras se entra (evita enviar dos veces)
  if (entrar) {
    var textoOriginal = entrar.textContent;
    form.addEventListener('submit', function () {
      entrar.textContent = 'Entrando…';
      entrar.setAttribute('aria-busy', 'true');
      setTimeout(function () { entrar.disabled = true; }, 0);
    });
    // Si se vuelve a esta página con el botón "atrás" del navegador
    window.addEventListener('pageshow', function () {
      entrar.textContent = textoOriginal;
      entrar.removeAttribute('aria-busy');
      entrar.disabled = false;
    });
  }
})();
