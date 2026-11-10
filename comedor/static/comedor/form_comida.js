/* Formulario de agregar/editar comida.
   - Ingredientes uno por uno (etiquetas que se pueden quitar)
   - Vista previa en vivo
   - Foto con vista previa y arrastrar y soltar
   Sin JavaScript el formulario sigue funcionando con el cuadro de texto normal. */
(function () {
  'use strict';

  var form = document.querySelector('[data-form-comida]');
  if (!form) { return; }

  var MAX_INGREDIENTES = 30;
  var MAX_LARGO = 60;
  var MAX_EN_VISTA_PREVIA = 5;

  function q(selector) { return document.querySelector(selector); }

  var nombre = q('#id_nombre');
  var textoIngredientes = q('#id_ingredientes');
  var entrada = q('#ingrediente-nuevo');
  var botonAgregar = q('[data-agregar]');
  var listaChips = q('[data-chips]');
  var aviso = q('[data-aviso-ingrediente]');
  var precio = q('#id_precio');
  var fotoInput = q('#id_imagen');
  var dropzone = q('[data-dropzone]');
  var fotoImg = q('[data-foto-img]');
  var fotoVacio = q('[data-foto-vacio]');

  var prev = {
    nombre: q('[data-prev-nombre]'),
    chips: q('[data-prev-chips]'),
    precio: q('[data-prev-precio]'),
    foto: q('[data-prev-foto]'),
    fotoVacio: q('[data-prev-foto-vacio]')
  };

  var AVISO_INICIAL = aviso.textContent.trim();

  /* ---------- Ingredientes ---------- */

  var ingredientes = [];
  var recienAgregados = 0;

  function separar(texto) {
    return texto.split(/[\n,]+/)
      .map(function (s) { return s.replace(/\s+/g, ' ').trim(); })
      .filter(Boolean);
  }

  function avisar(mensaje) {
    aviso.textContent = mensaje || AVISO_INICIAL;
    aviso.classList.toggle('aviso-alerta', Boolean(mensaje));
  }

  function crearChip(texto, indice, esNuevo) {
    var li = document.createElement('li');
    li.className = 'chip chip-editable' + (esNuevo ? ' nuevo' : '');

    var span = document.createElement('span');
    span.textContent = texto;

    var quitar = document.createElement('button');
    quitar.type = 'button';
    quitar.setAttribute('data-quitar', String(indice));
    quitar.setAttribute('aria-label', 'Quitar ' + texto);
    quitar.innerHTML = '<svg class="icono" aria-hidden="true"><use href="#i-x"></use></svg>';

    li.appendChild(span);
    li.appendChild(quitar);
    return li;
  }

  function dibujarVistaPrevia() {
    prev.chips.textContent = '';
    if (!ingredientes.length) {
      var vacio = document.createElement('li');
      vacio.className = 'chip chip-mas';
      vacio.textContent = 'Sin ingredientes aún';
      prev.chips.appendChild(vacio);
      return;
    }
    ingredientes.slice(0, MAX_EN_VISTA_PREVIA).forEach(function (texto) {
      var li = document.createElement('li');
      li.className = 'chip';
      li.textContent = texto;
      prev.chips.appendChild(li);
    });
    if (ingredientes.length > MAX_EN_VISTA_PREVIA) {
      var mas = document.createElement('li');
      mas.className = 'chip chip-mas';
      mas.textContent = '+' + (ingredientes.length - MAX_EN_VISTA_PREVIA) + ' más';
      prev.chips.appendChild(mas);
    }
  }

  function dibujarIngredientes() {
    var primeroNuevo = ingredientes.length - recienAgregados;
    listaChips.textContent = '';
    ingredientes.forEach(function (texto, i) {
      listaChips.appendChild(crearChip(texto, i, i >= primeroNuevo && recienAgregados > 0));
    });
    recienAgregados = 0;
    textoIngredientes.value = ingredientes.join('\n');
    dibujarVistaPrevia();
  }

  function agregar(texto) {
    var agregados = 0;
    var repetido = false;
    var mensaje = '';

    separar(texto).forEach(function (ingrediente) {
      if (ingrediente.length > MAX_LARGO) {
        mensaje = 'Cada ingrediente puede tener máximo ' + MAX_LARGO + ' caracteres.';
        return;
      }
      if (ingredientes.length >= MAX_INGREDIENTES) {
        mensaje = 'Máximo ' + MAX_INGREDIENTES + ' ingredientes.';
        return;
      }
      var existe = ingredientes.some(function (x) {
        return x.toLowerCase() === ingrediente.toLowerCase();
      });
      if (existe) { repetido = true; return; }
      ingredientes.push(ingrediente);
      agregados += 1;
    });

    if (!mensaje && repetido && !agregados) { mensaje = 'Ese ingrediente ya está en la lista.'; }
    avisar(mensaje);
    recienAgregados = agregados;
    dibujarIngredientes();
  }

  function confirmarEscrito() {
    var texto = entrada.value;
    entrada.value = '';
    if (texto.trim()) { agregar(texto); }
  }

  entrada.addEventListener('keydown', function (e) {
    if (e.key === 'Enter') {
      e.preventDefault();
      confirmarEscrito();
    } else if (e.key === 'Backspace' && entrada.value === '' && ingredientes.length) {
      ingredientes.pop();
      avisar('');
      dibujarIngredientes();
    }
  });

  // Al escribir una coma, lo escrito se vuelve ingrediente. Si se pega una lista
  // ("Salsa, crema, queso"), se agregan todos uno por uno.
  entrada.addEventListener('input', function () {
    if (entrada.value.indexOf(',') === -1) { return; }
    confirmarEscrito();
  });

  botonAgregar.addEventListener('click', function () {
    confirmarEscrito();
    entrada.focus();
  });

  listaChips.addEventListener('click', function (e) {
    var boton = e.target.closest('[data-quitar]');
    if (!boton) { return; }
    ingredientes.splice(Number(boton.getAttribute('data-quitar')), 1);
    avisar('');
    dibujarIngredientes();
    entrada.focus();
  });

  // Si quedó algo escrito sin agregar, se agrega al guardar.
  form.addEventListener('submit', confirmarEscrito);

  ingredientes = separar(textoIngredientes.value);
  dibujarIngredientes();

  /* ---------- Nombre y precio ---------- */

  function actualizarNombre() {
    var texto = nombre.value.trim();
    prev.nombre.textContent = texto || 'Nombre de la comida';
    prev.nombre.classList.toggle('es-placeholder', !texto);
  }

  function actualizarPrecio() {
    var valor = parseFloat(precio.value);
    prev.precio.textContent = '$' + (isFinite(valor) && valor > 0 ? valor.toFixed(2) : '0.00');
  }

  nombre.addEventListener('input', actualizarNombre);
  precio.addEventListener('input', actualizarPrecio);
  actualizarNombre();
  actualizarPrecio();

  /* ---------- Foto ---------- */

  var urlTemporal = null;

  function mostrarFoto(url) {
    fotoImg.src = url;
    fotoImg.hidden = false;
    fotoVacio.hidden = true;
    dropzone.classList.add('tiene-foto');
    prev.foto.src = url;
    prev.foto.hidden = false;
    prev.fotoVacio.setAttribute('hidden', '');
  }

  function usarArchivo() {
    var archivo = fotoInput.files && fotoInput.files[0];
    if (!archivo || archivo.type.indexOf('image/') !== 0) { return; }
    if (urlTemporal) { URL.revokeObjectURL(urlTemporal); }
    urlTemporal = URL.createObjectURL(archivo);
    mostrarFoto(urlTemporal);
  }

  fotoInput.addEventListener('change', usarArchivo);

  ['dragenter', 'dragover'].forEach(function (evento) {
    dropzone.addEventListener(evento, function (e) {
      e.preventDefault();
      dropzone.classList.add('arrastrando');
    });
  });
  ['dragleave', 'dragend'].forEach(function (evento) {
    dropzone.addEventListener(evento, function () { dropzone.classList.remove('arrastrando'); });
  });
  dropzone.addEventListener('drop', function (e) {
    e.preventDefault();
    dropzone.classList.remove('arrastrando');
    var archivos = e.dataTransfer && e.dataTransfer.files;
    if (archivos && archivos.length) {
      fotoInput.files = archivos;
      usarArchivo();
    }
  });

  // En edición ya hay foto guardada: se muestra también en la vista previa.
  if (fotoImg.getAttribute('src')) { mostrarFoto(fotoImg.getAttribute('src')); }
})();
