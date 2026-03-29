# Kat Layout ve Ölçüler (Tek Kat)

Bu doküman, depodaki tek bir katın (MZN1-MZN6 için ortak geometri) yerleşimini ve boyutlarını özetler.
Kaynak: src/utils/layoutConstants.js

## 1. Temel Ölçüler

| Parametre | Değer (m) | Açıklama |
|---|---:|---|
| AISLE_WIDTH | 1.36 | Koridor genişliği |
| COLUMN_LENGTH | 2.90 | Bir sütunun boyu (Y ekseni boyunca) |
| SHELF_DEPTH | 1.16 | Raf derinliği |
| CROSS_AISLE_WIDTH | 2.70 | Cross aisle genişliği |
| TOTAL_AISLES | 27 | Toplam koridor sayısı |
| TOTAL_COLUMNS | 20 | Toplam sütun sayısı |

## 2. Türetilmiş Ölçüler

- Koridor adımı (bir koridordan diğerine merkezden merkeze):
  - aisle pitch = AISLE_WIDTH + 2 * SHELF_DEPTH = 1.36 + 2 * 1.16 = 3.68 m
- Kat toplam genişliği (X):
  - LAYOUT_WIDTH = SHELF_DEPTH + AISLE_WIDTH + (TOTAL_AISLES - 1) * (AISLE_WIDTH + 2 * SHELF_DEPTH) + SHELF_DEPTH
  - LAYOUT_WIDTH = 1.16 + 1.36 + 26 * 3.68 + 1.16 = 99.36 m
- Kat toplam yüksekliği (Y):
  - LAYOUT_HEIGHT = CROSS_AISLE_WIDTH + 10 * COLUMN_LENGTH + CROSS_AISLE_WIDTH + 10 * COLUMN_LENGTH + CROSS_AISLE_WIDTH
  - LAYOUT_HEIGHT = 2.70 + 29.00 + 2.70 + 29.00 + 2.70 = 66.10 m

## 3. Y Ekseninde Bölgelendirme

Y ekseni yukarıdan aşağı doğru düşünülerek:

| Bölge | Y aralığı (m) | Açıklama |
|---|---|---|
| Cross Aisle 1 | 0.00 - 2.70 | Üst cross aisle |
| Column 1-10 bandı | 2.70 - 31.70 | İlk 10 sütun |
| Cross Aisle 2 | 31.70 - 34.40 | Orta cross aisle |
| Column 11-20 bandı | 34.40 - 63.40 | Son 10 sütun |
| Cross Aisle 3 | 63.40 - 66.10 | Alt cross aisle |

Cross aisle merkez Y noktaları:

- CROSS_AISLE_1_Y = 1.35 m
- CROSS_AISLE_2_Y = 33.05 m
- CROSS_AISLE_3_Y = 64.75 m

## 4. X Ekseninde Koridor Yerleşimi

Uygulamada görsel indeks ters çevrilir:

- Görselde AISLE 27 solda, AISLE 1 sağdadır.
- getReversedAisleIndex(aisle) = TOTAL_AISLES - aisle + 1

Koridor merkez X formülü:

- aisle1_center = SHELF_DEPTH + AISLE_WIDTH / 2 = 1.84 m
- x(aisle) = aisle1_center + (reversedAisle - 1) * 3.68

Örnek:

- AISLE 27 merkezi: x = 1.84 m (en sol)
- AISLE 1 merkezi: x = 97.52 m (en sağ)

## 5. Sütun Merkez Koordinatları

Sütun merkezleri iki bantta hesaplanır:

- column <= 10:
  - y = CROSS_AISLE_WIDTH + (column - 0.5) * COLUMN_LENGTH
- column > 10:
  - y = (CROSS_AISLE_WIDTH + 10 * COLUMN_LENGTH) + CROSS_AISLE_WIDTH + (column - 10 - 0.5) * COLUMN_LENGTH

Örnek Y merkezleri:

- Column 1: y = 4.15 m
- Column 10: y = 30.25 m
- Column 11: y = 35.85 m
- Column 20: y = 61.95 m

## 6. Asansör Konumları (CA1 Dışı)

Asansörler Cross Aisle 1'in dışında (üstte) konumludur:

| Asansör | Aisle hizası | X (m) | Y (m) |
|---|---:|---:|---:|
| Elevator 1 | 8 | getXCoordinate(8) | -0.75 |
| Elevator 2 | 18 | getXCoordinate(18) | -0.75 |

Not: ELEVATOR_DEPTH = 1.5 m, bu yüzden merkez Y = -ELEVATOR_DEPTH / 2.

## 7. Merdiven Konumları

| Stair | Aisle aralığı | Cross aisle |
|---|---|---:|
| S1 | 5-6 | 1 |
| S2 | 15-16 | 1 |
| S3 | 24-25 | 1 |
| S4 | 9-10 | 2 |
| S5 | 19-20 | 2 |
| S6 | 4-5 | 3 |
| S7 | 14-15 | 3 |
| S8 | 23-24 | 3 |

Merdiven X merkezi, ilgili iki koridor merkezinin ortalamasıdır.
Merdiven Y noktası, ilgili cross aisle sınırında shelf bitişiğine yerleştirilir.

## 8. Bir Lokasyonun Merkez Koordinatı

Bir toplama lokasyonu (aisle, column) için merkez:

- x = getXCoordinate(aisle)
- y = getYCoordinate(column)

Bu koordinatlar, görselleştirme ve Manhattan mesafe hesabının temelini oluşturur.

## 9. Basit ASCII Şema (Ölçeksiz)

```text
Y=0.00
+-------------------------------------------------------------+
|                    CROSS AISLE 1 (2.70 m)                   |
+-------------------------------------------------------------+
|                                                             |
|                 COLUMN 1..10 BANDI (29.00 m)               |
|                                                             |
+-------------------------------------------------------------+
|                    CROSS AISLE 2 (2.70 m)                   |
+-------------------------------------------------------------+
|                                                             |
|                COLUMN 11..20 BANDI (29.00 m)               |
|                                                             |
+-------------------------------------------------------------+
|                    CROSS AISLE 3 (2.70 m)                   |
+-------------------------------------------------------------+
Y=66.10

X yönünde: 27 koridor, pitch = 3.68 m, toplam genişlik = 99.36 m
```

## 10. Uygulama Notu

Tüm katlar aynı geometriyi kullanır. Fark, operasyonel erişim kuralındadır:

- MZN1-MZN3: merdiven tabanlı erişim
- MZN4-MZN6: asansör/pickcar tabanlı erişim

Geometri sabit, giriş stratejisi değişkendir.