(function (root) {
    const clamp = (value, min, max) => Math.max(min, Math.min(max, value));
    const uploadLimit = 2 * 1024 * 1024;

    async function preparePhoto(image, file) {
        const width = image.naturalWidth, height = image.naturalHeight;
        if (!width || !height || width * height > 32000000) throw new Error();
        if (file.size <= uploadLimit && width * height <= 12000000) return { image, file, width, height };
        const canvas = document.createElement('canvas');
        const scale = Math.min(1, 2048 / Math.max(width, height));
        canvas.width = Math.max(1, Math.round(width * scale));
        canvas.height = Math.max(1, Math.round(height * scale));
        const context = canvas.getContext('2d');
        context.fillStyle = '#ffffff';
        context.fillRect(0, 0, canvas.width, canvas.height);
        context.drawImage(image, 0, 0, canvas.width, canvas.height);
        for (const quality of [0.9, 0.75, 0.6]) {
            const blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/jpeg', quality));
            if (!blob) throw new Error();
            if (blob.size <= uploadLimit) return {
                image: canvas,
                file: new File([blob], 'profile-photo.jpg', { type: 'image/jpeg' }),
                width: canvas.width, height: canvas.height,
            };
        }
        throw new Error();
    }

    function constrain(state) {
        const size = Math.min(state.width, state.height) / state.zoom;
        state.cx = clamp(state.cx, size / 2, state.width - size / 2);
        state.cy = clamp(state.cy, size / 2, state.height - size / 2);
        return { x: state.cx - size / 2, y: state.cy - size / 2, size };
    }

    function move(state, dx, dy) {
        const scale = 256 / (Math.min(state.width, state.height) / state.zoom);
        state.cx -= dx / scale;
        state.cy -= dy / scale;
        return constrain(state);
    }

    function create(editor, onApply, onError) {
        const dialog = editor.querySelector('[data-avatar-crop]');
        const canvas = dialog.querySelector('[data-crop-canvas]');
        const context = canvas.getContext('2d');
        const stage = dialog.querySelector('[data-crop-stage]');
        const zoom = dialog.querySelector('[data-crop-zoom]');
        const error = dialog.querySelector('[data-crop-error]');
        const status = dialog.querySelector('[data-crop-status]');
        const apply = dialog.querySelector('[data-crop-apply]');
        const replacement = dialog.querySelector('[data-crop-replacement]');
        let image, file, state, url, pointer, generation = 0;

        function cleanup() {
            if (url) URL.revokeObjectURL(url);
            url = null;
            image = file = state = pointer = null;
            generation++;
        }

        function draw() {
            if (!state) return;
            constrain(state);
            const scale = 256 / (Math.min(state.width, state.height) / state.zoom);
            context.fillStyle = '#10151e';
            context.fillRect(0, 0, 320, 320);
            context.drawImage(image, 160 - state.cx * scale, 160 - state.cy * scale, state.width * scale, state.height * scale);
        }

        async function open(candidate) {
            const current = ++generation;
            const report = (message) => {
                status.textContent = '';
                apply.disabled = !state;
                if (dialog.open) error.textContent = message;
                else onError(message);
            };
            error.textContent = '';
            status.textContent = 'Opening photo…';
            apply.disabled = true;
            try {
                if (!dialog.open) dialog.showModal();
            } catch (_) {
                report('The photo editor could not open. Reload the page and try again.');
                return;
            }
            if (!['image/jpeg', 'image/png', 'image/webp'].includes(candidate.type) || candidate.size > 20 * 1024 * 1024) {
                report('Choose a JPG, PNG, or WebP photo up to 20 MB.');
                return;
            }
            let candidateUrl;
            try {
                candidateUrl = URL.createObjectURL(candidate);
                const loaded = new Image();
                loaded.src = candidateUrl;
                await loaded.decode();
                if (current !== generation) { URL.revokeObjectURL(candidateUrl); return; }
                status.textContent = 'Preparing photo…';
                const prepared = await preparePhoto(loaded, candidate);
                if (current !== generation) { URL.revokeObjectURL(candidateUrl); return; }
                if (url) URL.revokeObjectURL(url);
                url = candidateUrl;
                image = prepared.image;
                file = prepared.file;
                pointer = null;
                state = { width: prepared.width, height: prepared.height, zoom: 1, cx: prepared.width / 2, cy: prepared.height / 2 };
                zoom.value = '1';
                error.textContent = '';
                status.textContent = '';
                apply.disabled = false;
                draw();
                stage.focus();
            } catch (_) {
                URL.revokeObjectURL(candidateUrl);
                if (current !== generation) return;
                report('This photo could not be prepared. Try a smaller still JPG, PNG, or WebP, up to 32 million pixels.');
            }
        }

        dialog.querySelector('[data-crop-replace]').addEventListener('click', () => replacement.click());
        replacement.addEventListener('change', () => {
            const candidate = replacement.files[0];
            replacement.value = '';
            if (candidate) return open(candidate);
        });

        stage.addEventListener('pointerdown', (event) => {
            if (!state || (event.button !== undefined && event.button !== 0)) return;
            event.preventDefault();
            stage.focus();
            pointer = { id: event.pointerId, x: event.clientX, y: event.clientY };
            stage.setPointerCapture(event.pointerId);
        });
        stage.addEventListener('pointermove', (event) => {
            if (!pointer || pointer.id !== event.pointerId) return;
            const scale = 320 / stage.getBoundingClientRect().width;
            move(state, (event.clientX - pointer.x) * scale, (event.clientY - pointer.y) * scale);
            pointer.x = event.clientX;
            pointer.y = event.clientY;
            draw();
        });
        for (const name of ['pointerup', 'pointercancel', 'lostpointercapture']) stage.addEventListener(name, () => { pointer = null; });
        stage.addEventListener('keydown', (event) => {
            const keys = { ArrowLeft: [-10, 0], ArrowRight: [10, 0], ArrowUp: [0, -10], ArrowDown: [0, 10] };
            if (!state || !keys[event.key]) return;
            event.preventDefault();
            move(state, ...keys[event.key]);
            draw();
        });
        zoom.addEventListener('input', () => {
            if (!state) return;
            state.zoom = clamp(Number(zoom.value) || 1, 1, 4);
            draw();
        });
        dialog.querySelector('[data-crop-reset]').addEventListener('click', () => {
            if (!state) return;
            state.cx = state.width / 2;
            state.cy = state.height / 2;
            state.zoom = 1;
            zoom.value = '1';
            draw();
        });
        dialog.querySelector('[data-crop-cancel]').addEventListener('click', () => dialog.close());
        dialog.addEventListener('close', () => {
            cleanup();
            editor.querySelector('[data-avatar-editor] summary').focus();
        });
        dialog.querySelector('[data-crop-apply]').addEventListener('click', () => {
            if (!state) return;
            try {
                const crop = constrain(state);
                const output = document.createElement('canvas');
                output.width = output.height = 256;
                const target = output.getContext('2d');
                target.fillStyle = '#ffffff';
                target.fillRect(0, 0, 256, 256);
                target.drawImage(image, crop.x, crop.y, crop.size, crop.size, 0, 0, 256, 256);
                const chosenFile = file;
                const preview = output.toDataURL('image/jpeg', 0.85);
                dialog.close();
                onApply(chosenFile, crop, preview);
            } catch (_) {
                error.textContent = 'Could not apply this crop. Try a different photo.';
            }
        });
        return { open, dispose: cleanup };
    }

    const api = { constrain, move, create, preparePhoto };
    if (typeof module !== 'undefined' && module.exports) module.exports = api;
    else root.AvatarCrop = api;
})(typeof window !== 'undefined' ? window : globalThis);
