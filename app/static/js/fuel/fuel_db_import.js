(() => {
    'use strict';
    const widget = document.getElementById('fuelDbImportWidget');
    if (!widget) return;
    const form = widget.querySelector('#importFuelDbForm');
    const button = widget.querySelector('#importFuelDbBtn');
    const input = widget.querySelector('#importFuelDbFile');
    const status = widget.querySelector('#fuelDbImportStatus');
    const detail = widget.querySelector('[data-import-detail]');
    const file = widget.querySelector('[data-import-file]');
    const progress = widget.querySelector('[data-import-progress]');
    const result = widget.querySelector('[data-import-result]');
    const refresh = widget.querySelector('[data-import-refresh]');
    const storageKey = `fuel-db-import:${widget.dataset.owner}`;
    const buttonHtml = button?.innerHTML;
    let busy = true;

    function remember(jobId) {
        try {
            if (jobId) sessionStorage.setItem(storageKey, jobId);
            else sessionStorage.removeItem(storageKey);
        } catch (error) {
            console.warn('Не удалось сохранить локальный статус импорта', error);
        }
    }

    function setBusy(value) {
        busy = value;
        if (button) {
            button.disabled = value;
            if (value) button.textContent = 'Импорт... (подождите)';
            else button.innerHTML = buttonHtml;
        }
        if (input) input.disabled = value;
    }

    function show(message, kind = 'info') {
        status.hidden = false;
        status.classList.remove('alert-info', 'alert-success', 'alert-danger', 'alert-warning');
        status.classList.add(`alert-${kind}`);
        detail.textContent = message;
        const collapse = widget.closest('.collapse');
        if (collapse) collapse.classList.add('show');
    }

    async function request(url, options = {}) {
        const response = await fetch(url, {
            ...options, credentials: 'same-origin', cache: 'no-store',
            headers: {'X-Requested-With': 'XMLHttpRequest', Accept: 'application/json'},
        });
        if (response.redirected || response.status === 401) {
            const error = new Error('Сеанс завершен. Войдите в систему и обновите страницу для проверки импорта.');
            error.status = 401;
            throw error;
        }
        if (response.status === 404) {
            const error = new Error('Задание импорта не найдено.');
            error.status = 404;
            throw error;
        }
        const payload = await response.json();
        if (!response.ok || !payload.ok) {
            const error = new Error(payload.error || 'Сервис импорта временно недоступен.');
            error.status = response.status;
            throw error;
        }
        return payload.job;
    }

    function render(job) {
        const running = job.status === 'running';
        show(job.detail, running ? 'info' : job.status === 'done' ? 'success' : 'danger');
        file.textContent = `${job.filename}. Версия БД: ${job.database_version_id}`;
        progress.textContent = job.total ? `На текущем этапе: ${job.current} из ${job.total}` : '';
        result.textContent = job.error || job.result?.message || '';
        refresh.hidden = job.status !== 'done';
        if (job.status === 'done') refresh.href = job.redirect_url;
        setBusy(running);
        if (!running) {
            remember(null);
            if (input) input.value = '';
        }
    }

    async function poll(jobId) {
        try {
            const url = widget.dataset.statusUrl.replace('JOB_ID', encodeURIComponent(jobId));
            const job = await request(url);
            render(job);
            if (job.status === 'running') window.setTimeout(() => poll(jobId), 2000);
        } catch (error) {
            if (error.status === 404) {
                delete widget.dataset.initialJob;
                remember(null);
                show('Сохраненное задание не найдено. Проверяем текущий импорт...', 'warning');
                await recover();
            } else if (error.status === 401) {
                show(error.message, 'warning');
            } else {
                show('Связь со статусом временно потеряна. Импорт на сервере не отменен; проверка будет повторена.', 'warning');
                window.setTimeout(() => poll(jobId), 3000);
            }
        }
    }

    async function recover() {
        try {
            const active = await request(widget.dataset.activeUrl);
            let saved = widget.dataset.initialJob;
            if (!saved) {
                try { saved = sessionStorage.getItem(storageKey); }
                catch (error) { console.warn('Локальный статус импорта недоступен', error); }
            }
            const jobId = active?.id || saved;
            if (jobId) {
                remember(jobId);
                setBusy(true);
                await poll(jobId);
            } else {
                setBusy(false);
            }
        } catch (error) {
            show(error.status === 401 ? error.message : 'Не удалось проверить текущий импорт. Проверка будет повторена.', 'warning');
            if (error.status !== 401) window.setTimeout(recover, 3000);
        }
    }

    if (form) {
        if (button.type === 'button') button.addEventListener('click', () => input.click());
        if (input.hasAttribute('data-auto-submit')) {
            input.addEventListener('change', () => {
                if (!busy && input.files.length) form.requestSubmit();
            });
        }
        form.addEventListener('submit', async event => {
            event.preventDefault();
            if (busy || !input.files.length) return;
            const body = new FormData(form);
            setBusy(true);
            refresh.hidden = true;
            result.textContent = '';
            progress.textContent = '';
            show('Передача файла на сервер...');
            try {
                const job = await request(form.action, {method: 'POST', body});
                remember(job.id);
                render(job);
                if (job.status === 'running') await poll(job.id);
            } catch (error) {
                if (error.status >= 400 && error.status < 500 && error.status !== 401) {
                    show(error.message, 'danger');
                    setBusy(false);
                    input.value = '';
                } else {
                    show('Не удалось подтвердить запуск. Проверяем задание на сервере...', 'warning');
                    window.setTimeout(recover, 3000);
                }
            }
        });
    }
    setBusy(true);
    recover();
})();
