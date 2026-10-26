// Tema oscuro / claro (se guarda en el navegador)
(function () {
  const html = document.documentElement;
  const btn = document.getElementById('btn-tema');
  if (!btn) return;
  const icono = () => {
    btn.innerHTML = html.getAttribute('data-bs-theme') === 'dark'
      ? '<i class="bi bi-sun"></i>' : '<i class="bi bi-moon-stars"></i>';
  };
  icono();
  btn.addEventListener('click', () => {
    const nuevo = html.getAttribute('data-bs-theme') === 'dark' ? 'light' : 'dark';
    html.setAttribute('data-bs-theme', nuevo);
    try { localStorage.setItem('tema', nuevo); } catch (e) {}
    icono();
  });
})();

// Confirmación en formularios con data-confirm
document.addEventListener('submit', (e) => {
  const msg = e.target.dataset && e.target.dataset.confirm;
  if (msg && !window.confirm(msg)) e.preventDefault();
});

// Filas dinámicas compartidas (quitar fila)
document.addEventListener('click', (e) => {
  const b = e.target.closest('.quitar-fila');
  if (b) {
    const tbody = b.closest('tbody');
    b.closest('tr').remove();
    tbody.dispatchEvent(new Event('filas-cambiaron', { bubbles: true }));
  }
});
