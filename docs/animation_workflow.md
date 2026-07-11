# Combo-graph animation: inspect-and-improve workflow

A repeatable loop for iterating on [`combo_graph_animation.py`](combo_graph_animation.py)
(the Manim explainer for [`backend/spellbook/variants/combo_graph.py`](../backend/spellbook/variants/combo_graph.py)).

The core idea: **render a scene fast, flatten its whole timeline into one
"contact-sheet" image, look at that image, fix the code, repeat.** A single
picture exposes overlapping labels, off-screen nodes, crossing arrows, dead
time, and colour clashes far quicker than scrubbing a video.

## The loop

```
                 ┌───────────────────────────────────────────┐
                 ▼                                             │
   docs/preview_scene.py <Scene>     edit combo_graph_animation.py
                 │                                             ▲
                 ├─ manim -ql  (fast 480p render)              │
                 ├─ ffmpeg     (sample ~12–20 frames)          │
                 └─ ffmpeg     (tile into one _sheet.png)  ────┘
                                     │
                                Read the sheet, spot the defect
```

## Commands

Run from the repo root (the helper pins Manim's output dir, so the working
directory does not matter):

```sh
# One scene → media/inspect/<Scene>_sheet.png  (a numbered 4×3 grid of frames)
docs/.venv-manim/Scripts/python.exe docs/preview_scene.py Scene02_DownPhaseDFS

# Denser grid for a long/busy scene
docs/.venv-manim/Scripts/python.exe docs/preview_scene.py Scene02_DownPhaseDFS --cols 5 --rows 4

# Contact sheet for every scene
docs/.venv-manim/Scripts/python.exe docs/preview_scene.py --all

# Final film: render every scene at 1080p60, then stitch to one mp4
docs/.venv-manim/Scripts/python.exe docs/preview_scene.py --all --final --concat --quality h

# Just re-stitch whatever is already rendered at a quality
docs/.venv-manim/Scripts/python.exe docs/preview_scene.py --concat --quality h
```

Outputs:

- `docs/media/inspect/<Scene>_sheet.png` — the contact sheet to inspect
- `docs/media/inspect/<Scene>_frames/` — the raw sampled frames
- `docs/media/videos/combo_graph_animation/<quality>/<Scene>.mp4` — per-scene clips
- `docs/combo_graph_explained.mp4` — the concatenated final film

Everything under `docs/media/` is git-ignored and fully regenerable.

## Gotchas this workflow guards against

These bit us once; the helper now handles them so the loop stays trustworthy:

1. **Manim writes `./media` relative to the current directory.** Launch from a
   different folder and you silently inspect a *stale* render elsewhere. The
   helper passes `--media_dir docs/media` so output always lands next to the
   script.
2. **Manim caches partial-movie files** and can replay stale frames after an
   edit. The helper always passes `--disable_caching`.
3. **`docs/__pycache__`** can hold a compiled copy of the scene module — if a
   render ever looks wrong after an edit, delete it.
4. **`ffmpeg -ss` before `-i`** seeks by keyframe (fast but approximate); good
   enough for inspection, not for frame-exact work.

## Scenes (narrative order)

| Scene | Class | Shows |
|------:|-------|-------|
| 00 | `Scene00_Title` | Branded title card (lavender→coral) + card→combo→feature motif |
| 01 | `Scene01_GraphOverview` | The full tri-partite graph: cards → combos → features |
| 02 | `Scene02_DownPhaseDFS` | Faithful `_combo_nodes_down(C3)` recursion with a call-stack panel |
| 03 | `Scene03_VariantSetsGeometric` | OR = union of providers, AND = cross-product |
| 04 | `Scene04_MinimalSets` | Antichain pruning: discard supersets, keep subsets |
| 04b | `Scene04b_TwoFeatureMerge` | A combo needing two multi-recipe features: cross-product table where one product is a subset of another, so minimality prunes it |
| 05 | `Scene05_UpPhase` | Forward propagation from a hand of cards to `Win` |
| 06 | `Scene06_DownVsUp` | Down phase (DFS from target) vs up phase (BFS from cards) |

The legacy alias classes at the bottom of the script keep older render commands
working; the concatenation uses the `SceneNN_*` names in the order above.
