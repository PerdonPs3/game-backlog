(() => {
    'use strict';
    const input = document.querySelector('[data-help-query]');
    if (!input) return;
    const topics = [...document.querySelectorAll('[data-help-topic]')];
    const empty = document.querySelector('[data-help-empty]');
    function update() {
        const query = input.value.trim().toLocaleLowerCase();
        let visible = false;
        for (const topic of topics) {
            let matches = false;
            for (const entry of topic.querySelectorAll('[data-help-entry]')) {
                entry.hidden = !entry.dataset.helpText.toLocaleLowerCase().includes(query);
                matches ||= !entry.hidden;
            }
            topic.hidden = !matches;
            visible ||= matches;
        }
        empty.hidden = visible;
    }
    input.addEventListener('input', update);
    input.form?.addEventListener('submit', event => { event.preventDefault(); update(); });
    update();
})();
