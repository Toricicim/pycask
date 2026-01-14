# PyCask: Binary Key-Value Store

Python ile sıfırdan geliştirilmiş, disk tabanlı ve kalıcı (persistent) bir Anahtar-Değer (Key-Value) veritabanı motoru. Bu proje, Bitcask mimarisinin temel prensibi olan "Log-Structured File System" yapısını anlamak ve uygulamak amacıyla tasarlanmıştır.

Veriler disk üzerinde binary (ikili) formatta saklanır ve bellek içi (In-Memory) bir indeks yapısı ile yönetilir.

## Özellikler

- **Kalıcılık (Persistence):** Veriler diskte "append-only" (sadece ekleme) yöntemiyle saklanır. Program kapatılsa bile veriler korunur.
- **Yüksek Performans:** RAM üzerinde tutulan Hash Index sayesinde okuma işlemleri O(1) karmaşıklığında gerçekleşir.
- **Binary Protokol:** Veriler CSV veya metin formatında değil, `struct` modülü kullanılarak binary formatta paketlenir. Bu sayede veri içinde geçen özel karakterler (virgül, yeni satır vb.) bozulmaya yol açmaz.
- **Otomatik Kurtarma (Recovery):** Veritabanı başlatıldığında, diskteki veri dosyası taranarak indeks haritası otomatik olarak yeniden oluşturulur.
- **Bağımlılık Yok:** Harici hiçbir kütüphane kullanılmamıştır, sadece Python Standart Kütüphanesi (`struct`, `os`) ile yazılmıştır.

## Mimari

Bu veritabanı motoru iki ana bileşenden oluşur:

1.  **Disk Depolama (Data File):** Veriler diske sıralı olarak yazılır. Her kayıt şu binary formata sahiptir:
    `[Key Size (4 Byte)] [Value Size (4 Byte)] [Key Data] [Value Data]`
    
2.  **Bellek İndeksi (KeyDir):** Python'un yerleşik sözlük yapısı (Hash Map) kullanılarak anahtarların diskteki byte ofsetleri (başlangıç konumları) RAM'de tutulur.

## Kurulum

Bu proje herhangi bir harici paket kurulumu gerektirmez. Python 3.x yüklü olması yeterlidir.

Projeyi klonlayın:

git clone https://github.com/KULLANICI_ADIN/py-bitcask-db.git
cd py-bitcask-db

## Kullanım

Veritabanını projenize dahil etmek ve kullanmak için aşağıdaki örneği inceleyebilirsiniz:

```python
from db import DB

# Veritabanını başlat (Dosya yoksa oluşturulur, varsa indeks yüklenir)
db = DB()

# Veri Yazma
# Anahtar ve değer string tipinde olmalıdır.
db.yaz("kullanici_id", "10245")
db.yaz("kullanici_adi", "ahmet_yilmaz")
print("Veriler diske yazıldı.")

# Veri Okuma
# O(1) hızında diskten okuma yapar.
gelen_veri = db.oku("kullanici_adi")
print(f"Okunan Değer: {gelen_veri}")

# Olmayan veri sorgusu None döner
sonuc = db.oku("olmayan_anahtar")
