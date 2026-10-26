"""Interface local para cadastro e verificações manuais de destinos autorizados."""
import os
import secrets
from pathlib import Path

from flask import Flask, abort, flash, redirect, render_template, request, session, url_for
import database
from monitor import check_connectivity


def create_app(config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("NETMONITOR_SECRET_KEY") or secrets.token_hex(32),
        DATABASE=str(Path(app.instance_path) / "netmonitor.sqlite3"),
        MAX_CONTENT_LENGTH=16 * 1024,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Strict",
        TRUSTED_HOSTS=["localhost", "127.0.0.1", "[::1]"],
    )
    if config:
        app.config.update(config)
    database.init_db(app.config["DATABASE"])

    def db_path():
        return app.config["DATABASE"]

    def device_or_404(device_id):
        device = database.get_device(db_path(), device_id)
        if device is None:
            abort(404, description="Dispositivo não encontrado.")
        return device

    @app.before_request
    def csrf_protect():
        if request.method in ("POST", "PUT", "PATCH", "DELETE"):
            expected = session.get("csrf_token")
            received = request.form.get("csrf_token", "")
            if not expected or not secrets.compare_digest(expected.encode("utf-8"), received.encode("utf-8")):
                abort(400, description="Token CSRF inválido. Recarregue a página e tente novamente.")

    @app.context_processor
    def template_helpers():
        if "csrf_token" not in session:
            session["csrf_token"] = secrets.token_hex(32)
        return {"csrf_token": session["csrf_token"]}

    @app.get("/")
    def index():
        devices = database.list_devices(db_path())
        latest = {d["id"]: database.get_history(db_path(), d["id"], 1) for d in devices}
        return render_template("index.html", devices=devices, latest=latest)

    @app.route("/devices/new", methods=["GET", "POST"])
    @app.route("/devices/<int:device_id>/edit", methods=["GET", "POST"])
    def device_form(device_id=None):
        device = device_or_404(device_id) if device_id is not None else None
        if request.method == "POST":
            try:
                database.save_device(db_path(), request.form.get("name", ""),
                    request.form.get("address", ""), request.form.get("device_type", ""),
                    request.form.get("description", ""), device_id)
            except ValueError as exc:
                return render_template("device_form.html", device=request.form,
                    types=database.DEVICE_TYPES, error=str(exc)), 400
            flash("Dispositivo salvo.")
            return redirect(url_for("index"))
        return render_template("device_form.html", device=device, types=database.DEVICE_TYPES)

    @app.route("/devices/<int:device_id>/delete", methods=["GET", "POST"])
    def delete(device_id):
        device = device_or_404(device_id)
        if request.method == "POST":
            if request.form.get("confirm") != "yes":
                abort(400, description="Confirme a exclusão do dispositivo e seu histórico.")
            database.delete_device(db_path(), device_id)
            flash("Dispositivo e histórico excluídos.")
            return redirect(url_for("index"))
        return render_template("delete.html", device=device)

    @app.post("/devices/<int:device_id>/check")
    def check(device_id):
        device = device_or_404(device_id)
        result = check_connectivity(device["address"])
        database.record_check(db_path(), device_id, result)
        flash("Verificação registrada: " + result["status"])
        return redirect(url_for("index"))

    @app.get("/devices/<int:device_id>/history")
    def history(device_id):
        device = device_or_404(device_id)
        return render_template("history.html", device=device,
            checks=database.get_history(db_path(), device_id))

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
