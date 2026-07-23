# Error Handoff

Every failed command prints:

```text
[HATA KODU] E-...
[TANI PAKETİ] logs\diagnostics\DIAGNOSTIC_....zip
```

Send both the error code and the ZIP. Do not send model weights or identity photos.

Useful local commands:

```text
clipctl.bat diagnose latest
clipctl.bat diagnose collect
clipctl.bat job status
clipctl.bat comfy status
clipctl.bat goal status
```
