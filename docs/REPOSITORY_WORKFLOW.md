# Repository workflow

Development proceeds in small commits. Large model weights, ComfyUI runtime files, identity references and generated media remain local.

## Milestones

- v0.1.0 Core engine
- v0.2.0 ComfyUI headless integration
- v0.2.1 portable-layout repair
- v0.2.2 stable startup path
- v0.3.0 identity and start-frame generation
- v0.4.0 image-to-video generation

## Commit policy

- One logical change per commit.
- Never commit model weights, real-person reference media, generated video, local logs or embedded Python.
- Run the relevant local validation before marking a stage complete.
- Stage installers remain versioned under `installers/`.
