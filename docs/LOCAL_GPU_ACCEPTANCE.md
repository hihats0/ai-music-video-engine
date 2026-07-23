# Local GPU Acceptance — Multi-Character v1.1 Alpha

This branch is not production-ready until it passes the following checks on the target Windows machine.

## Why acceptance is staged

A two-person shot verifies ComfyUI node names, IPAdapter masks, API workflow submission, output download and the GPU recovery path with much less wasted generation time. Only after that succeeds should a seven-person master be attempted.

## A. Install the branch

From the local repository root:

```powershell
git fetch origin
git switch agent/multi-character-v2
git pull --ff-only origin agent/multi-character-v2
.\UPDATE_AND_INSTALL.bat
```

The branch remains a draft PR and is not merged into `main` during acceptance.

## B. Static and runtime readiness

Run:

```powershell
.\RUN_MULTI_CHARACTER_CHECKS.bat
```

Required result:

- Python compile succeeds.
- Unit tests succeed.
- `goal status` reports the ComfyUI API online.
- Wan, SDXL and IPAdapter models are present.
- Group-frame required nodes are present.

`lipsync status` is informative and may remain not-ready until the separate MuseTalk runtime is installed.

## C. Two-person workflow acceptance

Use two identities with explicit permission and at least one clear source image each.

```powershell
.\clipctl.bat project create acceptance_clip
.\clipctl.bat multicast init acceptance_clip
.\clipctl.bat multicast add acceptance_clip person_01 lead look_main high
.\clipctl.bat multicast add acceptance_clip person_02 co_lead look_main high
.\clipctl.bat scene create acceptance_clip duo_test
.\clipctl.bat multicast scene acceptance_clip duo_test person_01,person_02
```

Fill the two named wardrobe looks in:

```text
projects\acceptance_clip\wardrobe.yaml
```

Fill location, lighting and mood in:

```text
projects\acceptance_clip\scenes\duo_test\scene.yaml
```

Then run:

```powershell
.\clipctl.bat multicast check acceptance_clip duo_test
.\clipctl.bat frame group-generate acceptance_clip duo_test
.\clipctl.bat frame list acceptance_clip duo_test
```

Acceptance conditions:

- Two distinct people are present.
- The faces are not blended or duplicated.
- Each person appears inside the intended blocking region.
- Clothing matches the named look.
- No ComfyUI node-validation error occurs.
- The standard profile completes, or the automatic low-VRAM retry completes.

Approve the strongest candidate and animate it:

```powershell
.\clipctl.bat frame approve acceptance_clip duo_test <candidate-path>
.\clipctl.bat video group-generate acceptance_clip duo_test
.\clipctl.bat quality review acceptance_clip duo_test
```

Reject the output if either identity swaps, clothing changes, body parts merge, or a person teleports between extracted review frames.

## D. Seven-person master-frame acceptance

Add five more ready identities and complete all wardrobe looks. Create a separate scene:

```powershell
.\clipctl.bat scene create acceptance_clip seven_test
.\clipctl.bat multicast scene acceptance_clip seven_test person_01,person_02,person_03,person_04,person_05,person_06,person_07
.\clipctl.bat multicast check acceptance_clip seven_test
.\clipctl.bat frame group-generate acceptance_clip seven_test
```

Acceptance conditions for the master frame:

- Exactly seven people; no duplicate or missing person.
- At least the two lead/high-priority identities are clearly recognizable.
- Supporting identities remain distinct and are not face clones.
- All seven named wardrobe looks and palette constraints are respected.
- Perspective, body scale, ground contact and shadows are plausible.
- No more than three faces are marked `high` priority.
- The composition reads as layered front/mid/back blocking, not a flat lineup.

Generate at least three alternatives and approve only a frame passing every condition.

## E. Seven-person video acceptance

```powershell
.\clipctl.bat frame approve acceptance_clip seven_test <candidate-path>
.\clipctl.bat video group-generate acceptance_clip seven_test
.\clipctl.bat quality review acceptance_clip seven_test
```

Acceptance conditions:

- Character count remains seven throughout the clip.
- No identity swaps or face blending.
- No outfit morphing or accessory teleportation.
- Lead faces remain stable.
- Body and head motion stays subtle and plausible.
- Camera motion does not introduce severe blur or geometry collapse.
- Lighting direction and shadows remain coherent.

A failed shot must be rejected rather than repaired with face enhancement. First retry:

```powershell
.\clipctl.bat quality repair acceptance_clip seven_test
```

## F. Post-processing acceptance

After selecting a stable group video:

```powershell
.\clipctl.bat postprocess run acceptance_clip seven_test
```

Check:

- source MP4 still exists and is unchanged;
- final resolution and FPS match `scene.yaml`;
- interpolation does not create duplicate limbs or face warping;
- scaling does not oversharpen or invent facial details.

## G. Solo lip-sync acceptance

MuseTalk is tested only after group generation passes. Use a separate single-person scene with a medium close-up, low head motion and unobstructed face.

```powershell
.\clipctl.bat lipsync status
.\clipctl.bat lipsync prepare acceptance_clip solo_lipsync_test
.\clipctl.bat lipsync run acceptance_clip solo_lipsync_test
```

Check mouth timing, lip shape, mustache/facial-hair preservation, face jitter and cheek/jaw blending. MuseTalk output remains separate from the original video.

## Failure evidence

For every failure preserve and share:

```text
[HATA KODU]
[TANI PAKETİ]
logs\comfyui\server.log
logs\bootstrap\update_*.log
```

Do not delete model files or reset the Git repository while diagnosing a failure.
