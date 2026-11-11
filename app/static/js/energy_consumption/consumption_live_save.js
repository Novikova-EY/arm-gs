(function () {
    "use strict";

    window.bindConsumptionLiveSave = function (root, selector, save) {
        const pending = new Set();
        const failed = new Set();
        let running = false;
        let active = null;
        const revisions = new WeakMap();
        let idle = Promise.resolve();

        function mark(field, state, message) {
            field.classList.remove("is-save-success", "is-save-error");
            if (state) field.classList.add(state);
            if (message) {
                field.setAttribute("aria-invalid", "true");
                if (!field.dataset.saveError) field.dataset.saveOriginalTitle = field.title || "";
                field.dataset.saveError = message;
                field.title = message;
            } else {
                field.removeAttribute("aria-invalid");
                if (field.dataset.saveError) {
                    field.title = field.dataset.saveOriginalTitle;
                    delete field.dataset.saveOriginalTitle;
                    delete field.dataset.saveError;
                }
            }
        }

        async function drain() {
            running = true;
            try {
                while (pending.size) {
                    const field = pending.values().next().value;
                    pending.delete(field);
                    if (!field.isConnected) continue;
                    active = field;
                    mark(field, "");
                    field.setAttribute("aria-busy", "true");
                    const revision = revisions.get(field);
                    try {
                        await save(field);
                        failed.delete(field);
                        if (!pending.has(field) && revisions.get(field) === revision) mark(field, "is-save-success");
                    } catch (error) {
                        failed.add(field);
                        mark(field, "is-save-error", error.message || "Не удалось сохранить данные.");
                    } finally {
                        field.removeAttribute("aria-busy");
                        active = null;
                    }
                }
            } finally {
                running = false;
            }
        }

        function enqueue(field, allowReadOnly) {
            if (!field || field.disabled || (field.readOnly && !allowReadOnly)) return idle;
            pending.add(field);
            mark(field, "");
            if (!running) idle = drain();
            return idle;
        }

        root.addEventListener("change", function (event) {
            if (event.target.matches(selector)) enqueue(event.target);
        });
        root.addEventListener("input", function (event) {
            if (event.target.matches(selector)) {
                revisions.set(event.target, (revisions.get(event.target) || 0) + 1);
                mark(event.target, "");
            }
        });
        root.addEventListener("keydown", function (event) {
            if (event.key !== "Enter" || event.repeat || !event.target.matches(selector)) return;
            if (event.target.tagName === "TEXTAREA" && !event.ctrlKey) return;
            event.preventDefault();
            enqueue(event.target);
        });
        window.addEventListener("beforeunload", function (event) {
            const dirty = Array.from(root.querySelectorAll(selector)).some(function (field) {
                return !field.disabled && !field.readOnly && (field.type === "checkbox"
                    ? field.checked : field.value !== (field.dataset.initial || ""));
            });
            const errors = Array.from(failed).some(function (field) { return field.isConnected; });
            if (active || pending.size || errors || dirty) {
                event.preventDefault();
                event.returnValue = "";
            }
        });
        return { enqueue: enqueue, whenIdle: function () { return idle; } };
    };
})();
