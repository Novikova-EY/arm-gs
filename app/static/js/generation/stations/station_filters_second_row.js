document.addEventListener('DOMContentLoaded', function () {
    const switchEl = document.getElementById('per_page_switch');
    const selectEl = document.getElementById('per_page_select');
    const hiddenInput = document.getElementById('per_page_hidden');
    const form = document.getElementById('perPageForm');
    const selectWrapper = document.getElementById('per_page_select_wrapper');

    function updatePerPage() {
        if (switchEl.checked) {
            hiddenInput.value = 'all';
            selectWrapper.style.display = 'none';
        } else {
            hiddenInput.value = selectEl.value;
            selectWrapper.style.display = 'block';
        }
    }

    if (switchEl && selectEl && hiddenInput && form && selectWrapper) {
        switchEl.addEventListener('change', function () {
            updatePerPage();
            setTimeout(() => {
                form.submit();
            }, 0);
        });

        selectEl.addEventListener('change', function () {
            updatePerPage();
            setTimeout(() => {
                form.submit();
            }, 0);
        });

        updatePerPage();
    } else {
        console.warn("❌ Некоторые элементы формы не найдены!");
    }
});