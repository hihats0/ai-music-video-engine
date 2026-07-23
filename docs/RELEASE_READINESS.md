# v1.0.0 Release Readiness

This branch exists to run the repository test workflow against the complete pipeline.

Validated surfaces:

- core CLI and diagnostics
- ComfyUI headless API integration
- resumable Wan 2.2 TI2V 5B assets
- consent-gated SDXL + IPAdapter start frames
- explicit frame approval
- Wan video generation and low-VRAM retry
- review-frame extraction and conservative repair
- optional 720p/48 FPS post-processing
- privacy exclusions for local references, models, outputs and logs

Hardware-dependent generation remains a local acceptance test on the target RTX 4070 Laptop GPU.
