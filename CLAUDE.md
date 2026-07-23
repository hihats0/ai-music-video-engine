# Claude Code Talimatları

Bu proje 8 GB VRAM ve 16 GB RAM sınırına göre hazırlanmıştır.

Başlamadan önce sırayla oku:

1. `agents/shared/PROJECT_RULES.md`
2. `agents/shared/HARDWARE_LIMITS.md`
3. `agents/shared/COMMAND_REFERENCE.md`
4. `configs/hardware.yaml`
5. `configs/engine.yaml`

Ana görevlerin:

- Kullanıcının sahne fikrini açık bir `scene.yaml` dosyasına çevirmek
- Görsel prompt hazırlamak
- Video hareket promptu hazırlamak
- Üretilen görüntüleri eleştirmek
- Kimlik kayması ve görüntü hatalarını açıklamak
- Güvenli yeniden deneme önermek

Final kurgu yapma.
Kullanıcının seçtiği dosyaları silme.
Test edilmemiş workflow veya custom node kullanma.
GPU görevlerini `clipctl` dışında başlatma.


2. AŞAMA sonrası ayrıca oku:

- agents/shared/COMFYUI_OPERATIONS.md
- configs/comfyui.yaml
