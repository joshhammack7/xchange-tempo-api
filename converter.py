import xml.etree.ElementTree as ET
import json
import io
import os
from pathlib import Path


def convert_xchange_to_tempo_from_bytes(
    xchange_bytes,
    filename,
    video_source=None,
    playname_prefix=None,
    fps_override=None,
):
    """
    Core converter: takes raw XML bytes and returns (output_name, BytesIO) for a .tempo file.

    Design:
      - Tempo prefers filename-only in "Source" (no absolute paths) so files are portable.
      - "RelativeTo": "ClipFolder" tells Tempo to resolve filenames using its clip folder
        / project context, not your local filesystem paths.

    Parameters:
      xchange_bytes: contents of the .xchange file (bytes)
      filename: name of the uploaded .xchange file (e.g. "25 0528 TXNO O vs ALSO.xchange")
      video_source: optional, can be filename ("foo.mp4") or any path; we will keep only
                    the basename (e.g. "foo.mp4")
      playname_prefix: prefix for PlayName; defaults to stem of filename
      fps_override: optional float/str; if not provided we try to read FramesPerSecond
                    from XML; fallback to 59.94
    """
    # Parse XML
    root = ET.fromstring(xchange_bytes)
    stem = Path(filename).stem  # "25 0528 TXNO O vs ALSO"

    # --- FPS handling --------------------------------------------------------
    fps = None

    if fps_override is not None:
        try:
            fps = float(fps_override)
        except (TypeError, ValueError):
            fps = None

    if fps is None:
        fps_elem = root.find(".//FramesPerSecond")
        if fps_elem is not None and fps_elem.text:
            try:
                fps = float(fps_elem.text.strip())
            except ValueError:
                fps = None

    if fps is None:
        # Fallback – adjust if you know your capture is actually 30, 60, etc.
        fps = 59.94

    # --- Playname prefix -----------------------------------------------------
    if playname_prefix is None or playname_prefix.strip() == "":
        playname_prefix = stem

    # --- Determine clip path as Tempo will see it ---------------------------
    # IMPORTANT: Use whatever the user passed as-is (can be a full path or filename).
    if video_source and video_source.strip():
        clip_path = video_source.strip()
    else:
        # Fallback: just the stem + .mp4
        clip_path = f"{stem}.mp4"


    # --- Locate <Plays> ------------------------------------------------------
    plays_parent = root.find("Plays")
    if plays_parent is None:
        raise RuntimeError("Could not find <Plays> section in .xchange file")

    # Keys to pull into PlayData
    play_keys = [
        "FullSequence",
        "PlayNumber",
        "Down",
        "Distance",
        "Yardline",
        "Quarter",
        "Series",
        "SeriesPlay",
        "SeriesEnd",
        "Gain",
        "PlayType",
        "BallCarrierJerseyNumber",
        "PassResult",
        "PenaltyType",
        "PenaltyYards",
        "PenaltyJerseyNum",
        "TacklerJerseyNum",
    ]

    plays_out = []

    # --- Iterate plays -------------------------------------------------------
    for play_elem in plays_parent.findall("Play"):
        pn_txt = (play_elem.findtext("PlayNumber", "0") or "").strip()
        try:
            pn = int(pn_txt)
        except ValueError:
            pn = 0

        playdata = {
            key: (play_elem.findtext(key, "") or "").strip()
            for key in play_keys
        }

        views_json = []
        views_elem = play_elem.find("Views")
        if views_elem is not None:
            for view in views_elem.findall("View"):
                markin_txt = (view.findtext("MarkIn", "0") or "0").strip()
                dur_txt = (view.findtext("Duration", "0") or "0").strip()
                cam = (view.findtext("CameraView", "") or "").strip()

                try:
                    markin = float(markin_txt)
                except ValueError:
                    markin = 0.0
                try:
                    duration = float(dur_txt)
                except ValueError:
                    duration = 0.0

                # Convert frames to seconds
                in_point = markin / fps
                out_point = (markin + duration - 1) / fps if duration > 0 else in_point

                views_json.append(
                    {
                        # IMPORTANT: filename only so Tempo can resolve it
                        # using ClipFolder / project context.
                        "Source": clip_path,
                        "InPoint": in_point,
                        "OutPoint": out_point,
                        "Camera": cam,
                    }
                )

        plays_out.append(
            {
                "PlayNumber": pn,
                "PlayName": f"{playname_prefix}.{pn:03d}",
                "Views": views_json,
                "PlayData": playdata,
            }
        )

    # Sort plays just to be safe
    plays_out.sort(key=lambda p: p["PlayNumber"])

    # --- Final Tempo JSON object --------------------------------------------
    tempo_obj = {
        "FileVersion": 1,
        "Plays": plays_out,
    }


    tempo_bytes = json.dumps(tempo_obj, indent=2).encode("utf-8")
    buf = io.BytesIO(tempo_bytes)
    buf.seek(0)

    out_name = stem + ".tempo"
    return out_name, buf


def convert_xchange_to_tempo(
    xchange_path,
    tempo_path,
    video_source=None,
    playname_prefix=None,
    fps_override=None,
):
    """
    Backward-compatible wrapper that works with your original CLI-style function.

    Reads the .xchange file from disk, calls convert_xchange_to_tempo_from_bytes,
    and writes the resulting .tempo file to tempo_path.
    """
    xchange_path = Path(xchange_path)
    tempo_path = Path(tempo_path)

    with xchange_path.open("rb") as f:
        xchange_bytes = f.read()

    out_name, buf = convert_xchange_to_tempo_from_bytes(
        xchange_bytes=xchange_bytes,
        filename=xchange_path.name,
        video_source=video_source,
        playname_prefix=playname_prefix,
        fps_override=fps_override,
    )

    tempo_path.write_bytes(buf.getvalue())
