"""
Iterative preview/inspection helper for combo_graph_animation.py.

Purpose
-------
Render a scene FAST (low quality), then extract evenly-spaced frames and tile
them into a single "contact sheet" PNG. Inspecting one image reveals the whole
timeline at a glance: overlapping labels, off-screen nodes, crossing arrows,
empty dead-time, colour clashes, etc. Fix the code, re-run, re-inspect.

Usage (from repo root, Windows)
-------------------------------
    docs/.venv-manim/Scripts/python.exe docs/preview_scene.py Scene01_GraphOverview
    docs/.venv-manim/Scripts/python.exe docs/preview_scene.py Scene02_DownPhaseDFS --cols 5 --rows 4
    docs/.venv-manim/Scripts/python.exe docs/preview_scene.py --all          # contact sheet per scene
    docs/.venv-manim/Scripts/python.exe docs/preview_scene.py Scene01_GraphOverview --quality h --final  # high-q final render

Output
------
    docs/media/inspect/<Scene>_sheet.png   <- the contact sheet to Read
    docs/media/inspect/<Scene>_frames/     <- the raw sampled frames
plus the normal manim mp4 under docs/media/videos/...
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

DOCS_DIR = Path(__file__).resolve().parent
SCRIPT = DOCS_DIR / "combo_graph_animation.py"
PYTHON = sys.executable
INSPECT_DIR = DOCS_DIR / "media" / "inspect"

QUALITY_FLAG = {"l": "-ql", "m": "-qm", "h": "-qh", "k": "-qk"}
QUALITY_DIR = {"l": "480p15", "m": "720p30", "h": "1080p60", "k": "2160p60"}

# All authored scenes, in narrative order.
SCENES = [
    "Scene00_Title",
    "Scene01_GraphOverview",
    "Scene02_DownPhaseDFS",
    "Scene03_VariantSetsGeometric",
    "Scene04_MinimalSets",
    "Scene04b_TwoFeatureMerge",
    "Scene05_UpPhase",
    "Scene06_DownVsUp",
]


def run(cmd: list[str]) -> None:
    print("»", " ".join(str(c) for c in cmd))
    subprocess.run(cmd, check=True)


def probe_duration(video: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(video)],
        capture_output=True, text=True, check=True,
    )
    return float(out.stdout.strip())


def render(scene: str, quality: str) -> Path:
    """Render one scene, return the produced mp4 path."""
    flag = QUALITY_FLAG[quality]
    media_dir = DOCS_DIR / "media"
    # --media_dir pins output next to the script no matter the CWD (manim
    # otherwise writes ./media relative to the working directory, which silently
    # leaves you inspecting a stale render elsewhere).
    # --disable_caching is essential for an iterate loop: manim otherwise reuses
    # cached partial-movie files and can render stale frames after an edit.
    run([PYTHON, "-m", "manim", flag, "--disable_caching",
         "--media_dir", str(media_dir), str(SCRIPT), scene])
    qdir = QUALITY_DIR[quality]
    video = media_dir / "videos" / SCRIPT.stem / qdir / f"{scene}.mp4"
    if not video.exists():
        raise FileNotFoundError(f"expected render at {video}")
    return video


def contact_sheet(scene: str, video: Path, cols: int, rows: int) -> Path:
    n = cols * rows
    dur = probe_duration(video)
    frames_dir = INSPECT_DIR / f"{scene}_frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    for f in frames_dir.glob("*.png"):
        f.unlink()

    # Sample n frames evenly across (0.02 .. 0.98) of the duration so we skip
    # the very first/last blank frames.
    stamps = [dur * (0.02 + 0.96 * i / (n - 1)) for i in range(n)] if n > 1 else [dur / 2]
    frame_paths: list[Path] = []
    for i, t in enumerate(stamps):
        fp = frames_dir / f"f{i:02d}.png"
        run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{t:.3f}",
             "-i", str(video), "-frames:v", "1", "-vf", "scale=480:-1", str(fp)])
        frame_paths.append(fp)

    # Tile into a single sheet with a light border between frames.
    sheet = INSPECT_DIR / f"{scene}_sheet.png"
    inputs: list[str] = []
    for fp in frame_paths:
        inputs += ["-i", str(fp)]
    filtergraph = (
        "".join(f"[{i}]drawtext=text='{i}':x=6:y=6:fontsize=22:fontcolor=yellow:"
                f"box=1:boxcolor=black@0.6:boxborderw=4[l{i}];" for i in range(n))
        + "".join(f"[l{i}]" for i in range(n))
        + f"xstack=inputs={n}:layout={_xstack_layout(cols, rows)}[out]"
    )
    run(["ffmpeg", "-y", "-loglevel", "error", *inputs,
         "-filter_complex", filtergraph, "-map", "[out]", str(sheet)])
    print(f"\n== contact sheet: {sheet}  ({dur:.1f}s, {n} frames) ==")
    return sheet


def concat(quality: str) -> Path:
    """Stitch every scene mp4 (in narrative order) into one final film."""
    qdir = QUALITY_DIR[quality]
    vids_dir = DOCS_DIR / "media" / "videos" / SCRIPT.stem / qdir
    parts = [vids_dir / f"{s}.mp4" for s in SCENES]
    missing = [p for p in parts if not p.exists()]
    if missing:
        raise FileNotFoundError(f"render these first: {[p.name for p in missing]}")

    listfile = DOCS_DIR / "media" / "_concat_list.txt"
    listfile.write_text("".join(f"file '{p.as_posix()}'\n" for p in parts))
    out = DOCS_DIR / "combo_graph_explained.mp4"
    # Re-encode (not -c copy) so a uniform stream survives any per-scene quirk.
    run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
         "-i", str(listfile), "-c:v", "libx264", "-pix_fmt", "yuv420p",
         "-crf", "18", "-preset", "medium", str(out)])
    print(f"\n== final film: {out} ==")
    return out


def _xstack_layout(cols: int, rows: int) -> str:
    # xstack layout string: per-input x|y using tile width/height tokens.
    cells = []
    for idx in range(cols * rows):
        r, c = divmod(idx, cols)
        x = "0" if c == 0 else "+".join(f"w{j}" for j in range(c))
        y = "0" if r == 0 else "+".join(f"h{j * cols}" for j in range(r))
        cells.append(f"{x}_{y}")
    return "|".join(cells)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("scene", nargs="?", help="scene class name")
    ap.add_argument("--all", action="store_true", help="preview every scene")
    ap.add_argument("--quality", default="l", choices=list(QUALITY_FLAG))
    ap.add_argument("--cols", type=int, default=4)
    ap.add_argument("--rows", type=int, default=3)
    ap.add_argument("--final", action="store_true",
                    help="just render (no contact sheet); use with --quality h/k")
    ap.add_argument("--concat", action="store_true",
                    help="stitch all scene videos at --quality into one final film")
    args = ap.parse_args()

    INSPECT_DIR.mkdir(parents=True, exist_ok=True)

    if args.concat and not (args.scene or args.all):
        # Pure concat of whatever is already rendered at this quality.
        concat(args.quality)
        return

    targets = SCENES if args.all else [args.scene]
    if not targets or targets == [None]:
        ap.error("give a scene name, --all, or --concat")

    for scene in targets:
        video = render(scene, args.quality)
        if not args.final:
            contact_sheet(scene, video, args.cols, args.rows)

    if args.concat:
        concat(args.quality)


if __name__ == "__main__":
    main()
