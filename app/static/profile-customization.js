(() => {
    'use strict';
    const form = document.querySelector('#profile-form');
    if (!form) return;
    const badges = [...form.querySelectorAll('[name="featured_badges"]')];
    const dialog = form.querySelector('[data-badge-dialog]');
    const summary = form.querySelector('[data-badge-summary]');
    let activeSlot = 0;
    const validateBadges = () => {
        const selected = badges.filter(input => input.checked);
        const message = selected.length > 3 ? 'Choose up to three featured badges.' : '';
        badges.forEach(input => {
            input.setCustomValidity(message);
            input.disabled = !input.checked && selected.length >= 3;
        });
        form.querySelector('[data-badge-selection-count]').textContent = `${selected.length}/3 featured`;
        form.querySelector('[data-badge-dialog-count]').textContent = `${selected.length}/3 selected`;
        summary.replaceChildren();
        for (let slot = 0; slot < 3; slot++) {
            const input = selected[slot];
            const item = document.createElement('button');
            item.type = 'button';
            item.className = 'badge-summary-card';
            item.setAttribute('aria-haspopup', 'dialog');
            const name = document.createElement('span');
            if (input) {
                const label = input.closest('label');
                item.append(label.querySelector('.achievement-emblem').cloneNode(true));
                name.textContent = label.querySelector('span:last-child').firstChild.textContent;
                item.setAttribute('aria-label', `Change badge: ${name.textContent}`);
            } else {
                item.className += ' is-empty';
                const plus = document.createElement('span');
                plus.className = 'badge-slot-plus';
                plus.textContent = '+';
                plus.setAttribute('aria-hidden', 'true');
                item.append(plus);
                name.textContent = 'Add badge';
                item.setAttribute('aria-label', 'Add badge');
            }
            item.append(name);
            item.addEventListener('click', () => { activeSlot = slot; dialog.showModal(); });
            summary.append(item);
        }
    };
    badges.forEach(input => input.addEventListener('change', validateBadges));
    dialog.querySelector('[data-badge-done]').addEventListener('click', () => dialog.close());
    dialog.addEventListener('close', () => summary.children[activeSlot]?.focus());
    validateBadges();
})();
