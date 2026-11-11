(() => {
  const table = document.getElementById('eeGenerationTable');
  if (!table) return;
  const states = new WeakMap();
  let refreshVersion = 0;

  async function refreshTotals() {
    const version = ++refreshVersion;
    const response = await fetch(window.location.href, {credentials: 'same-origin'});
    if (!response.ok) throw new Error('Не удалось обновить итоги');
    const doc = new DOMParser().parseFromString(await response.text(), 'text/html');
    if (version !== refreshVersion) return;
    const updated = doc.querySelectorAll('#eeGenerationTable [data-ee-refresh]');
    table.querySelectorAll('[data-ee-refresh]').forEach((row, index) => {
      // A control row can contain an unsaved value entered by the user.
      if (updated[index] && !row.contains(document.activeElement)) {
        updated[index].classList.toggle('summary-row-hidden', row.classList.contains('summary-row-hidden'));
        row.replaceWith(updated[index]);
      }
    });
  }

  async function save(input, state) {
    if (state.saving || input.value === state.saved) return;
    const raw = input.value;
    const cell = input.closest('td');
    state.saving = true;
    cell.classList.remove('is-save-success', 'is-save-error');
    try {
      const response = await fetch(table.dataset.stationSaveUrl, {
        method: 'PATCH', credentials: 'same-origin',
        headers: {'Content-Type': 'application/json', 'X-CSRFToken': table.dataset.csrf},
        body: JSON.stringify({
          station_id: input.dataset.stationId, period: input.dataset.period, value: raw,
          ee_period_mode: table.dataset.periodMode, selected_year: table.dataset.selectedYear || null,
        }),
      });
      const result = await response.json();
      if (!response.ok || !result.ok) throw new Error(result.error || 'Ошибка сохранения');
      state.saved = raw;
      if (input.value === raw) {
        cell.classList.add('is-save-success');
        input.removeAttribute('aria-invalid');
        input.title = 'Сохранено';
      }
      refreshTotals().catch(error => { input.title = 'Сохранено. ' + error.message; });
    } catch (error) {
      cell.classList.add('is-save-error');
      input.setAttribute('aria-invalid', 'true');
      input.title = error.message;
    } finally {
      state.saving = false;
      if (input.value !== raw) save(input, state);
    }
  }

  function schedule(event) {
    const input = event.target.closest('input.ee-station-value');
    if (!input) return;
    let state = states.get(input);
    if (!state) {
      state = {saved: input.defaultValue, saving: false};
      states.set(input, state);
    }
    clearTimeout(state.timer);
    if (input.value === state.saved && !state.saving) return;
    input.closest('td').classList.remove('is-save-success', 'is-save-error');
    if (event.type === 'change') save(input, state);
    else state.timer = setTimeout(() => save(input, state), 400);
  }
  table.addEventListener('input', schedule);
  table.addEventListener('change', schedule);
})();
