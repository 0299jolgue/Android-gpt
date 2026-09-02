document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('[data-time]').forEach((el) => {
    const value = Number(el.dataset.time);
    if (!Number.isNaN(value) && value > 0) el.textContent = new Date(value * 1000).toLocaleString('pt-PT');
  });

  const form = document.querySelector('[data-apk-generator]');
  const result = document.querySelector('[data-apk-result]');
  if (!form || !result) return;

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    result.hidden = false;
    result.innerHTML = '<strong>A iniciar…</strong><p>O servidor está a preparar a compilação do APK.</p>';
    const button = form.querySelector('button[type="submit"]');
    if (button) button.disabled = true;

    try {
      const response = await fetch(form.action, { method: 'POST', body: new FormData(form) });
      const data = await response.json();
      if (!response.ok || !data.ok) throw new Error(data.error || 'Não foi possível iniciar a compilação.');

      const poll = async () => {
        const statusResponse = await fetch(data.status_url, { cache: 'no-store' });
        const status = await statusResponse.json();
        if (!statusResponse.ok || !status.ok) throw new Error(status.error || 'Falha ao consultar a compilação.');
        if (status.status === 'ready') {
          result.innerHTML = `<strong>APK pronto ✅</strong><p>${escapeHtml(status.message || '')}</p><a class="button" href="${status.download}">Baixar APK</a>`;
          if (button) button.disabled = false;
          return;
        }
        if (status.status === 'error') {
          result.innerHTML = `<strong>Erro na compilação</strong><p>${escapeHtml(status.message || 'Erro desconhecido.')}</p>`;
          if (button) button.disabled = false;
          return;
        }
        result.innerHTML = `<strong>A compilar…</strong><p>${escapeHtml(status.message || 'A preparar…')}</p>`;
        window.setTimeout(poll, 2500);
      };
      await poll();
    } catch (error) {
      result.innerHTML = `<strong>Erro</strong><p>${escapeHtml(error.message || String(error))}</p>`;
      if (button) button.disabled = false;
    }
  });
});

function escapeHtml(value) {
  return String(value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}
