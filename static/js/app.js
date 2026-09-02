document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('[data-time]').forEach((el) => {
    const value = Number(el.dataset.time);
    if (!Number.isNaN(value) && value > 0) el.textContent = new Date(value * 1000).toLocaleString('pt-PT');
  });

  const form = document.querySelector('[data-apk-generator]');
  const result = document.querySelector('[data-apk-result]');
  if (!form || !result) return;

  let activeJob = null;

  const notify = async (title, body) => {
    try {
      if (!('Notification' in window)) return;
      if (Notification.permission === 'default') {
        await Notification.requestPermission();
      }
      if (Notification.permission === 'granted') {
        new Notification(title, { body, tag: 'android-gpt-build' });
      }
    } catch (_) { /* Alguns browsers bloqueiam notificações sem gesto do utilizador. */ }
  };

  const saveJob = (job) => localStorage.setItem('android-gpt-apk-job', JSON.stringify(job));
  const loadJob = () => {
    try { return JSON.parse(localStorage.getItem('android-gpt-apk-job') || 'null'); }
    catch (_) { return null; }
  };

  const clearJob = () => localStorage.removeItem('android-gpt-apk-job');

  const showStatus = (status, button) => {
    if (status.status === 'ready') {
      result.hidden = false;
      result.innerHTML = `<strong>APK pronto ✅</strong><p>${escapeHtml(status.message || 'A compilação terminou.')}</p><a class="button" href="${status.download}">Baixar APK</a>`;
      if (button) button.disabled = false;
      if (activeJob && activeJob.notified !== true) {
        notify('Android GPT', 'A tua APK terminou de compilar e está pronta para baixar.');
        activeJob.notified = true;
        saveJob(activeJob);
      }
      return true;
    }
    if (status.status === 'error') {
      result.hidden = false;
      result.innerHTML = `<strong>Erro na compilação</strong><p>${escapeHtml(status.message || 'Erro desconhecido.')}</p>`;
      if (button) button.disabled = false;
      if (activeJob && activeJob.notified !== true) {
        notify('Android GPT', 'A compilação da APK terminou com erro.');
        activeJob.notified = true;
        saveJob(activeJob);
      }
      return true;
    }
    result.hidden = false;
    result.innerHTML = `<strong>${status.status === 'queued' ? 'Na fila…' : 'A compilar…'}</strong><p>${escapeHtml(status.message || 'A preparar…')}</p>`;
    return false;
  };

  const pollJob = async (job, button) => {
    activeJob = job;
    try {
      const statusResponse = await fetch(job.status_url, { cache: 'no-store' });
      const status = await statusResponse.json();
      if (!statusResponse.ok || !status.ok) throw new Error(status.error || 'A compilação já não está disponível.');
      saveJob({ ...job, lastStatus: status.status });
      if (!showStatus(status, button)) window.setTimeout(() => pollJob(job, button), 2000);
    } catch (error) {
      result.hidden = false;
      result.innerHTML = `<strong>Acompanhamento interrompido</strong><p>${escapeHtml(error.message || String(error))}</p><p>Podes voltar a abrir esta página; a compilação continua no servidor.</p>`;
      if (button) button.disabled = false;
    }
  };

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    result.hidden = false;
    result.innerHTML = '<strong>A iniciar…</strong><p>A compilação corre no servidor e continua mesmo que feches esta página.</p>';
    const button = form.querySelector('button[type="submit"]');
    if (button) button.disabled = true;

    try {
      const response = await fetch(form.action, { method: 'POST', body: new FormData(form) });
      const data = await response.json();
      if (!response.ok || !data.ok) throw new Error(data.error || 'Não foi possível iniciar a compilação.');
      activeJob = { job_id: data.job_id, status_url: data.status_url, notified: false };
      saveJob(activeJob);
      if ('Notification' in window && Notification.permission === 'default') {
        try { await Notification.requestPermission(); } catch (_) { /* ignore */ }
      }
      await pollJob(activeJob, button);
    } catch (error) {
      result.innerHTML = `<strong>Erro</strong><p>${escapeHtml(error.message || String(error))}</p>`;
      if (button) button.disabled = false;
    }
  });

  const previousJob = loadJob();
  if (previousJob && previousJob.status_url) {
    result.hidden = false;
    result.innerHTML = '<strong>A recuperar compilação…</strong><p>A verificar uma compilação iniciada anteriormente.</p>';
    const button = form.querySelector('button[type="submit"]');
    if (button) button.disabled = true;
    pollJob(previousJob, button);
  }
});

function escapeHtml(value) {
  return String(value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}
