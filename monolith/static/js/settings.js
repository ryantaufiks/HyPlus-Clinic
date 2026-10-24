/* Settings home: filter the module cards as you type. */
(function () {
    "use strict";
    const input = document.getElementById("module-search");
    if (!input) return;
    const groups = [...document.querySelectorAll(".module-group")];
    const empty = document.getElementById("module-empty");
    input.addEventListener("input", () => {
        const words = input.value.toLowerCase().split(/\s+/).filter(Boolean);
        let shown = 0;
        groups.forEach((group) => {
            let inGroup = 0;
            group.querySelectorAll("[data-module]").forEach((card) => {
                const match = words.every((w) => card.dataset.module.includes(w));
                card.hidden = !match;
                if (match) inGroup++;
            });
            group.hidden = inGroup === 0;
            shown += inGroup;
        });
        empty.classList.toggle("d-none", shown > 0);
    });
})();
