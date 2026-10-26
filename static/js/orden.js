// Órdenes de compra: filas dinámicas; precarga el producto sugerido por la alerta de stock
(function () {
  const tbody = document.querySelector('#tabla-orden tbody');
  const tpl = document.getElementById('fila-orden-tpl');
  if (!tbody || !tpl) return;

  function agregarFila(productoId) {
    tbody.appendChild(tpl.content.cloneNode(true));
    const fila = tbody.lastElementChild;
    if (productoId) {
      const sel = fila.querySelector('select');
      sel.value = String(productoId);
      const opt = sel.selectedOptions[0];
      if (opt && opt.dataset.sug) fila.querySelector('input[name="cantidad"]').value = opt.dataset.sug;
    }
  }

  document.getElementById('agregar-fila-orden').addEventListener('click', () => agregarFila());
  agregarFila(window.PRODUCTO_SUGERIDO);
})();
