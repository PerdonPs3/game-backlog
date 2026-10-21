"use strict";
(() => {
    const password = document.getElementById('password');
    if (!password) return;
    const form = password.form;
    const confirmation = document.getElementById('confirmation');
    const counter = document.getElementById('password-count');
    const feedback = document.getElementById('confirmation-feedback');
    const toggles = document.querySelectorAll('[data-password-toggle]');
    function conceal() {
        toggles.forEach(button => {
            document.getElementById(button.dataset.passwordToggle).type = 'password';
            button.setAttribute('aria-pressed', 'false');
            button.setAttribute('aria-label', button.dataset.passwordToggle === 'confirmation' ? 'Show confirm password' : 'Show password');
            button.querySelector('[data-eye-slash]').toggleAttribute('hidden', true);
        });
    }
    function validate() {
        if (counter) {
            const length = Array.from(password.value).length;
            counter.textContent = `${length} characters · Min. 8 · Max. 128`;
            password.setCustomValidity(length && (length < 8 || length > 128) ? 'Use 8 to 128 characters.' : '');
        }
        if (confirmation) {
            const mismatch = confirmation.value && confirmation.value !== password.value;
            confirmation.setCustomValidity(mismatch ? 'Passwords do not match.' : '');
            const text = !confirmation.value ? '' : mismatch ? 'Passwords do not match.' : 'Passwords match.';
            if (feedback.textContent !== text) feedback.textContent = text;
        }
    }
    toggles.forEach(button => {
        button.hidden = false;
        button.addEventListener('click', () => {
            const input = document.getElementById(button.dataset.passwordToggle);
            const show = input.type === 'password';
            input.type = show ? 'text' : 'password';
            button.setAttribute('aria-pressed', String(show));
            button.setAttribute('aria-label', `${show ? 'Hide' : 'Show'} ${input.id === 'confirmation' ? 'confirm password' : 'password'}`);
            button.querySelector('[data-eye-slash]').toggleAttribute('hidden', !show);
        });
    });
    password.addEventListener('input', validate);
    confirmation?.addEventListener('input', validate);
    form.addEventListener('submit', conceal);
    form.addEventListener('reset', () => { conceal(); window.setTimeout(validate, 0); });
    window.addEventListener('pagehide', conceal);
    window.addEventListener('pageshow', () => { conceal(); validate(); });
    validate();
})();
