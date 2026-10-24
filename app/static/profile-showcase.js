(() => {
    const form = document.querySelector('[data-showcase-form]');
    if (!form) return;
    const slots = [...form.querySelectorAll('[data-showcase-slot]')];
    const status = form.querySelector('[data-showcase-status]');
    function update(slot) {
        const select = slot.querySelector('select');
        const image = slot.querySelector('[data-slot-cover]');
        const cover = select.selectedOptions[0]?.dataset.cover;
        image.hidden = !cover;
        if (cover) image.src = cover;
        else image.removeAttribute('src');
    }
    for (const [index, slot] of slots.entries()) {
        const select = slot.querySelector('select');
        const image = slot.querySelector('[data-slot-cover]');
        image.addEventListener('error', () => { image.hidden = true; });
        select.addEventListener('change', () => {
            update(slot);
            status.textContent = 'You have unsaved showcase changes.';
        });
        for (const button of slot.querySelectorAll('[data-move]')) {
            button.addEventListener('click', () => {
                const other = slots[index + Number(button.dataset.move)];
                if (!other) return;
                const target = other.querySelector('select');
                [select.value, target.value] = [target.value, select.value];
                update(slot);
                update(other);
                status.textContent = 'Order updated. Save your showcase to keep these changes.';
                target.focus();
            });
        }
        update(slot);
    }
})();
