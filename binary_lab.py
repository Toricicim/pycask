import struct

key = "isim"
value = "İstatistikçi"

key_bytes = key.encode("utf-8")
value_bytes = value.encode("utf-8")

k_len = len(key_bytes)
v_len = len(value_bytes)

print(f"Key Uzunluk:{k_len} byte")
print(f"Value Uzunluk:{v_len} byte")

#  Paketleme:
header= struct.pack("II", k_len,v_len)

tam_veri = header + key_bytes + value_bytes
print(f"Diske yazılacak ham veri: {tam_veri}")

okunan_header = tam_veri[0:8]

cozulen_len_k, cozulen_len_v = struct.unpack("II",okunan_header)
print(f"Headerda okunan boylar, key: {cozulen_len_k}, value: {cozulen_len_v}")

start = 8
end_key = 8 + cozulen_len_k

okunan_key_bytes = tam_veri[start:end_key]
okunan_val_bytes = tam_veri[end_key : end_key + cozulen_len_v]

sonuc_key = okunan_key_bytes.decode("utf-8")
sonuc_val = okunan_val_bytes.decode("utf-8")

print(f"Sonuc: Anahtar: {sonuc_key}, deger = {sonuc_val}")
