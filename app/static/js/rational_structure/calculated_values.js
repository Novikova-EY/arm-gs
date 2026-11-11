(() => {
    'use strict';

    for (const panel of document.querySelectorAll('[data-calculated-values]')) {
        const button = panel.querySelector('[data-load-results]');
        const content = panel.querySelector('[data-result-content]');
        const status = panel.querySelector('[data-result-status]');

        button.addEventListener('click', async () => {
            if (button.disabled) return;
            button.disabled = true;
            content.setAttribute('aria-busy', 'true');
            status.classList.remove('text-danger');
            status.textContent = 'Загрузка данных из API...';
            try {
                const response = await fetch(button.dataset.url, {
                    headers: {Accept: 'application/json'},
                    credentials: 'same-origin',
                    cache: 'no-store',
                });
                if (response.redirected || response.status === 401) {
                    throw new Error('Сеанс завершен. Обновите страницу и войдите в систему.');
                }
                if (!response.headers.get('Content-Type')?.includes('application/json')) {
                    throw new Error(`Сервер вернул неожиданный ответ (HTTP ${response.status}). Повторите загрузку.`);
                }
                const payload = await response.json();
                if (!response.ok) {
                    throw new Error(payload.error || `Ошибка загрузки (HTTP ${response.status}).`);
                }
                if (typeof payload.html !== 'string') {
                    throw new Error('Сервер вернул некорректные данные. Повторите загрузку.');
                }
                // HTML формируется нашим шаблоном с экранированием значений внешнего API.
                content.innerHTML = payload.html;
                status.textContent = 'Загрузка завершена. Таблица обновлена.';
            } catch (error) {
                status.classList.add('text-danger');
                if (error instanceof TypeError) {
                    status.textContent = 'Не удалось связаться с сервером. Проверьте соединение и повторите загрузку.';
                } else if (error instanceof SyntaxError) {
                    status.textContent = 'Сервер вернул некорректный JSON. Повторите загрузку.';
                } else {
                    status.textContent = error.message;
                }
            } finally {
                button.disabled = false;
                content.setAttribute('aria-busy', 'false');
            }
        });
    }
})();
