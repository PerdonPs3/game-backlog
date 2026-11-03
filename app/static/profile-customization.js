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
})();
