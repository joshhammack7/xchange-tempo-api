from flask import Flask, request, send_file, jsonify
from flask_cors import CORS
from pathlib import Path
import io
import tempfile

from converter import convert_xchange_to_tempo  # reuse your working logic

app = Flask(__name__)
CORS(app)  # you can restrict origins later if needed


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


@app.route("/convert", methods=["POST"])
def convert():
    """
    Expects multipart/form-data:
      - xchange_file: file (required)
      - video_source: string (required in practice)
      - playname_prefix: string (optional)
      - fps: float (optional, e.g. 59.94 or 30)
    Returns: .tempo file as attachment
    """
    if "xchange_file" not in request.files:
        return jsonify({"error": "xchange_file is required"}), 400

    file = request.files["xchange_file"]
    if file.filename == "":
        return jsonify({"error": "empty filename"}), 400

    video_source = request.form.get("video_source") or ""
    playname_prefix = request.form.get("playname_prefix") or None
    fps_text = request.form.get("fps") or ""
    fps_override = None

    if not video_source:
        return jsonify({"error": "video_source is required"}), 400

    if fps_text:
        try:
            fps_override = float(fps_text)
        except ValueError:
            return jsonify({"error": "fps must be numeric"}), 400

    upload_name = Path(file.filename).name

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        xchange_path = tmpdir / upload_name
        tempo_path = tmpdir / (Path(upload_name).with_suffix(".tempo").name)

        file.save(xchange_path)

        try:
            convert_xchange_to_tempo(
                xchange_path,
                tempo_path,
                video_source=video_source,
                playname_prefix=playname_prefix,
                fps_override=fps_override,
            )
        except Exception as e:
            return jsonify({"error": str(e)}), 500

        data = tempo_path.read_bytes()
        buf = io.BytesIO(data)
        buf.seek(0)

    return send_file(
        buf,
        as_attachment=True,
        download_name=tempo_path.name,
        mimetype="application/json",
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
