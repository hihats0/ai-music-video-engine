# Multi-Character Realistic Music Video Context

## Product goal

Build a local, command-driven music-video engine that can maintain a cast of up to seven permitted real people across a clip, generate highly realistic group shots, preserve each character's clothing and appearance, generate solo lip-sync shots, and finish selected outputs with upscale and frame interpolation.

This document is the durable product and engineering context for future Claude Code, Codex, and human work. Changes that conflict with these constraints require an explicit architecture decision record.

## Non-negotiable requirements

- Up to seven distinct characters may appear in one group frame.
- Identity references must only be used after explicit permission is recorded.
- Clothing, hair, accessories, palette, and role must remain stable across shots.
- Lip-sync is designed for one visible lead face per shot. Group shots do not require lip-sync.
- Group output must prioritize realism, temporal stability, blocking, lighting, wardrobe continuity, and recognizable cast over aggressive motion.
- The engine remains usable on the current Windows system: RTX 4070 Laptop GPU with 8 GB VRAM and 16 GB RAM.
- Heavy steps must be resumable, diagnosable, and safe. Failures retain logs and diagnostic bundles.
- The user selects and edits final shots manually; the engine produces organized raw material.

## Evidence-backed technical decisions

### Video backbone

Use the native ComfyUI Wan 2.2 TI2V 5B route for local image-to-video generation. ComfyUI documents that the 5B workflow fits well on 8 GB VRAM with native offloading. The official Wan repository states that TI2V-5B supports image-to-video and 24 FPS output, while full 720p inference outside ComfyUI is substantially more demanding. Therefore the local default is a conservative 832x480 or 704x400 generation profile followed by post-processing.

Sources:
- https://docs.comfy.org/tutorials/video/wan/wan2_2
- https://github.com/Wan-Video/Wan2.2

### Multi-character still construction

Do not concatenate seven identity images into one undifferentiated IPAdapter reference. Build a master group frame using explicit rectangular regions and masks. Apply each character reference only inside the assigned region, and combine regional text conditioning with the global scene conditioning.

The ComfyUI IPAdapter implementation supports attention masks, multiple chained adapters, and regional conditioning. Built-in ComfyUI conditioning nodes support area coordinates, strengths, masks, and combination of multiple conditioning sets.

Sources:
- https://github.com/comfyorg/comfyui-ipadapter
- https://github.com/cubiq/ComfyUI_IPAdapter_plus/blob/main/NODES.md
- https://docs.comfy.org/built-in-nodes/ConditioningSetAreaPercentage
- https://docs.comfy.org/built-in-nodes/ConditioningCombine

### Quality-first group-shot policy

The seven-person workflow is keyframe-first:

1. Define cast, wardrobe, blocking, set, lighting, lens, and motion policy.
2. Generate a global composition plate.
3. Apply character identities regionally according to blocking slots.
4. Run a conservative unification/refinement pass.
5. Require human approval of the master frame.
6. Animate the approved frame with Wan 2.2 using low or medium-low movement.
7. Review extracted frames for identity, clothing, body, and flicker defects.

A seven-person shot should normally use wide or medium-wide framing, layered depth, controlled occlusion, slow camera movement, and subtle body motion. Solo and duo shots carry close facial detail; solo shots carry lip-sync.

### Lip-sync

Use a separate solo-shot pipeline. MuseTalk 1.5 is the preferred research target because its official project describes latent-space face-region modification, improved identity consistency and clarity, and precise lip-speech synchronization. It operates on the visible face region rather than regenerating the entire group frame.

Source:
- https://github.com/TMElyralab/MuseTalk

The local integration must remain optional because it introduces another model environment and significant storage/dependency requirements. The first implementation provides configuration, validation, manifests, command contracts, and a pluggable runner. Installation and GPU acceptance are a separate stage.

### Upscale and frame interpolation

Use deterministic FFmpeg scaling as the always-available baseline. Add optional Real-ESRGAN for learned restoration/upscale and RIFE for interpolation after the selected shot has passed quality review.

Sources:
- https://github.com/xinntao/Real-ESRGAN
- https://github.com/megvii-research/ECCV2022-RIFE

Do not use face enhancement by default on group shots because it can invent or alter identity details. Learned restoration is opt-in and must produce a separate output.

## Architecture

### Project-level files

