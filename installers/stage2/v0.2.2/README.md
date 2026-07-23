# 2. Aşama — Kalıcı ComfyUI Düzeltmesi v0.2.2

Bu paket, ComfyUI'nin elle açılmasını sağlayan klasör düzeltmesini kalıcı hâle getirir.

## Düzeltilen sorun

Eski başlatma dosyası `comfyui\runtime\main.py` yolunu çalıştırıyordu. ComfyUI Windows Portable kendi kaynak klasörünü `ComfyUI` adıyla beklediği için `import comfy.options` hatası oluşuyordu.

v0.2.2 şu yapıyı kullanır:

```text
comfyui/
├── ComfyUI -> runtime klasörüne junction
├── python_embeded/
└── runtime/
```

Başlatma komutu:

```text
python_embeded\python.exe -s ComfyUI\main.py
```

## Kullanım

1. Açık ComfyUI ve PowerShell pencerelerini kapat.
2. `2_ASAMA_2_2_UYGULA.bat` dosyasını çalıştır.
3. İçinde `clipctl.bat` bulunan ana motor klasörünü seç.
4. `[OK] 2. ASAMA v0.2.2 TAMAMEN HAZIR` mesajını bekle.
5. `http://127.0.0.1:8188` adresini aç.

Paket ComfyUI'yi yeniden indirmez, model indirmez ve proje dosyalarını silmez.
