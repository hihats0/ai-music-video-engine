# ComfyUI operasyon kuralları

## Kurulum yapısı

- Ana program: `comfyui/ComfyUI/main.py`
- Gömülü Python: `comfyui/python_embeded/python.exe`
- API: `http://127.0.0.1:8188`
- Sunucu logu: `logs/comfyui/server.log`

## Kullanılacak komutlar

```text
clipctl.bat comfy status
clipctl.bat comfy start
clipctl.bat comfy stop
clipctl.bat comfy open
```

## Zorunlu kurallar

1. ComfyUI'ı sistem Python'u veya proje `.venv` ortamıyla çalıştırma. Yalnızca embedded Python kullan.
2. API'yi `0.0.0.0` veya LAN adresinde açma. Yalnızca `127.0.0.1` kullan.
3. Manager'ı otomatik etkinleştirme.
4. Kullanıcı izni olmadan custom node kurma.
5. Sunucunun hazır olduğunu varsayma; `/system_stats` sağlık kontrolünü yap.
6. `logs/comfyui/server.log` incelenmeden bağımlılıkları değiştirme.
7. Model veya workflow kurulumu bu aşamanın kapsamı değildir.
