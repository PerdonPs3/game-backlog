(() => {
    for (const picker of document.querySelectorAll('[data-rating-picker]')) {
        const output = picker.querySelector('[data-rating-score]');
        const update = () => {
            const value = picker.querySelector('input:checked')?.value;
            output.textContent = value ? `${value}/10` : 'Not rated';
        };
        picker.addEventListener('change', update);
        picker.closest('form')?.addEventListener('reset', () => setTimeout(update, 0));
        update();
    }
})();
