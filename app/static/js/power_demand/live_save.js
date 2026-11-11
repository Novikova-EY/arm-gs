(function () {
    "use strict";

    // Последовательные запросы позволяют отделить свои commit от изменений других вкладок.
    let queue = Promise.resolve();
    window.powerDemandSaveFetch = function (url, options) {
        const request = queue.then(async function () {
            document.dispatchEvent(new CustomEvent("module-data:saving", {detail: {active: true}}));
            try {
                const response = await fetch(url, options);
                if (response.ok) {
                    const data = await response.clone().json().catch(function () { return null; });
                    const before = response.headers.get("X-Power-Demand-Revision-Before");
                    const revision = response.headers.get("X-Power-Demand-Revision");
                    if (data && data.ok && before && revision) {
                        document.dispatchEvent(new CustomEvent("module-data:saved", {
                            detail: {before: before, revision: revision}
                        }));
                    }
                }
                return response;
            } finally {
                document.dispatchEvent(new CustomEvent("module-data:saving", {detail: {active: false}}));
            }
        });
        queue = request.catch(function () {});
        return request;
    };
}());
