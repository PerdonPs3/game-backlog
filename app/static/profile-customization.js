(() => {
    'use strict';
    const form = document.querySelector('#profile-form');
    if (!form) return;
    const badges = [...form.querySelectorAll('[name="featured_badges"]')];
    const validateBadges = () => {
        const message = badges.filter(input => input.checked).length > 3 ? 'Choose up to three featured badges.' : '';
        badges.forEach(input => input.setCustomValidity(message));
    };
    badges.forEach(input => input.addEventListener('change', validateBadges));
    const upload = form.querySelector('[name="background"]');
    upload?.addEventListener('change', () => {
        const file = upload.files[0];
        upload.setCustomValidity(file && file.size > 2 * 1024 * 1024 ? 'Choose a background smaller than 2 MB.' : '');
        if (file) {
            const remove = form.querySelector('[name="remove_background"]');
            if (remove) remove.checked = false;
        }
    });
})();
