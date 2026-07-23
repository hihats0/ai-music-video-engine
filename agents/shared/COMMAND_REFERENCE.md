# Komut Referansı

```powershell
clipctl.bat system init
clipctl.bat system check
clipctl.bat system status
clipctl.bat system doctor

clipctl.bat comfy status
clipctl.bat comfy start
clipctl.bat comfy stop
clipctl.bat comfy open

clipctl.bat project create PROJE_ADI
clipctl.bat project list
clipctl.bat project show PROJE_ADI

clipctl.bat identity create KISI_ADI
clipctl.bat identity check KISI_ADI
clipctl.bat identity show KISI_ADI

clipctl.bat scene create PROJE_ADI SAHNE_ADI
clipctl.bat scene check PROJE_ADI SAHNE_ADI
clipctl.bat scene show PROJE_ADI SAHNE_ADI

clipctl.bat frame generate PROJE_ADI SAHNE_ADI
clipctl.bat video generate PROJE_ADI SAHNE_ADI

clipctl.bat job status
clipctl.bat job cancel
```

`frame generate` ve `video generate` komutları şu anda yalnızca hazırlık kontrolü yapar. Gerçek üretim ComfyUI workflow ve model aşamaları eklendiğinde etkinleşir.
