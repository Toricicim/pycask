class DB:
    def __init__(self) -> None:
        self.dosya = open("database.data","a+")
        self.index = {}
        
        self.yukle()

    def yaz(self,key,value):
        konum = self.dosya.tell()

        self.dosya.write(f"{key},{value}\n")

        self.index[key] = konum

    def oku(self,key):
        if key not in self.index:
            return None
        konum = self.index[key]

        self.dosya.seek(konum)

        satir = self.dosya.readline()

        deger = satir.strip().split(",")[1]
        
        return deger

    def yukle(self):
        self.dosya.seek(0)

        while True:
            baslangic_konum = self.dosya.tell()
            satir = self.dosya.readline()
            if not satir:
                break

            parcalar = satir.strip().split(",")
            anahtar = parcalar[0]

            self.index[anahtar] = baslangic_konum

db = DB()

print("Girdiler:")
db.yaz("kullanici_1", "Ali")
db.yaz("kullanici_2", "Veli")

print("Okunuyor")
gelen_veri = db.oku("kullanici_1")
print(f"kullanici_1: {gelen_veri}")
print(f"kullanici_1 için veritabanından gelen değer: {gelen_veri}")

print(f"Olmayan veri testi: {db.oku("mehmet")}")

print("--- Hafıza Testi ---")
print(f"kullanici_1: {db.oku('kullanici_2')}")
