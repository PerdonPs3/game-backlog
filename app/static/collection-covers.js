"use strict";

(() => {
    function bindCoverFallbacks() {
        document.querySelectorAll(".game-card-cover img").forEach((image) => {
            if (!image.dataset.fallbackBound) {
                image.addEventListener("error", () => image.remove());
                image.dataset.fallbackBound = "true";
            }
            // Cached images can fail before the deferred script runs.
            if (image.complete && image.naturalWidth === 0) image.remove();
        });
    }
    bindCoverFallbacks();
    document.addEventListener("collection:updated", bindCoverFallbacks);
})();
