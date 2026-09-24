(function () {
  var LIVE_FIELDS = ["emin", "emax", "ecur", "h", "ecurdis", "hdis", "etp", "kobl"];

  function restrictionsOn() {
    var ar = document.getElementById("apply_restrictions");
    return !!(ar && ar.checked);
  }

  function setBusy(busy) {
    document.querySelectorAll(
      "#runDistributionForm button, #nrHfixApplyForm button, #nrHfixSkipForm button, .fuel-calc-stage-buttons button[type='submit']"
    ).forEach(function (btn) {
      if (busy) {
        if (!btn.hasAttribute("data-live-prev-disabled")) {
          btn.setAttribute("data-live-prev-disabled", btn.disabled ? "1" : "0");
        }
        btn.disabled = true;
        return;
      }
      btn.disabled = btn.getAttribute("data-live-prev-disabled") === "1";
      btn.removeAttribute("data-live-prev-disabled");
    });
  }

  function flashCell(td) {
    if (!td) return;
    td.classList.remove("fuel-restr-flash");
    void td.offsetWidth;
    td.classList.add("fuel-restr-flash");
    window.setTimeout(function () {
      td.classList.remove("fuel-restr-flash");
    }, 800);
  }

  function applyRow(tr, row) {
    LIVE_FIELDS.forEach(function (field) {
      var cell = tr.querySelector('[data-live-field="' + field + '"]');
      var payload = row[field];
      if (!cell || !payload) return;
      var next = payload.text || "—";
      if (cell.textContent.trim() !== next) {
        cell.textContent = next;
        flashCell(cell);
      }
    });
  }

  function applyTotals(event) {
    var totals = event.totals;
    if (!totals) return;
    ["ecur", "ecurdis", "etp"].forEach(function (field) {
      var cell = document.querySelector('#fuelCalcRestrictionsTable [data-total-field="' + field + '"]');
      var payload = totals[field];
      if (!cell || !payload) return;
      var next = payload.text || "—";
      if (cell.textContent.trim() !== next) {
        cell.textContent = next;
        flashCell(cell);
      }
    });
  }

  function applySnapshot(event) {
    var table = document.getElementById("fuelCalcRestrictionsTable");
    if (!table || !event.rows) return;
    event.rows.forEach(function (row) {
      if (row.id == null) return;
      var tr = table.querySelector('tr[data-restriction-id="' + row.id + '"]');
      if (tr) applyRow(tr, row);
    });
    applyTotals(event);
    var kCell = document.querySelector('[data-dp-live="k"]');
    var knCell = document.querySelector('[data-dp-live="kn"]');
    if (kCell && event.k && event.k.text) {
      if (kCell.textContent.trim() !== event.k.text) {
        kCell.textContent = event.k.text;
        flashCell(kCell);
      }
    }
    if (knCell && event.kn && event.kn.text) {
      if (knCell.textContent.trim() !== event.kn.text) {
        knCell.textContent = event.kn.text;
        flashCell(knCell);
      }
    }
    var status = document.getElementById("fuelCalcRestrictionsLiveStatus");
    if (status) {
      status.hidden = false;
      if (event.type === "start") {
        status.textContent = "старт · k=" + ((event.k && event.k.text) || "—");
      } else if (event.type === "pass") {
        status.textContent =
          "проход " + event.outer + " / " + event.outer_max +
          " · k=" + ((event.k && event.k.text) || "—") +
          " · ΣE=" + ((event.sum_e && event.sum_e.text) || "—");
      }
    }
  }

  function showBanner(message, level) {
    var host = document.getElementById("fuelCalcRestrictionsLive");
    if (!host || !message) return;
    var old = document.getElementById("fuelCalcRestrictionsLiveBanner");
    if (old) old.remove();
    var div = document.createElement("div");
    div.id = "fuelCalcRestrictionsLiveBanner";
    div.className = "alert alert-" + (level === "danger" ? "danger" : level === "warning" ? "warning" : "success") + " mt-2 mb-0 py-2 small";
    div.setAttribute("role", "status");
    div.textContent = message;
    host.parentNode.insertBefore(div, host.nextSibling);
  }

  function applyDone(event) {
    var limCell = document.querySelector('[data-dp-live="lim"]');
    if (limCell) {
      limCell.textContent = "да";
      flashCell(limCell);
    }
    var status = document.getElementById("fuelCalcRestrictionsLiveStatus");
    if (status && event.result) {
      status.hidden = false;
      status.textContent =
        "готово · проходов " + (event.result.restriction_outer_iterations || "—") +
        " · k=" + (event.result.final_k || "—");
    }
    var text = event.message || "";
    if (event.composite_warning) {
      text = text ? text + " " + event.composite_warning : event.composite_warning;
    }
    showBanner(text, event.composite_warning ? "warning" : event.level);
  }

  async function runLive(form) {
    var body = new FormData(form);
    body.set("live", "1");
    var csrf = form.querySelector('[name="csrf_token"]');
    var headers = { Accept: "application/x-ndjson" };
    if (csrf && csrf.value) headers["X-CSRF-Token"] = csrf.value;
    setBusy(true);
    try {
      var response = await fetch(form.action, {
        method: "POST",
        body: body,
        headers: headers,
        credentials: "same-origin",
      });
      var ctype = (response.headers.get("content-type") || "").toLowerCase();
      if (ctype.indexOf("application/json") !== -1 && ctype.indexOf("ndjson") === -1) {
        var paused = await response.json();
        if (paused && paused.type === "paused_nr_hfix") {
          window.location.reload();
          return;
        }
        throw new Error((paused && paused.message) || "Ошибка Распреда");
      }
      if (!response.ok || !response.body) {
        throw new Error("Ошибка Распреда");
      }
      var reader = response.body.getReader();
      var decoder = new TextDecoder("utf-8");
      var buf = "";
      while (true) {
        var chunk = await reader.read();
        if (chunk.done) break;
        buf += decoder.decode(chunk.value, { stream: true });
        var lines = buf.split("\n");
        buf = lines.pop() || "";
        for (var i = 0; i < lines.length; i += 1) {
          var line = lines[i].trim();
          if (!line) continue;
          var event = JSON.parse(line);
          if (event.type === "paused_nr_hfix") {
            window.location.reload();
            return;
          }
          if (event.type === "error") {
            throw new Error(event.message || "Ошибка Распреда");
          }
          if (event.type === "start" || event.type === "pass") {
            applySnapshot(event);
          }
          if (event.type === "done") {
            applyDone(event);
          }
        }
      }
    } catch (err) {
      showBanner(err.message || String(err), "danger");
    } finally {
      setBusy(false);
    }
  }

  function intercept(form) {
    if (!form) return;
    form.addEventListener("submit", function (ev) {
      if (!restrictionsOn()) return;
      if (!document.getElementById("fuelCalcRestrictionsTable")) return;
      ev.preventDefault();
      runLive(form);
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    intercept(document.getElementById("runDistributionForm"));
    intercept(document.getElementById("nrHfixApplyForm"));
    intercept(document.getElementById("nrHfixSkipForm"));
  });
})();
