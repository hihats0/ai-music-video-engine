# Donanım Sınırları

Bu proje şu bilgisayar için hazırlanmıştır:

- GPU: RTX 4070 Mobile
- VRAM: 8 GB
- Sistem RAM: 16 GB
- İşletim sistemi: Windows

## Değiştirilemez kurallar

1. Aynı anda yalnızca bir GPU üretim görevi çalıştır.
2. 832×480 üzeri ham video üretme.
3. 81 kare üzeri video üretme.
4. İkinci video işinden önce mevcut görevi kontrol et.
5. Out-of-memory sonrasında ayarları otomatik yükseltme.
6. Sistem RAM'i 2 GB altına yaklaşırsa yeni iş başlatma.
7. Kullanıcı açıkça istemedikçe büyük model indirme.
8. LTX-2, Wan 14B ve benzeri ağır modelleri kurma.
9. Windows ve diğer programlar için RAM bırak.
10. Başarısız görevi başarılı olarak bildirme.
