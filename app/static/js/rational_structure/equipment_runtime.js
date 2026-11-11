(function () {
    const button = document.getElementById('rs-runtime-calculation-toggle');
    if (!button) return;

    const page = button.closest('.rs-data-page');
    button.addEventListener('click', function () {
        const hidden = page.classList.toggle('rs-runtime-results-hidden');
        button.classList.toggle('active', !hidden);
        button.setAttribute('aria-pressed', String(!hidden));
        window.armGsApplyStickyTheadOffsets?.();
    });
})();
