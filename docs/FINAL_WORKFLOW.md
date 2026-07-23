# Final Operator Workflow

## Update and install

Run `UPDATE_AND_INSTALL.bat`. It pulls the latest code, installs dependencies and all required model assets, restarts ComfyUI and performs the final readiness check.

## Create the local identity and scene

```text
clipctl.bat identity create artist_01
clipctl.bat project create first_clip
clipctl.bat scene create first_clip scene_001
```

Put permitted reference images in `identities\artist_01\source\`, set `permission.confirmed: true`, and fill the scene YAML.

## Generate and approve a start frame

```text
clipctl.bat frame generate first_clip scene_001
clipctl.bat frame list first_clip scene_001
clipctl.bat frame approve first_clip scene_001 <printed-candidate-path>
```

## Generate a raw video

```text
clipctl.bat video generate first_clip scene_001
```

The standard 8 GB profile is 832×480. A CUDA memory failure receives one automatic 704×400 retry.

## Review and repair

```text
clipctl.bat quality review first_clip scene_001
clipctl.bat quality repair first_clip scene_001
```

Review extracts one frame per second. Repair performs a conservative regeneration with low camera, body and head motion and strict anti-occlusion rules.

## Optional final processing

```text
clipctl.bat postprocess status
clipctl.bat postprocess run first_clip scene_001
```

This creates an H.264 1280×720, 48 FPS file using FFmpeg interpolation and Lanczos scaling.

## Failure handoff

Copy the printed error code and provide the generated `logs\diagnostics\DIAGNOSTIC_*.zip`. The bundle excludes reference photos, model files and generated media.
