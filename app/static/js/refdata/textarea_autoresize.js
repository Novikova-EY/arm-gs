<!-- Скрипт подстройки высоты строк под содержимое ячеек -->

function autoResize(textarea) {
    textarea.style.height = 'auto'; // Сбрасываем текущую высоту
    textarea.style.height = textarea.scrollHeight + 'px'; // Устанавливаем новую высоту
}

// Если нужно, чтобы поле изначально подстраивалось под контент:
document.querySelectorAll('textarea').forEach(textarea => {
    autoResize(textarea);
});
