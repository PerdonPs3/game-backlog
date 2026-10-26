"use strict";

(() => {
    const scene = document.querySelector(".entry-map-room");
    const header = document.querySelector(".workspace-site-header");
    if (!scene || !header) return;

    const alignScene = () => {
        scene.style.setProperty("--entry-header-height", `${header.getBoundingClientRect().height}px`);
    };
    alignScene();
    if (typeof ResizeObserver === "function") {
        new ResizeObserver(alignScene).observe(header);
    } else {
        window.addEventListener("resize", alignScene);
    }
})();
