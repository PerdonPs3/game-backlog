(() => {
    const trigger = document.querySelector('[data-edit-background]');
    const dialog = document.querySelector('[data-background-options]');
    const field = document.querySelector('#profile-background');
    if (!trigger || !dialog || !field || typeof dialog.showModal !== 'function') return;
    dialog.querySelector('[data-background-options-body]').append(field);
    trigger.addEventListener('click', event => {
        event.preventDefault();
        dialog.showModal();
    });
    dialog.querySelector('[data-background-options-close]').addEventListener('click', () => dialog.close());
    dialog.addEventListener('close', () => { if (!document.querySelector('[data-background-dialog]')?.open) trigger.focus(); });
    // Close options before the crop dialog opens; keep all inputs in the profile form.
    field.querySelector('[name="background"]').addEventListener('change', () => { if (dialog.open) dialog.close(); });
    field.querySelector('[data-background-adjust]').addEventListener('click', () => { if (dialog.open) dialog.close(); });
    if (window.location.hash === '#profile-background') dialog.showModal();
})();
