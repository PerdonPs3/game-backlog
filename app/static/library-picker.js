"use strict";

(() => {
    const form = document.querySelector('.adventure-preferences');
    const genre = document.querySelector('#pick-genre');
    if (!form || !genre) return;
    form.addEventListener('change', (event) => {
        // The available genres are scoped to the selected states.
        if (event.target.name === 'status') genre.value = '';
    });
})();
