document.addEventListener('DOMContentLoaded', function () {
    const journal = document.querySelector('.rs-journal');
    if (!journal) return;
    const table = journal.querySelector('table');
    const body = table.tBodies[0];
    const button = journal.querySelector('.rs-journal-more');
    const pageEvents = journal.querySelector('.rs-journal-page-events');
    const status = journal.querySelector('.rs-journal-status');
    let offset = 0;
    let loaded = false;
    let loading = false;

    async function load(reset) {
        if (loading) return;
        if (reset) {
            offset = 0;
            loaded = false;
            body.replaceChildren();
        }
        loading = true;
        button.disabled = true;
        pageEvents.disabled = true;
        button.hidden = false;
        status.textContent = 'Загрузка…';
        try {
            const url = new URL(journal.dataset.logsUrl, window.location.origin);
            url.searchParams.set('offset', String(offset));
            url.searchParams.set('show_page_events', String(pageEvents.checked));
            const response = await fetch(url, { headers: { Accept: 'application/json' } });
            if (!response.ok) throw new Error('HTTP ' + response.status);
            const data = await response.json();
            data.logs.forEach(log => body.appendChild(ChangeLogTable.rowFromLog(log)));
            offset += data.logs.length;
            loaded = true;
            ChangeLogTable.applyFilters(table);
            status.textContent = offset ? 'Загружено записей: ' + offset : 'Записей пока нет.';
            button.hidden = !data.has_more;
            button.textContent = 'Загрузить еще';
        } catch (error) {
            status.textContent = 'Не удалось загрузить журнал. Повторите попытку.';
            button.textContent = 'Повторить';
        } finally {
            loading = false;
            button.disabled = false;
            pageEvents.disabled = false;
        }
    }

    journal.addEventListener('toggle', function () {
        if (journal.open && !loaded) load(false);
    });
    pageEvents.addEventListener('change', () => load(true));
    button.addEventListener('click', () => load(false));
});
