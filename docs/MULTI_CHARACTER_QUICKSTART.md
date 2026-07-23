# Multi-Character Quickstart

This document describes the command sequence for one realistic group shot and one separate solo lip-sync shot. It assumes ComfyUI, SDXL/IPAdapter and Wan 2.2 models have already passed `clipctl.bat goal status`.

## 1. Create identities

Create one identity for each permitted real person:

```text
clipctl.bat identity create person_01
clipctl.bat identity create person_02
clipctl.bat identity create person_03
clipctl.bat identity create person_04
clipctl.bat identity create person_05
clipctl.bat identity create person_06
clipctl.bat identity create person_07
```

Place clear reference images in each `identities/<id>/source/` folder. Set `permission.confirmed: true` in every identity YAML. Check each identity:

```text
clipctl.bat identity check person_01
```

## 2. Create the project and cast registry

```text
clipctl.bat project create realistic_clip
clipctl.bat multicast init realistic_clip
clipctl.bat multicast add realistic_clip person_01 lead look_main high
clipctl.bat multicast add realistic_clip person_02 co_lead look_main high
clipctl.bat multicast add realistic_clip person_03 support look_main normal
clipctl.bat multicast add realistic_clip person_04 support look_main normal
clipctl.bat multicast add realistic_clip person_05 support look_main normal
clipctl.bat multicast add realistic_clip person_06 support look_main normal
clipctl.bat multicast add realistic_clip person_07 support look_main normal
```

Edit:

```text
projects\realistic_clip\wardrobe.yaml
projects\realistic_clip\continuity.yaml
```

Do not leave clothing fields blank. Each person should have a named look with outerwear, top, bottom, footwear, accessories, hair/grooming, dominant colors and prohibited substitutions.

## 3. Create and configure a seven-person group shot

```text
clipctl.bat scene create realistic_clip group_hero_01
clipctl.bat multicast scene realistic_clip group_hero_01 person_01,person_02,person_03,person_04,person_05,person_06,person_07
```

Edit the scene YAML:

```text
projects\realistic_clip\scenes\group_hero_01\scene.yaml
```

Required creative fields include location, time, mood and lighting. Keep group motion low. Recommended:

```yaml
composition:
  location: "wet underground parking garage with concrete pillars"
  time_of_day: "night"
  shot_type: medium_wide
  camera_angle: eye_level
  framing: layered_group
  lens_mm: 35

lighting:
  style: "motivated cinematic practical lighting"
  key_light: "soft cool overhead light with controlled red rim"
  background_light: "blue-white practical fixtures and wet-floor reflections"
  contrast: medium_high

movement:
  camera_motion: slow_dolly_in
  camera_motion_strength: low
  body_motion_strength: low
  head_motion_strength: low

style:
  visual_style: cinematic_photorealism
  mood: "controlled, confident, nocturnal"
  color_description: "black wardrobe, cool blue environment, restrained red accents"
```

Check the scene and inspect the assembled prompt:

```text
clipctl.bat multicast check realistic_clip group_hero_01
clipctl.bat multicast prompt realistic_clip group_hero_01
```

## 4. Generate and approve the group master frame

```text
clipctl.bat frame group-generate realistic_clip group_hero_01
clipctl.bat frame list realistic_clip group_hero_01
```

Open every candidate. Reject any frame with a missing person, duplicated person, blended faces, incorrect outfit, implausible hands or broken perspective.

Approve one exact candidate path:

```text
clipctl.bat frame approve realistic_clip group_hero_01 <candidate-path>
```

## 5. Animate the approved group master

```text
clipctl.bat video group-generate realistic_clip group_hero_01
clipctl.bat quality review realistic_clip group_hero_01
```

The review folder contains one extracted frame per second and a `review.json` cast/wardrobe checklist. Reject the shot if any identity or outfit changes between frames.

A conservative retry is available:

```text
clipctl.bat quality repair realistic_clip group_hero_01
```

## 6. Create a separate solo lip-sync shot

Create a solo scene, add exactly one cast member and generate/approve its video using the normal single-character path. Then set:

```yaml
lipsync:
  enabled: true
  target_identity: person_01
  source_audio: "audio/song.wav"
  start_seconds: 12.0
  end_seconds: 16.0
```

Check optional MuseTalk readiness:

```text
clipctl.bat lipsync status
```

Prepare its 25 FPS video and 16 kHz driving-audio inputs:

```text
clipctl.bat lipsync prepare realistic_clip solo_lipsync_01
```

When the separate MuseTalk runtime and weights are installed:

```text
clipctl.bat lipsync run realistic_clip solo_lipsync_01
```

The lip-sync output is separate from the source generation.

## 7. Final post-processing

Set the desired post settings in the scene YAML, for example:

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
clipctl.bat postprocess run realistic_clip group_hero_01
```

The current always-available baseline uses FFmpeg motion interpolation and Lanczos scaling. Real-ESRGAN and RIFE are optional tool targets and are not silently substituted into the pipeline.

## Quality rule

For seven-person shots, realism comes from an approved master frame, layered blocking, stable wardrobe, controlled movement and strict rejection of bad candidates. Do not use a seven-person close-up, aggressive choreography or group lip-sync as the default production path.
