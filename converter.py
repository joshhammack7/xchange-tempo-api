import xml.etree.ElementTree as ET
import json
from pathlib import Path


def convert_xchange_to_tempo(
    xchange_path,
    output_path,
    video_source=None,
    playname_prefix=None,
    fps_override=None,
):
    """
    Core converter, same behavior as your working local script.
    xchange_path: Path to .xchange file
    output_path: Path to write .tempo file
    video_source: video path string (required in practice)
    playname_prefix: optional prefix for PlayName
    fps_override: optional float FPS; if None, use XML's FramesPerSecond
    """
    xchange_path = Path(xchange_path)
    output_path = Path(output_path)

    # Parse XML
    tree = ET.parse(xchange_path)
    root = tree.getroot()
    stem = xchange_path.stem

    # --- FPS handling ---
    fps = None
    if fps_override is not None:
        try:
            fps = float(fps_override)
        except ValueError:
            fps = None

    if fps is None:
        fps_elem = root.find(".//FramesPerSecond")
        if fps_elem is not None and fps_elem.text:
            try:
                fps = float(fps_elem.text.strip())
            except ValueError:
                fps = None

    if fps is None:
        fps = 59.94  # fallback – matches what worked for you

    # Defaults
    if not playname_prefix:
        playname_prefix = stem

    if not video_source:
        video_source = stem + ".mp4"

    plays_parent = root.find("Plays")
    if plays_parent is None:
        raise RuntimeError("Could not find <Plays> section in .xchange file")

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

    for play_elem in plays_parent.findall("Play"):
        pn_txt = (play_elem.findtext("PlayNumber", "0") or "").strip()
        try:
            pn = int(pn_txt)
        except ValueError:
            pn = 0

        playdata = {}
        for key in play_keys:
            val = play_elem.findtext(key, "")
            playdata[key] = (val or "").strip()

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

                in_point = markin / fps
                out_point = (markin + duration - 1) / fps if duration > 0 else in_point

                views_json.append(
                    {
                        "Source": str(video_source),
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

    plays_out.sort(key=lambda p: p["PlayNumber"])

    tempo_obj = {
    "FileVersion": 1,
    "RelativeTo": "ClipFolder",
    "Plays": plays_out
}


    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(tempo_obj, f, indent=2)
