/* Keep the existing ISO form fields; enhance date entry without a browser popup. */
(() => {
    function dateValue(day, month, year) {
        const parts = [day, month, year].map(value => String(value).trim());
        if (parts.every(value => !value)) return { value: '', error: '' };
        if (parts.some(value => !value)) return { value: '', error: 'Enter a complete date or clear it.' };
        if (parts.some(value => !/^\d+$/.test(value))) return { value: '', error: 'Choose a valid date.' };
        if (parts[2].length !== 4) return { value: '', error: 'Use a four-digit year.' };
        const [d, m, y] = parts.map(Number);
        const leap = y % 4 === 0 && (y % 100 !== 0 || y % 400 === 0);
        const days = [31, leap ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
        if (y < 1 || y > 9999 || m < 1 || m > 12 || d < 1 || d > days[m - 1]) {
            return { value: '', error: 'Choose a valid date.' };
        }
        return { value: `${String(y).padStart(4, '0')}-${String(m).padStart(2, '0')}-${String(d).padStart(2, '0')}`, error: '' };
    }

    if (typeof module !== 'undefined' && module.exports) module.exports = { dateValue };
    if (typeof document === 'undefined') return;
    const months = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
    for (const native of document.querySelectorAll('[data-play-date]')) {
        if (native.dataset.enhanced) continue;
        const name = native.dataset.dateLabel;
        const originalId = native.id;
        const label = native.parentElement.querySelector(`label[for="${originalId}"]`);
        const entry = document.createElement('div');
        entry.className = 'date-entry';
        entry.innerHTML = '<div class="date-parts" role="group"><label class="date-part"><span>Day</span><input type="text" inputmode="numeric" maxlength="2" placeholder="DD" autocomplete="off"></label><label class="date-part"><span>Month</span><select><option value="">—</option></select></label><label class="date-part"><span>Year</span><input type="text" inputmode="numeric" maxlength="4" placeholder="YYYY" autocomplete="off"></label></div><div class="date-entry-actions"><button type="button" data-date-today>Today</button><button type="button" data-date-clear>Clear</button></div>';
        const group = entry.querySelector('.date-parts');
        group.setAttribute('aria-label', name);
        entry.querySelector('[data-date-today]').setAttribute('aria-label', name + ': today');
        entry.querySelector('[data-date-clear]').setAttribute('aria-label', name + ': clear');
        const [day, month, year] = entry.querySelectorAll('input, select');
        day.id = originalId + '-day';
        day.setAttribute('aria-label', name + ' day');
        month.setAttribute('aria-label', name + ' month');
        year.setAttribute('aria-label', name + ' year');
        months.forEach((text, index) => month.add(new Option(text.slice(0, 3), String(index + 1))));

        function restore() {
            const parts = native.value.split('-');
            year.value = parts[0] || '';
            month.value = parts[1] ? String(Number(parts[1])) : '';
            day.value = parts[2] ? String(Number(parts[2])) : '';
            day.setCustomValidity('');
        }
        function update() {
            const result = dateValue(day.value, month.value, year.value);
            day.setCustomValidity(result.error);
            native.value = result.value;
            native.dispatchEvent(new Event('input', { bubbles: true }));
            native.dispatchEvent(new Event('change', { bubbles: true }));
        }
        restore();
        [day, month, year].forEach(part => {
            part.addEventListener('input', update);
            part.addEventListener('change', update);
        });
        entry.querySelector('[data-date-today]').addEventListener('click', () => {
            const today = new Date();
            day.value = String(today.getDate());
            month.value = String(today.getMonth() + 1);
            year.value = String(today.getFullYear());
            update();
        });
        entry.querySelector('[data-date-clear]').addEventListener('click', () => {
            day.value = month.value = year.value = '';
            update();
            day.focus();
        });
        native.form?.addEventListener('reset', () => queueMicrotask(restore));
        native.insertAdjacentElement('afterend', entry);
        native.type = 'hidden';
        native.id = originalId + '-value';
        native.dataset.enhanced = 'true';
        if (label) label.htmlFor = day.id;
    }
})();
