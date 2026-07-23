# AI Music Video Engine

Terminal-first, ComfyUI-based raw music-video scene generator for Windows.

Current milestone: **Goal MVP v0.9.0**.

## Target machine

- NVIDIA RTX 4070 Laptop GPU
- 8 GB VRAM
- 16 GB system RAM
- Windows
- One heavy GPU job at a time

## What the engine does

1. Stores real-person references locally.
2. Creates project and scene definitions.
3. Lets the user approve a start frame.
4. Converts the approved frame into a 4–5 second 16:9 Wan 2.2 clip.
5. Saves prompts, seeds, ComfyUI history, outputs and diagnostic records.

Final editing, music synchronization and timeline assembly remain manual.

## Install or update

After the local folder has been connected to this repository, run:

```text
UPDATE_AND_INSTALL.bat
```

The script performs a fast-forward `git pull`, updates Python dependencies, starts ComfyUI, downloads the official Wan 2.2 5B files with resume support and runs the final readiness check.

Manual equivalent:

```text
git pull --ff-only
clipctl.bat goal install
clipctl.bat goal status
```

## Basic workflow

```text
clipctl.bat identity create artist_01
clipctl.bat project create first_clip
clipctl.bat scene create first_clip scene_001
```

Put permitted reference images in:

```text
identities\artist_01\source\
```

Set `permission.confirmed: true` in the identity YAML and fill the scene YAML. Then:

```text
clipctl.bat frame prepare first_clip scene_001
clipctl.bat frame list first_clip scene_001
clipctl.bat frame approve first_clip scene_001 identity_reference_01.jpg
clipctl.bat video generate first_clip scene_001
```

## Failure diagnostics

Every CLI command gets a unique run ID. On failure the terminal prints:

```text
[HATA KODU] E-...
[TANI PAKETİ] logs\diagnostics\DIAGNOSTIC_....zip
```

The bundle contains the traceback, command journal, GPU/driver snapshot, Git revision, configuration inventory and the tail of the ComfyUI server log. It does not include identity photos, model weights or generated media.

Manual collection:

```text
clipctl.bat diagnose collect
```

See `docs/ERROR_DIAGNOSTICS.md` and `docs/FINAL_WORKFLOW.md`.

## Privacy and repository safety

Real-person photos, identity data, model weights, generated videos, logs and the local ComfyUI runtime are excluded from Git by `.gitignore`.
