/*
 * Declarative event handlers, so pages need no inline on*="" attributes
 * (which the Content-Security-Policy forbids):
 *   data-action="fn" data-args='["a", 1]'  click: calls window.fn("a", 1) (dotted paths allowed)
 *   data-submit="fn"                        form submit: calls fn(event)
 *   data-input="fn"                         input: calls fn(event)
 *   data-confirm="Sure?"                    click (or form submit): asks first, cancels on No
 *   data-autosubmit                         change: submits the field's form
 */
(function () {
    "use strict";

    function call(path, args, event) {
        const parts = path.split(".");
        const owner = parts.slice(0, -1).reduce((obj, key) => (obj ? obj[key] : undefined), window);
        const fn = (owner || window)[parts[parts.length - 1]];
        if (typeof fn !== "function") {
            console.warn("No handler", path);
            return;
        }
        return fn.apply(owner || window, args === undefined ? [event] : args);
    }

    document.addEventListener("click", (event) => {
        const confirmEl = event.target.closest("[data-confirm]:not(form)");
        if (confirmEl && !window.confirm(confirmEl.dataset.confirm)) {
            event.preventDefault();
            event.stopImmediatePropagation();
            return;
        }
        const el = event.target.closest("[data-action]");
        if (!el || el.disabled) return;
        call(el.dataset.action, el.dataset.args ? JSON.parse(el.dataset.args) : [], event);
    });

    document.addEventListener("submit", (event) => {
        const form = event.target;
        if (form.dataset.confirm && !window.confirm(form.dataset.confirm)) {
            event.preventDefault();
            return;
        }
        if (form.dataset.submit) call(form.dataset.submit, undefined, event);
    });

    document.addEventListener("input", (event) => {
        const el = event.target.closest("[data-input]");
        if (el) call(el.dataset.input, undefined, event);
    });

    document.addEventListener("change", (event) => {
        if (event.target.matches("[data-autosubmit]") && event.target.form) event.target.form.submit();
    });
})();
