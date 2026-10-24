"use strict";
(() => {
    const name = document.getElementById('display-name');
    const username = document.getElementById('setup-username');
    if (!name || !username || username.readOnly) return;
    const reserved = new Set(JSON.parse(username.dataset.reservedUsernames || '[]'));
    let automatic = !username.value;
    function suggest() {
        if (!automatic) return;
        const display = name.value.trim();
        if (!display) { username.value = ''; return; }
        let value = display.normalize('NFKD').replace(/[\u0300-\u036f]/g, '').toLowerCase()
            .replace(/[^a-z0-9_]+/g, '_').replace(/^_+|_+$/g, '');
        if (!value) value = 'player';
        if (!/^[a-z]/.test(value)) value = `player_${value}`;
        value = value.slice(0, 24);
        if (value.length < 3 || reserved.has(value)) value = `${value}_player`.slice(0, 24);
        username.value = value;
    }
    name.addEventListener('input', suggest);
    name.addEventListener('change', suggest);
    username.addEventListener('input', () => { automatic = false; });
    suggest();
})();
