(() => {
    'use strict';
    const notice = document.querySelector('[data-achievement-notice]');
    if (!notice) return;
    let timeout;
    let dismissed = false;
    const dismiss = () => {
        if (dismissed) return;
        dismissed = true;
        clearTimeout(timeout);
        notice.classList.add('is-dismissed');
        window.setTimeout(() => notice.remove(), 250);
    };
    const pause = () => clearTimeout(timeout);
    const resume = () => {
        pause();
        timeout = window.setTimeout(dismiss, 10000);
    };
    const acknowledge = async () => {
        const data = new FormData();
        data.set('csrf_token', notice.dataset.csrf);
        JSON.parse(notice.dataset.badges).forEach(key => data.append('badge', key));
        try {
            await fetch(notice.dataset.ackUrl, { method: 'POST', body: data, credentials: 'same-origin', headers: { Accept: 'application/json' } });
        } catch (_) {
            // An unacknowledged milestone remains available on the next page.
        }
    };
    const show = () => {
        if (document.visibilityState === 'hidden') return;
        document.removeEventListener('visibilitychange', show);
        acknowledge();
        notice.classList.add('is-timed');
        resume();
    };
    notice.querySelector('[data-dismiss-achievement]').addEventListener('click', dismiss);
    notice.addEventListener('mouseenter', pause);
    notice.addEventListener('mouseleave', resume);
    notice.addEventListener('focusin', pause);
    notice.addEventListener('focusout', event => { if (!notice.contains(event.relatedTarget)) resume(); });
    if (document.visibilityState === 'hidden') document.addEventListener('visibilitychange', show);
    else show();
})();
