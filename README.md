# AI Music Video Engine

Terminal-first, ComfyUI-based raw music-video scene generator for Windows.

Current milestone: **Full Pipeline MVP v1.0.0**.

## Target machine

- NVIDIA RTX 4070 Laptop GPU
- 8 GB VRAM
- 16 GB system RAM
- Windows
- One heavy GPU job at a time

## Pipeline

1. Keep permitted real-person references locally.
2. Define projects and scenes in YAML.
3. Generate 16:9 SDXL + IPAdapter portrait start-frame alternatives.
4. Require explicit user approval of one start frame.
5. Generate a 4–5 second Wan 2.2 TI2V 5B clip.
6. Extract review frames and optionally run a conservative low-motion repair.
7. Optionally interpolate and upscale to 1280×720 at 48 FPS.
8. Store prompts, workflows, seeds, output metadata, logs and safe diagnostic ZIPs.

Final editing, music synchronization and timeline assembly remain manual.

## Install or update

In the connected local engine folder run:

```text
UPDATE_AND_INSTALL.bat
```

It performs a fast-forward `git pull`, updates Python dependencies and runs the all-stage installer. Model downloads resume after interruption. The complete local model set requires substantial disk space; model weights never enter Git.

Manual equivalent:

```text
git pull --ff-only
INSTALL_ALL_STAGES.bat
```

Final readiness check:

```text
clipctl.bat goal status
```

## First project

```text
clipctl.bat identity create artist_01
clipctl.bat project create first_clip
clipctl.bat scene create first_clip scene_001
```

Put permitted reference photos in:

```text
identities\artist_01\source\
```

Set `permission.confirmed: true` in `identities\artist_01\identity.yaml`. Fill the required fields in `projects\first_clip\scenes\scene_001\scene.yaml`.

Generate start frames:

```text
clipctl.bat frame generate first_clip scene_001
clipctl.bat frame list first_clip scene_001
```

Approve one exact path printed by `frame list`:

```text
clipctl.bat frame approve first_clip scene_001 projects\first_clip\scenes\scene_001\frames\generated_...\candidate_01_01.png
```

Generate video:

```text
clipctl.bat video generate first_clip scene_001
```

Review and repair when needed:

```text
clipctl.bat quality review first_clip scene_001
clipctl.bat quality repair first_clip scene_001
```

Optional final processing:

```text
clipctl.bat postprocess status
clipctl.bat postprocess run first_clip scene_001
```

## Failure diagnostics

Every intercepted and legacy CLI command receives a unique run ID. On failure the terminal prints:

```text
[HATA KODU] E-...
[TANI PAKETİ] logs\diagnostics\DIAGNOSTIC_....zip
```

The diagnostic bundle contains the traceback, command journal, GPU and driver snapshot, Git revision, configuration inventory and the tail of the ComfyUI server log. It excludes reference photos, model weights and generated media.

Manual collection:

```text
clipctl.bat diagnose collect
```

## Privacy and consent

Real-person references are processed only after `permission.confirmed: true`. Photos, identity folders, model weights, videos, logs and the local ComfyUI runtime are excluded from Git by `.gitignore`.
