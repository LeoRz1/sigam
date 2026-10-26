// Punto de venta: filas dinámicas y totales con IVA
(function () {
  const form = document.getElementById('form-venta');
  if (!form) return;
  const iva = parseFloat(form.dataset.iva || '0.19');
  const tbody = document.querySelector('#tabla-items tbody');
  const tpl = document.getElementById('fila-tpl');
  const fmt = (n) => '$' + Math.round(n).toLocaleString('es-CO');

  function recalcular() {
    let subtotal = 0;
    tbody.querySelectorAll('tr').forEach((tr) => {
      const sel = tr.querySelector('.item-producto');
      const opt = sel.selectedOptions[0];
      const precio = opt && opt.dataset.precio ? parseFloat(opt.dataset.precio) : 0;
      const stock = opt && opt.dataset.stock ? parseInt(opt.dataset.stock, 10) : null;
      const cantInput = tr.querySelector('.item-cant');
      if (stock !== null) cantInput.max = stock;
      const cant = parseInt(cantInput.value || '0', 10);
      const sub = precio * cant;
      tr.querySelector('.item-precio').textContent = fmt(precio);
      tr.querySelector('.item-subtotal').textContent = fmt(sub);
      subtotal += sub;
    });
    document.getElementById('t-subtotal').textContent = fmt(subtotal);
    document.getElementById('t-iva').textContent = fmt(subtotal * iva);
    document.getElementById('t-total').textContent = fmt(subtotal * (1 + iva));
  }

  function agregarFila() {
    tbody.appendChild(tpl.content.cloneNode(true));
    recalcular();
  }

  document.getElementById('agregar-fila').addEventListener('click', agregarFila);
  tbody.addEventListener('input', recalcular);
  tbody.addEventListener('change', recalcular);
  tbody.addEventListener('filas-cambiaron', recalcular);
  agregarFila();
})();
