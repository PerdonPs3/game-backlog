(() => {
    'use strict';
    const form = document.querySelector('#profile-form');
    if (!form) return;
    const badges = [...form.querySelectorAll('[name="featured_badges"]')];
    const dialog = form.querySelector('[data-badge-dialog]');
    const choose = form.querySelector('[data-badge-choose]');
    const summary = form.querySelector('[data-badge-summary]');
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
        for (const input of selected.slice(0, 3)) {
            const label = input.closest('label');
            const item = document.createElement('div');
            item.className = 'badge-summary-card';
            item.append(label.querySelector('.achievement-emblem').cloneNode(true));
            const name = document.createElement('span');
            name.textContent = label.querySelector('span:last-child').firstChild.textContent;
            item.append(name);
            summary.append(item);
        }
        if (!selected.length) {
            const empty = document.createElement('p');
            empty.className = 'profile-field-hint';
            empty.textContent = badges.length ? 'Choose badges to feature here.' : 'Add a game to unlock your first badge.';
            summary.append(empty);
        }
    };
    badges.forEach(input => input.addEventListener('change', validateBadges));
    choose?.addEventListener('click', () => dialog.showModal());
    dialog.querySelector('[data-badge-done]').addEventListener('click', () => dialog.close());
    dialog.addEventListener('close', () => choose?.focus());
    validateBadges();
})();