Each project contains:

- `project.yaml`: project metadata and clip-wide visual language.
- `cast.yaml`: ordered cast registry and identity references.
- `wardrobe.yaml`: stable named looks for each character.
- `continuity.yaml`: clip-wide continuity rules and approved values.
- `scenes/<scene>/scene.yaml`: shot description, cast roster, blocking, motion, and post settings.

### Cast model

Each cast member points to an existing identity directory. The cast registry stores role, priority, approved look, height band, and continuity notes. Identity source photos remain inside `identities/<id>/source` and are excluded from diagnostic archives.

### Blocking model

Every scene uses normalized rectangular slots:

- `x`, `y`, `width`, `height` are values from 0.0 to 1.0.
- `depth` is `front`, `mid`, or `back`.
- `face_priority` controls identity strength and review priority.
- Slots may not overlap excessively unless `allow_occlusion` is explicit.

Recommended seven-character hero blocking:

- two front characters,
- three mid characters,
- two rear characters,
- asymmetric spacing,
- no more than three high-priority faces.

### Workflow tiers

1. `group_master`: regional multi-character still generation.
2. `group_video`: conservative Wan image-to-video animation.
3. `solo_master`: high-priority single-character still.
4. `solo_video`: performance video generation.
5. `solo_lipsync`: optional MuseTalk processing.
6. `quality_review`: frame extraction and continuity checklist.
7. `postprocess`: upscale, interpolation, and export.

## Default quality presets

### `group_realism_7`

- people: 2-7
- base resolution: 832x480
- low-memory retry: 704x400
- duration: 4 seconds
- target generated frames: nearest valid Wan frame count
- camera motion: static, slow dolly, or slow lateral
- body motion: low
- head motion: low
- lip-sync: disabled
- visible high-priority faces: maximum 3
- alternatives: minimum 3 for master-frame review

### `solo_lipsync_quality`

- people: 1
- shot: medium close-up or close-up
- head movement: low
- face occlusion: disabled
- duration: 3-5 seconds
- lip-sync target: one identity
- source audio: explicit clip file and time range

## Continuity policy

Wardrobe continuity is data, not prose alone. Every character uses an approved named look containing:

- outerwear
- top
- bottom
- footwear
- accessories
- hair and grooming
- makeup where applicable
- dominant and accent colors
- prohibited substitutions

Generated scene prompts are assembled from these fields. A scene may override a look only through a named alternate look recorded in `wardrobe.yaml`.

## Validation and safety rules

- Cast size must be between 1 and 7.
- Every cast member must exist as an identity and have permission confirmed.
- Every scene member must reference a defined wardrobe look.
- Blocking boxes must stay inside the frame.
- Duplicate identity IDs in a scene are rejected.
- Group scenes reject lip-sync settings.
- Solo lip-sync scenes reject more than one cast member.
- Video generation requires an approved master frame.
- Post-processing never overwrites the source generation.

## Implementation sequence

### Phase 1 — data and CLI foundation

- Add project cast, wardrobe, continuity, and multi-character scene schemas.
- Add validation and prompt assembly.
- Add commands to initialize and check multi-character projects.
- Maintain backward compatibility with existing single-character scenes.

### Phase 2 — regional master-frame workflow

- Add mask generation from normalized blocking boxes.
- Build a chained regional IPAdapter workflow for 2-7 identities.
- Add a global refinement pass and master-frame alternatives.
- Add runtime node compatibility checks.

### Phase 3 — group video and review

- Feed approved group masters into Wan 2.2.
- Add group-specific conservative retry policies.
- Expand quality review with cast and wardrobe checklists.

### Phase 4 — solo lip-sync

- Add MuseTalk model manifest and optional installer.
- Add audio segment configuration and solo-only validation.
- Preserve original audio/video and emit a separate synced file.

### Phase 5 — learned post-processing

- Add optional Real-ESRGAN and RIFE runners.
- Keep FFmpeg baseline available.
- Record all transformation settings in metadata.

## Acceptance target

The first end-to-end acceptance project contains seven permitted identities and produces:

- one approved seven-character hero master frame,
- one four-second seven-character group video,
- one approved solo performance video,
- one optional solo lip-sync result,
- one 720p/24 FPS final post-processed result,
- complete generation metadata and diagnostic traces.
