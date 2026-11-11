from pathlib import Path


def test_graph_point_exclusion_keeps_value_and_allows_readonly_save(app):
    template, *_ = app.jinja_loader.get_source(
        app.jinja_env, "electrical_intensity/electrical_intensity.html"
    )
    live_save = (
        Path(__file__).resolve().parents[2]
        / "app/static/js/electrical_intensity/live_save.js"
    ).read_text(encoding="utf-8")
    shared_save = (
        Path(__file__).resolve().parents[2]
        / "app/static/js/energy_consumption/consumption_live_save.js"
    ).read_text(encoding="utf-8")

    assert "exclusionRestoreValue" not in template + live_save
    assert 'field.readOnly = checkbox.checked' in live_save
    assert 'live.enqueue(field, true)' in live_save
    assert 'field.readOnly && !allowReadOnly' in shared_save
    assert 'min-width: 4.75rem' in template
    assert 'td.summary-year-cell > .fuel-param-input {' in template
    assert 'td.summary-year-cell > .fuel-param-input[readonly]' in template
    assert 'color: var(--bs-secondary-color, #6c757d)' in template
    assert 'background-color: #e9ecef' in template
