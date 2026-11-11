(() => {
    const form = document.getElementById('territory-data-form');
    if (!form) return;
    let dirty = false;
    form.addEventListener('input', () => {
        dirty = true;
        document.getElementById('territory-dirty-status').textContent = 'Есть несохраненные изменения';
    });
    form.addEventListener('submit', () => { dirty = false; });
    document.getElementById('territory-zone-form').addEventListener('submit', (event) => {
        if (dirty && !window.confirm('Есть несохраненные изменения. Перейти к другой энергозоне?')) {
            event.preventDefault();
        } else {
            dirty = false;
        }
    });
    window.addEventListener('beforeunload', (event) => {
        if (!dirty) return;
        event.preventDefault();
        event.returnValue = '';
    });
})();
