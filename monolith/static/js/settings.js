/* Settings home: filter the module cards as you type, and sort them. */
(function () {
    "use strict";
    const input = document.getElementById("module-search");
    const sort = document.getElementById("module-sort");
    if (!input || !sort) return;
    const sorted = document.getElementById("module-sorted");
    const sortedGrid = sorted.querySelector(".module-grid");
    const groups = [...document.querySelectorAll(".module-group")].filter((g) => g !== sorted);
    const empty = document.getElementById("module-empty");
    // Remember where every card lives so "Sort by group" can put it back.
    const cards = [...document.querySelectorAll("[data-module]")].map((el, i) => ({ el, home: el.parentElement, i }));
    const STORE = "hyplus.settingsSort";

    const byName = (a, b) => a.el.dataset.title.localeCompare(b.el.dataset.title);
    const ORDER = {
        az: byName,
        za: (a, b) => byName(b, a),
        // Pending items first (most first), then modules still to set up, then the rest; coming soon last.
        attention: (a, b) => (Number(b.el.dataset.badge) - Number(a.el.dataset.badge))
            || ("warn" in b.el.dataset) - ("warn" in a.el.dataset)
            || ("soon" in a.el.dataset) - ("soon" in b.el.dataset) || byName(a, b),
    };

    function arrange() {
        const order = ORDER[sort.value];
        if (order) {
            [...cards].sort(order).forEach((c) => sortedGrid.appendChild(c.el));
        } else {
            cards.forEach((c) => c.home.appendChild(c.el));  // original order: cards were collected in it
        }
        filter();
    }

    function filter() {
        const words = input.value.toLowerCase().split(/\s+/).filter(Boolean);
        const flat = sort.value in ORDER;
        let shown = 0;
        cards.forEach((c) => {
            c.el.hidden = !words.every((w) => c.el.dataset.module.includes(w));
            if (!c.el.hidden) shown++;
        });
        groups.forEach((g) => { g.hidden = flat || !g.querySelector("[data-module]:not([hidden])"); });
        sorted.hidden = !flat || shown === 0;
        empty.classList.toggle("d-none", shown > 0);
    }

    try { const saved = localStorage.getItem(STORE); if (saved && [...sort.options].some((o) => o.value === saved)) sort.value = saved; } catch (e) { /* storage blocked */ }
    input.addEventListener("input", filter);
    sort.addEventListener("change", () => {
        try { localStorage.setItem(STORE, sort.value); } catch (e) { /* storage blocked */ }
        arrange();
    });
    arrange();
})();
