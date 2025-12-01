from flask import Blueprint, current_app, jsonify, request, send_from_directory
import os

exports_bp = Blueprint("exports_bp", __name__)


def _get_queue():
    redis_url = current_app.config.get("REDIS_URL", "redis://localhost:6379/0")
    try:
        # Ленивая загрузка, чтобы не требовать rq/redis при старте приложения
        import redis  # type: ignore
        from rq import Queue  # type: ignore
        connection = redis.from_url(redis_url)
        return Queue("exports", connection=connection)
    except Exception as e:
        current_app.logger.error(f"RQ init failed or not installed: {e}")
        return None


@exports_bp.route("/exports/start", methods=["POST"])
def start_export():
    q = _get_queue()
    filters = request.get_json(silent=True) or {}
    if q is None:
        # Фолбэк: синхронно (не блокируем UI за счёт коротких данных)
        from app.exports.tasks import run_export_task
        resp = run_export_task(filters)
        files = resp.get("files", [])
        urls = [
            request.host_url.rstrip('/') + current_app.url_for("exports_bp.download_export", filename=f)
            for f in files
        ]
        return jsonify({"status": "finished", **resp, "urls": urls})

    from app.exports.tasks import run_export_task
    job = q.enqueue(run_export_task, filters, job_timeout=60 * 30)  # до 30 минут
    return jsonify({"status": "queued", "job_id": job.get_id()}), 202


@exports_bp.route("/exports/status/<job_id>", methods=["GET"])
def export_status(job_id: str):
    q = _get_queue()
    if q is None:
        return jsonify({"status": "unknown"}), 400

    job = q.fetch_job(job_id)
    if job is None:
        return jsonify({"status": "not_found"}), 404

    try:
        job.refresh()
    except Exception:
        pass

    if job.is_queued:
        return jsonify({"status": "queued"})
    if job.is_started:
        return jsonify({"status": "started"})
    if job.is_failed:
        return jsonify({"status": "failed", "error": str(job.exc_info)})

    # Завершено
    result = job.result or {}
    files = result.get("files", [])
    urls = [request.host_url.rstrip('/') + current_app.url_for("exports_bp.download_export", filename=f) for f in files]
    return jsonify({"status": "finished", "files": files, "urls": urls})


@exports_bp.route("/exports/download/<path:filename>", methods=["GET"])
def download_export(filename: str):
    exports_dir = current_app.config.get("EXPORTS_DIR") or os.path.join(current_app.instance_path, "exports")
    return send_from_directory(directory=exports_dir, path=filename, as_attachment=True)


