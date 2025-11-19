from flask import Flask, request, send_file, jsonify
from flask_cors import CORS
import io


from converter import convert_xchange_to_tempo_from_bytes

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

    try:
        # Read the uploaded .xchange into memory
        xchange_bytes = file.read()

        # Call the new bytes-based converter
        out_name, buf = convert_xchange_to_tempo_from_bytes(
            xchange_bytes=xchange_bytes,
            filename=file.filename,
            video_source=video_source,
            playname_prefix=playname_prefix,
            fps_override=fps_override,
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    # buf is already a BytesIO positioned at start from the converter
    return send_file(
        buf,
        as_attachment=True,
        download_name=out_name,
        mimetype="application/json",
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
