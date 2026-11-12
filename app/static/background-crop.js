(function () {
    const clamp = (value, min, max) => Math.max(min, Math.min(max, value));
    function cropBox(width, height, zoom, cx, cy) {
        const w = Math.min(width, height * 8 / 3) / zoom;
        const h = w * 3 / 8;
        return {x: clamp(cx - w / 2, 0, width - w), y: clamp(cy - h / 2, 0, height - h), width: w, height: h};
    }
    async function optimizeBackground(source, createCanvas = () => document.createElement('canvas')) {
        const canvas = createCanvas();
        const scale = Math.min(1, 2400 / Math.max(source.naturalWidth, source.naturalHeight));
        canvas.width = Math.max(1, Math.round(source.naturalWidth * scale));
        canvas.height = Math.max(1, Math.round(source.naturalHeight * scale));
        const target = canvas.getContext('2d');
        if (!target) throw new Error('Canvas unavailable');
        target.fillStyle = '#182126';
        target.fillRect(0, 0, canvas.width, canvas.height);
        target.drawImage(source, 0, 0, canvas.width, canvas.height);
        for (const quality of [.9, .8, .65, .5, .35]) {
            const blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/jpeg', quality));
            if (!blob) throw new Error('Encoding failed');
            if (blob.size <= 2 * 1024 * 1024) return {canvas, blob};
        }
        throw new Error('Optimization failed');
    }
    if (typeof module !== 'undefined' && module.exports) { module.exports = {cropBox, optimizeBackground}; return; }
    const form = document.querySelector('#profile-form');
    const upload = form?.querySelector('[name="background"]');
    if (!upload) return;
    const dialog = document.querySelector('[data-background-dialog]');
    const editor = form.querySelector('[data-background-editor]');
    const preview = form.querySelector('[data-background-preview]');
    const adjust = form.querySelector('[data-background-adjust]');
    const canvas = dialog.querySelector('[data-background-canvas]');
    const context = canvas.getContext('2d');
    if (!context) return;
    const zoom = dialog.querySelector('[data-background-zoom]');
    const apply = dialog.querySelector('[data-background-apply]');
    const error = dialog.querySelector('[data-background-error]');
    const loading = dialog.querySelector('[data-background-dialog-status]');
    const crop = form.querySelector('[name="background_crop"]');
    const status = form.querySelector('[data-background-status]');
    const saved = form.querySelector('[data-background-saved]');
    const custom = form.querySelector('[data-background-custom]');
    const customRadio = custom.querySelector('input');
    const remove = form.querySelector('[name="remove_background"]');
    let committed = null, staged = null, box, cx, cy, pointer, objectUrl, generation = 0;
    let returnFocus = upload;

    function restoreFile() {
        const transfer = new DataTransfer();
        if (committed) transfer.items.add(committed.file);
        upload.files = transfer.files;
    }
    function cleanup() {
        generation++;
        if (objectUrl) URL.revokeObjectURL(objectUrl);
        objectUrl = null;
        staged = pointer = null;
    }
    function draw() {
        const image = staged.image;
        box = cropBox(image.width, image.height, Number(zoom.value), cx, cy);
        cx = box.x + box.width / 2; cy = box.y + box.height / 2;
        context.fillStyle = '#182126';
        context.fillRect(0, 0, canvas.width, canvas.height);
        context.drawImage(image, box.x, box.y, box.width, box.height, 0, 0, canvas.width, canvas.height);
    }
    function show() {
        error.textContent = ''; loading.textContent = '';
        apply.disabled = true; zoom.disabled = true; canvas.hidden = true;
        dialog.showModal();
    }
    function ready() {
        canvas.hidden = false; zoom.disabled = false; apply.disabled = false;
        draw(); loading.textContent = '';
    }
    function move(dx, dy) {
        if (!staged) return;
        cx -= dx * box.width / canvas.getBoundingClientRect().width;
        cy -= dy * box.height / canvas.getBoundingClientRect().height;
        draw();
    }
    upload.addEventListener('change', () => {
        const file = upload.files[0];
        restoreFile();
        if (!file) return;
        cleanup(); returnFocus = upload;
        show();
        const fail = message => {
            cleanup(); loading.textContent = ''; error.textContent = message;
            apply.disabled = true; canvas.hidden = true; zoom.disabled = true;
        };
        if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) return fail('Choose a JPG, PNG, or WebP background.');
        const current = generation;
        const candidate = new Image();
        objectUrl = URL.createObjectURL(file);
        loading.textContent = 'Optimizing your background…';
        candidate.onload = async () => {
            if (current !== generation) return;
            try {
                if (!candidate.naturalWidth || !candidate.naturalHeight) throw new Error('Invalid image');
                const optimized = await optimizeBackground(candidate);
                if (current !== generation) return;
                staged = {image: optimized.canvas,
                    file: new File([optimized.blob], 'profile-background.jpg', {type: 'image/jpeg'})};
                cx = staged.image.width / 2; cy = staged.image.height / 2; zoom.value = '1';
                ready();
                if (objectUrl) URL.revokeObjectURL(objectUrl);
                objectUrl = null;
            } catch (_) {
                if (current === generation) fail('This image could not be optimized. Try exporting it as JPG or choosing another image.');
            }
        };
        candidate.onerror = () => { if (current === generation) fail('This image could not be opened. Choose another background.'); };
        candidate.src = objectUrl;
    });
    adjust.addEventListener('click', () => {
        if (!committed) return;
        cleanup(); returnFocus = adjust; show();
        staged = {image: committed.image, file: committed.file};
        cx = committed.cx; cy = committed.cy; zoom.value = committed.zoom;
        ready();
    });
    apply.addEventListener('click', () => {
        if (!staged) return;
        draw();
        committed = {...staged, cx, cy, zoom: zoom.value};
        restoreFile();
        crop.value = JSON.stringify(box);
        preview.src = canvas.toDataURL('image/jpeg', .9);
        editor.hidden = false;
        if (saved) saved.hidden = true;
        custom.hidden = false; customRadio.checked = true;
        if (remove) remove.checked = false;
        status.textContent = '';
        form.dispatchEvent(new Event('change', {bubbles: true}));
        returnFocus = adjust;
        dialog.close();
    });
    dialog.querySelector('[data-background-cancel]').addEventListener('click', () => dialog.close());
    dialog.addEventListener('close', () => {
        cleanup(); restoreFile();
        const hiddenOptions = returnFocus.closest('[data-background-options]');
        const target = hiddenOptions && !hiddenOptions.open ? document.querySelector('[data-edit-background]') : returnFocus;
        target?.focus();
    });
    canvas.addEventListener('pointerdown', event => {
        if (!staged || event.button !== 0) return;
        event.preventDefault(); canvas.focus();
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
    zoom.addEventListener('input', () => { if (staged) draw(); });
    dialog.querySelector('[data-background-center]').addEventListener('click', () => {
        if (!staged) return;
        cx = staged.image.width / 2; cy = staged.image.height / 2; zoom.value = '1'; draw();
    });
    function discard() {
        cleanup(); committed = null; restoreFile(); crop.value = ''; editor.hidden = true;
        preview.removeAttribute('src'); status.textContent = '';
        if (saved) saved.hidden = false;
        custom.hidden = !saved;
    }
    for (const preset of form.querySelectorAll('[name="background_key"]')) preset.addEventListener('change', () => {
        if (preset.checked && preset.value !== 'custom') discard();
    });
    remove?.addEventListener('change', () => {
        if (!remove.checked) return;
        discard();
        if (customRadio.checked) form.querySelector('[name="background_key"][value="castle"]').checked = true;
    });
    window.addEventListener('pagehide', cleanup);
})();
