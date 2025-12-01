document.addEventListener("DOMContentLoaded", () => {
    function wireOpenInNewTab(formId) {
        const form = document.getElementById(formId);
        if (!form) return;
        const submitBtn = form.querySelector('button[type="submit"], button');
        if (!submitBtn) return;
        submitBtn.addEventListener('click', (e) => {
            try {
                e.preventDefault();
                const action = form.getAttribute('action');
                if (!action) return;
                const params = new URLSearchParams();
                // include all inputs
                form.querySelectorAll('input').forEach(inp => {
                    if (!inp.name) return;
                    if (inp.type === 'checkbox' || inp.type === 'radio') {
                        if (inp.checked) params.append(inp.name, inp.value);
                    } else if (inp.type === 'file') {
                        // skip file inputs for GET
                    } else {
                        params.append(inp.name, inp.value ?? '');
                    }
                });
                const url = action + (action.includes('?') ? '&' : '?') + params.toString();
                window.open(url, '_blank', 'noopener');
            } catch (_) {
                // fallback to default behavior
                form.submit();
            }
        });
    }

    // НЕ перехватываем exportExcelFormFull - он обрабатывается в station_page_logic.js
    // wireOpenInNewTab('exportExcelFormFull');
    wireOpenInNewTab('exportExcelSiprForm');
});

