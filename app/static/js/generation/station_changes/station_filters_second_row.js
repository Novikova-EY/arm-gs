document.addEventListener("DOMContentLoaded", function () {
    const form = document.getElementById("exportExcelFormFull");
    const button = document.getElementById("exportExcelFull");

    if (!form || !button) {
        console.warn("Форма или кнопка не найдены!");
        return;
    }

    button.addEventListener("click", function (event) {
        event.preventDefault();

        form.querySelectorAll("input[name='show_p_ogr'], input[name='show_p_rasp']").forEach(el => el.remove());

        if (document.getElementById("toggleP_Ogr")?.checked) {
            const inputOgr = document.createElement("input");
            inputOgr.type = "hidden";
            inputOgr.name = "show_p_ogr";
            inputOgr.value = "1";
            form.appendChild(inputOgr);
        }

        if (document.getElementById("toggleP_Rasp")?.checked) {
            const inputRasp = document.createElement("input");
            inputRasp.type = "hidden".style;
            inputRasp.name = "show_p_rasp";
            inputRasp.value = "1";
            form.appendChild(inputRasp);
        }

        form.submit();
    });
});

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