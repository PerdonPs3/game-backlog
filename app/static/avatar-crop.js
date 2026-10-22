(function (root) {
    const clamp = (value, min, max) => Math.max(min, Math.min(max, value));

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
            if (!['image/jpeg', 'image/png', 'image/webp'].includes(candidate.type) || candidate.size > 2 * 1024 * 1024) {
                report('Choose a JPG, PNG, or WebP photo up to 2 MB.');
                return;
            }
            let candidateUrl;
            try {
                candidateUrl = URL.createObjectURL(candidate);
                const loaded = new Image();
                loaded.src = candidateUrl;
                await loaded.decode();
                if (current !== generation) { URL.revokeObjectURL(candidateUrl); return; }
                if (!loaded.naturalWidth || !loaded.naturalHeight || loaded.naturalWidth * loaded.naturalHeight > 12000000) throw new Error();
                if (url) URL.revokeObjectURL(url);
                url = candidateUrl;
                image = loaded;
                file = candidate;
                pointer = null;
                state = { width: loaded.naturalWidth, height: loaded.naturalHeight, zoom: 1, cx: loaded.naturalWidth / 2, cy: loaded.naturalHeight / 2 };
                zoom.value = '1';
                error.textContent = '';
                status.textContent = '';
                apply.disabled = false;
                draw();
                stage.focus();
            } catch (_) {
                URL.revokeObjectURL(candidateUrl);
                if (current !== generation) return;
                report('This photo could not be opened. Use a still JPG, PNG, or WebP up to 12 million pixels.');
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

    const api = { constrain, move, create };
    if (typeof module !== 'undefined' && module.exports) module.exports = api;
    else root.AvatarCrop = api;
})(typeof window !== 'undefined' ? window : globalThis);
