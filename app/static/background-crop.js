(function () {
    const clamp = (value, min, max) => Math.max(min, Math.min(max, value));
    function cropBox(width, height, zoom, cx, cy) {
        const w = Math.min(width, height * 8 / 3) / zoom;
        const h = w * 3 / 8;
        return {x: clamp(cx - w / 2, 0, width - w), y: clamp(cy - h / 2, 0, height - h), width: w, height: h};
    }
    if (typeof module !== 'undefined' && module.exports) { module.exports = {cropBox}; return; }
    const form = document.querySelector('#profile-form');
    const upload = form?.querySelector('[name="background"]');
    if (!upload) return;
    const editor = form.querySelector('[data-background-editor]');
    const canvas = form.querySelector('[data-background-canvas]');
    const context = canvas.getContext('2d');
    if (!context) return;
    const zoom = form.querySelector('[data-background-zoom]');
    const crop = form.querySelector('[name="background_crop"]');
    const status = form.querySelector('[data-background-status]');
    const saved = form.querySelector('[data-background-saved]');
    const custom = form.querySelector('[data-background-custom]');
    const customRadio = custom.querySelector('input');
    const remove = form.querySelector('[name="remove_background"]');
    let image, box, cx, cy, pointer, objectUrl, generation = 0;

    function dispose() {
        generation++;
        if (objectUrl) URL.revokeObjectURL(objectUrl);
        objectUrl = null;
        image = box = pointer = null;
        crop.value = '';
        editor.hidden = true;
        upload.setCustomValidity('');
        if (saved) saved.hidden = false;
        custom.hidden = !saved;
        if (!saved && customRadio.checked) form.querySelector('[name="background_key"][value="castle"]').checked = true;
    }
    function draw() {
        box = cropBox(image.naturalWidth, image.naturalHeight, Number(zoom.value), cx, cy);
        cx = box.x + box.width / 2;
        cy = box.y + box.height / 2;
        context.fillStyle = '#182126';
        context.fillRect(0, 0, canvas.width, canvas.height);
        context.drawImage(image, box.x, box.y, box.width, box.height, 0, 0, canvas.width, canvas.height);
        crop.value = JSON.stringify(box);
    }
    function move(dx, dy) {
        if (!image) return;
        cx -= dx * box.width / canvas.getBoundingClientRect().width;
        cy -= dy * box.height / canvas.getBoundingClientRect().height;
        draw();
    }
    upload.addEventListener('change', () => {
        dispose();
        status.textContent = '';
        const file = upload.files[0];
        if (!file) return;
        const fail = message => {
            dispose();
            upload.setCustomValidity(message);
            status.textContent = message;
        };
        if (file.size > 2 * 1024 * 1024) return fail('Choose a background smaller than 2 MB.');
        if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) return fail('Choose a JPG, PNG, or WebP background.');
        const current = generation;
        const candidate = new Image();
        objectUrl = URL.createObjectURL(file);
        upload.setCustomValidity('Wait for your background preview to load.');
        status.textContent = 'Opening background…';
        candidate.onload = () => {
            if (current !== generation) return;
            if (!candidate.naturalWidth || !candidate.naturalHeight || candidate.naturalWidth * candidate.naturalHeight > 12000000) {
                return fail('Use a background with no more than 12 million pixels.');
            }
            image = candidate;
            cx = image.naturalWidth / 2;
            cy = image.naturalHeight / 2;
            zoom.value = '1';
            editor.hidden = false;
            if (saved) saved.hidden = true;
            custom.hidden = false;
            customRadio.checked = true;
            if (remove) remove.checked = false;
            draw();
            upload.setCustomValidity('');
            status.textContent = '';
        };
        candidate.onerror = () => { if (current === generation) fail('This image could not be opened. Choose another background.'); };
        candidate.src = objectUrl;
    });
    canvas.addEventListener('pointerdown', event => {
        if (!image || event.button !== 0) return;
        event.preventDefault();
        canvas.focus();
        pointer = {id: event.pointerId, x: event.clientX, y: event.clientY};
        canvas.setPointerCapture(event.pointerId);
    });
    canvas.addEventListener('pointermove', event => {
        if (!pointer || pointer.id !== event.pointerId) return;
        move(event.clientX - pointer.x, event.clientY - pointer.y);
        pointer.x = event.clientX; pointer.y = event.clientY;
    });
    for (const name of ['pointerup', 'pointercancel', 'lostpointercapture']) canvas.addEventListener(name, () => { pointer = null; });
    canvas.addEventListener('keydown', event => {
        const directions = {ArrowLeft: [-10, 0], ArrowRight: [10, 0], ArrowUp: [0, -10], ArrowDown: [0, 10]};
        if (!directions[event.key]) return;
        event.preventDefault(); move(...directions[event.key]);
    });
    zoom.addEventListener('input', () => { if (image) draw(); });
    form.querySelector('[data-background-center]').addEventListener('click', () => {
        if (!image) return;
        cx = image.naturalWidth / 2; cy = image.naturalHeight / 2; zoom.value = '1'; draw();
    });
    for (const preset of form.querySelectorAll('[name="background_key"]')) preset.addEventListener('change', () => {
        if (!preset.checked || preset.value === 'custom') return;
        upload.value = ''; dispose(); status.textContent = '';
    });
    remove?.addEventListener('change', () => {
        if (!remove.checked) return;
        upload.value = ''; dispose(); status.textContent = '';
        if (customRadio.checked) form.querySelector('[name="background_key"][value="castle"]').checked = true;
    });
    window.addEventListener('pagehide', () => { if (objectUrl) URL.revokeObjectURL(objectUrl); });
})();
