(() => {
    const editor = document.querySelector('[data-profile-editor]');
    if (!editor) return;
    const select = editor.querySelector('[name="country_code"]');
    const badge = editor.querySelector('[data-profile-country]');
    const flag = badge?.querySelector('[data-country-flag]');
    if (!select || !badge || !flag) return;
    function previewCountry() {
        const option = select.selectedOptions[0];
        const visible = Boolean(option?.value && option.dataset.flag);
        badge.hidden = !visible;
        if (visible) {
            flag.src = option.dataset.flag;
            flag.alt = option.textContent;
            badge.title = option.textContent;
        } else {
            flag.removeAttribute('src');
            flag.alt = '';
            badge.removeAttribute('title');
        }
    }
    select.addEventListener('change', previewCountry);
    window.addEventListener('pageshow', previewCountry);
    previewCountry();
})();
