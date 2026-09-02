document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('[data-time]').forEach((el) => {
    const value = Number(el.dataset.time);
    if (!Number.isNaN(value) && value > 0) el.textContent = new Date(value * 1000).toLocaleString('pt-PT');
  });
});
