# Regret Algoritması Nedir?

Bu doküman, projedeki **regret-based heuristic** yaklaşımını basit Türkçe ile açıklar.

## Kısa fikir

Regret algoritması, her ürün için sadece "şu an en iyi seçim hangisi?" diye bakmaz.

Bunun yanında şunu da düşünür:

- Eğer bu ürünü şimdi en iyi yerden almazsam,
- sonra mecburen daha kötü bir yerden almak zorunda kalır mıyım?

İşte **regret (pişmanlık)** değeri, bu farkı anlatır.

Basitçe:

- **En iyi seçenek çok iyi**,
- **ikinci en iyi seçenek çok kötü** ise,
- o ürünü erken seçmek mantıklıdır.

Çünkü beklersen ileride "pişmanlık" büyüyebilir.

---

## Günlük hayattan benzetme

Diyelim ki markettesin:

- Bir ürünün sana çok yakın bir rafta son 1 kutusu var.
- Aynı ürünün başka bir rafta da alternatifi var ama çok uzakta.

Bu durumda yakın olanı önce almak mantıklı olur.

Neden?

Çünkü yakın olan fırsatı kaçırırsan sonra uzak rafı kullanmak zorunda kalırsın.
Bu da ekstra yürüyüş maliyeti demektir.

Regret yaklaşımı tam olarak buna bakar.

---

## Bu projede ne yapıyor?

Bu projede amaç sadece ürünü bulmak değil. Aynı zamanda şu maliyetleri de düşük tutmak:

- **toplam mesafe**
- **açılan THM sayısı**
- **kullanılan kat sayısı**

Yani algoritma şuna bakıyor:

> Bu ürünü hangi lokasyondan alırsam toplam plan daha iyi olur?

Burada her aday lokasyon için yaklaşık bir maliyet hesaplanıyor.
Sonra ürünler arasında öncelik belirleniyor.

---

## Adım adım basit çalışma mantığı

### 1. Ürünleri sırala

Önce ürünler önem sırasına konur.
Bu sıralamada genelde şunlar öne çıkar:

- az sayıda uygun lokasyonu olan ürünler
- en iyi ve ikinci en iyi seçeneği arasında büyük fark olan ürünler

Yani alternatifleri zayıf olan ürünler önce ele alınır.

### 2. Seçilecek ürünü al

Sıradaki ürün için ihtiyaç miktarı kadar stok aranır.

### 3. En iyi lokasyonu seç

Aday lokasyonlar arasında şu tip etkiler değerlendirilir:

- mesafeyi ne kadar artırıyor?
- yeni bir THM açıyor mu?
- yeni bir kat açıyor mu?
- mevcut rotayı bozuyor mu?

En düşük ek maliyeti veren seçim tercih edilir.

### 4. Miktarı yerleştir

Ürünün ihtiyacı bitene kadar uygun lokasyonlardan toplama yapılır.

### 5. Rotaları yeniden kur

Tüm seçimler bittikten sonra kat bazında rota daha düzgün hale getirilir.

---

## “Regret” neden faydalı?

Normal greedy yaklaşım bazen sadece o anki en ucuz karara bakar.
Bu kısa vadede iyi görünür ama ileride kötü sonuç verebilir.

Regret yaklaşımı ise biraz daha ileriye dönük düşünür:

- "Şimdi bunu çözmezsem sonra daha pahalıya patlar mı?"

Bu yüzden özellikle şu durumlarda işe yarar:

- alternatif lokasyonlar çok farklı kalitedeyse
- bazı ürünlerin iyi seçenekleri çok sınırlıysa
- erken yanlış seçim ileride mesafeyi veya THM sayısını büyütüyorsa

---

## Avantajları

- Basit greedy’den daha akıllıdır.
- Genelde hızlı çalışır.
- Büyük veri setlerinde pratik sonuç verir.
- Mesafe + THM + kat gibi birleşik hedeflerle uyumlu çalışabilir.

---

## Dezavantajları

- Yine de tam optimumu garanti etmez.
- İlk kararlar sonraki kararları etkilediği için bazen yerel olarak iyi ama global olarak zayıf sonuç verebilir.
- Eğer sadece yapıcı (constructive) kalırsa, sonradan iyileştirme araması olmayan yöntemlere göre sınırlı kalabilir.

---

## Bu projedeki sürümün özeti

Projede kullanılan regret tabanlı yöntem şu fikre yakın çalışır:

1. Ürünleri statik bir regret önceliğine göre sırala.
2. Her ürün için o anki duruma göre en düşük marjinal maliyetli lokasyonu seç.
3. Gerekirse aynı ürün için birden fazla lokasyondan toplama yap.
4. En sonda rotayı yeniden optimize et.

Yani yöntem tamamen rastgele değil;
**deterministic, hızlı ve tekrarlanabilir** bir yapıdadır.

---

## Tek cümlede özet

**Regret algoritması, ileride kötü bir seçime mecbur kalmamak için bugün kritik ürünleri önce ve daha dikkatli seçen bir sezgiseldir.**
