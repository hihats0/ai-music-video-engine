# Proje Kuralları

## Temel görev

Bu sistem ham müzik klibi sahneleri üretir.

## Yasak işler

- Final video kurgulamak
- Timeline oluşturmak
- Müziğe göre otomatik sahne dizmek
- Altyazı eklemek
- Kullanıcının dosyalarını silmek
- İnternete video yüklemek
- Kullanıcı onayı olmadan custom node kurmak
- Test edilmemiş workflow çalıştırmak
- İki GPU görevini aynı anda çalıştırmak

## Sahne üretim sırası

1. Projeyi doğrula.
2. Kimlik profilini doğrula.
3. Sahne YAML dosyasını doğrula.
4. Draft başlangıç karesi üret.
5. Kullanıcının seçtiği kareyi kaydet.
6. Seçilen kareden video üret.
7. Prompt, seed ve ayarları kaydet.
8. Sonucu generations klasörüne koy.
9. Sonucu otomatik olarak approved klasörüne taşıma.

## Kullanıcı seviyesi

Kullanıcının teknik bilgi bildiğini varsayma. Her hata mesajında şu üç soruyu açıkça cevapla:

- Ne oldu?
- Neden olmuş olabilir?
- Kullanıcı şimdi ne yapmalı?
