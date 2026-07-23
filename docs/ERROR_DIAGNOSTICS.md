# Hata ve Tanı Sistemi

Motorun her terminal komutu ayrı bir `run_id` ile kaydedilir.

## Hata çıktısı

Bir işlem başarısız olduğunda terminalde üç önemli bölüm görünür:

```text
[HATA] İnsan tarafından okunabilir açıklama
[HATA KODU] E-VIDEO-GENERATE-123456
[TANI PAKETİ] logs\diagnostics\DIAGNOSTIC_20260723_123456.zip
```

Sorun bildirilirken hata kodu ile tanı ZIP'i birlikte kullanılmalıdır.

## Tanı ZIP'inde bulunanlar

- Tam Python traceback
- Çalıştırılan komut ve `run_id`
- Olay günlüğü
- Windows, Python, GPU ve sürücü özeti
- Boş disk alanı
- Git commit'i, remote ve çalışma ağacı durumu
- ComfyUI `server.log` dosyasının son bölümü
- Motor günlüğünün son bölümü
- Yapılandırma ve model envanteri

## Tanı ZIP'ine konulmayanlar

- Gerçek kişi fotoğrafları
- Kimlik dosyalarının görsel içerikleri
- Model ağırlıkları
- Üretilen videolar ve sesler
- ComfyUI'ın büyük çalışma ortamı

## Elle tanı paketi oluşturma

```text
clipctl.bat diagnose collect
```

Son oluşturulan paketi bulma:

```text
clipctl.bat diagnose latest
```

## Kurulum aşaması hataları

`UPDATE_AND_INSTALL.bat` ayrıca şu dosyayı oluşturur:

```text
logs\bootstrap\update_TARIH_SAAT.log
```

Git, Python ortamı veya model indirme aşamasında sorun olursa bu log da saklanmalıdır.

## CUDA bellek hatası

Normal video profili GPU belleğine sığmazsa motor bir kez düşük çözünürlüklü kurtarma profiliyle yeniden dener. İkinci deneme de başarısız olursa başka otomatik deneme yapılmaz; hata kodu ve tanı paketi üretilir.

## Takılı kalan GPU kilidi

Önce durumu kontrol et:

```text
clipctl.bat job status
```

ComfyUI işi gerçekten çalışmıyorsa kilidi kaldır:

```text
clipctl.bat job cancel
```
