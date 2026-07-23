# AI Music Video Engine

Terminal-first, ComfyUI-based raw music-video scene generator for Windows.

Current development milestone: **Multi-Character Pipeline v1.1.0-alpha.1**.

## Target machine

- NVIDIA RTX 4070 Laptop GPU
- 8 GB VRAM
- 16 GB system RAM
- Windows
- One heavy GPU job at a time

## Production goal

- Up to seven permitted real people in one realistic group frame and group clip.
- Named wardrobe looks and clip-wide continuity rules.
- Region-masked identity conditioning rather than one mixed reference batch.
- Human approval of a group master frame before animation.
- Conservative Wan 2.2 group animation.
- Solo-only optional lip-sync through a separate MuseTalk 1.5 runtime.
- Quality review, source-preserving post-processing, upscale and interpolation.
- Manual final edit and music-video timeline assembly.

The durable architecture context is in:

```text
docs\MULTI_CHARACTER_REALISTIC_CLIP_CONTEXT.md
```

The command-by-command workflow is in:

```text
docs\MULTI_CHARACTER_QUICKSTART.md
```

## Core pipeline

1. Keep permitted identity references locally.
2. Register 1–7 cast members in each project.
3. Define named wardrobe looks and continuity constraints.
4. Define normalized blocking rectangles for each group scene.
5. Generate several SDXL/IPAdapter regional group-master candidates.
6. Approve one exact master frame after checking all faces, bodies and outfits.
7. Animate the approved master with Wan 2.2 TI2V 5B.
8. Extract review frames and complete the cast/wardrobe checklist.
9. Generate separate single-person performance shots for lip-sync.
10. Optionally prepare/run MuseTalk and apply source-preserving post-processing.

## Install or update

In the connected local engine folder run:

```text
UPDATE_AND_INSTALL.bat
```

It performs a fast-forward `git pull`, updates Python dependencies and runs the all-stage installer. Model downloads resume after interruption. Model weights and third-party runtimes never enter Git.

Final readiness check:

```text
clipctl.bat goal status
```

## Single-character compatibility

The existing single-character path remains available:

```text
clipctl.bat identity create artist_01
clipctl.bat project create first_clip
clipctl.bat scene create first_clip scene_001
clipctl.bat frame generate first_clip scene_001
clipctl.bat frame list first_clip scene_001
clipctl.bat frame approve first_clip scene_001 <candidate-path>
clipctl.bat video generate first_clip scene_001
```

## Multi-character project

Create identities and put permitted photos in their local `source` folders. Every identity requires `permission.confirmed: true`.

```text
clipctl.bat project create realistic_clip
clipctl.bat multicast init realistic_clip
clipctl.bat multicast add realistic_clip person_01 lead look_main high
clipctl.bat multicast add realistic_clip person_02 co_lead look_main high
clipctl.bat multicast add realistic_clip person_03 support look_main normal
```

Continue up to seven people, then complete:

```text
projects\realistic_clip\wardrobe.yaml
projects\realistic_clip\continuity.yaml
```

Create a group scene:

```text
clipctl.bat scene create realistic_clip group_hero_01
clipctl.bat multicast scene realistic_clip group_hero_01 person_01,person_02,person_03
clipctl.bat multicast check realistic_clip group_hero_01
clipctl.bat multicast prompt realistic_clip group_hero_01
```

Generate, approve and animate:

```text
clipctl.bat frame group-generate realistic_clip group_hero_01
clipctl.bat frame list realistic_clip group_hero_01
clipctl.bat frame approve realistic_clip group_hero_01 <candidate-path>
clipctl.bat video group-generate realistic_clip group_hero_01
clipctl.bat quality review realistic_clip group_hero_01
```

A conservative group regeneration is available:

```text
clipctl.bat quality repair realistic_clip group_hero_01
```

## Solo lip-sync

Group lip-sync is rejected by validation. Lip-sync is for a scene containing exactly one cast member.

Set its scene YAML:

```yaml
lipsync:
  enabled: true
  target_identity: person_01
  source_audio: "audio/song.wav"
  start_seconds: 12.0
  end_seconds: 16.0
```

Commands:

```text
clipctl.bat lipsync status
clipctl.bat lipsync prepare realistic_clip solo_lipsync_01
clipctl.bat lipsync run realistic_clip solo_lipsync_01
```

`prepare` creates a 25 FPS input video and 16 kHz mono driving audio. `run` requires a separately installed MuseTalk 1.5 checkout, Python environment and weights under `tools\MuseTalk`. It never overwrites the source video.

## Post-processing

Post settings are read from each scene:

```yaml
postprocess:
  upscale: true
  interpolation: true
  target_width: 1280
  target_height: 720
  target_fps: 24
  learned_upscale: false
```

Run:

```text
clipctl.bat postprocess status
clipctl.bat postprocess run realistic_clip group_hero_01
```

The guaranteed baseline uses FFmpeg interpolation and Lanczos scaling. Real-ESRGAN and RIFE are optional local tool targets; learned processing is not claimed unless its runner is actually installed and used.

## Failure diagnostics

Every intercepted and legacy CLI command receives a unique run ID. On failure the terminal prints:

```text
[HATA KODU] E-...
[TANI PAKETİ] logs\diagnostics\DIAGNOSTIC_....zip
```

The diagnostic bundle contains traceback, command journal, GPU and driver snapshot, Git revision, configuration inventory and the tail of the ComfyUI server log. It excludes reference photos, model weights and generated media.

Manual collection:

```text
clipctl.bat diagnose collect
```

## Privacy and consent

Real-person references are processed only after `permission.confirmed: true`. Photos, identity folders, model weights, videos, audio, logs, third-party runtimes and the local ComfyUI runtime are excluded from Git.

## Alpha limitation

Static workflow and schema tests are automated. Actual seven-person generation quality, exact ComfyUI node compatibility, MuseTalk runtime acceptance and 8 GB VRAM behavior must still be validated on the target Windows machine before this branch is treated as production-ready.
