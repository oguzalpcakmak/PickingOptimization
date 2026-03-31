# GRASP Multi-Start Yaklaşımı: Türkçe Açıklama

Bu doküman, depodaki toplama problemi için eklenen `grasp_heuristic.py` yaklaşımının ne yaptığını, neden işe yaradığını ve kodda nasıl uygulandığını ayrıntılı ama pratik bir dille açıklar.

## 1. Temel Fikir

GRASP, `Greedy Randomized Adaptive Search Procedure` ifadesinin kısaltmasıdır.

Bu yaklaşımın özü şudur:

1. Tamamen rastgele bir çözüm üretmez.
2. Tamamen deterministik bir açgözlü çözümle de yetinmez.
3. "En iyi adaylar" arasından kontrollü rastgele seçimler yapar.
4. Bunu birden fazla kez tekrarlar.
5. En iyi bulunan çözümü saklar.

Bu yüzden GRASP, "tek bir hızlı açgözlü çözüm" ile "daha pahalı ama daha kaliteli çoklu deneme" arasında iyi bir dengedir.

## 2. Neden Bu Problem İçin Uygun?

Bizim problemimizde aynı ürünü karşılayabilecek birden fazla lokasyon olabilir. Ayrıca bir lokasyonun iyi olup olmaması sadece stok miktarına bağlı değildir.

Bir lokasyon seçildiğinde şu etkiler oluşur:

- Yeni bir THM açılabilir.
- Yeni bir kata girilmiş olabilir.
- Mevcut rota uzayabilir.
- Aynı düğüm veya aynı THM tekrar kullanılıyorsa maliyet daha düşük kalabilir.

Bu nedenle "en yakın lokasyonu seç" gibi basit kurallar çoğu zaman yeterli olmaz. GRASP burada iyi çalışır, çünkü her adımda:

- maliyeti düşük adaylara öncelik verir,
- ama tek bir yola kilitlenmez,
- farklı kombinasyonları deneyerek daha iyi global çözümler bulabilir.

## 3. Kullandığımız Amaç Fonksiyonu

Kodda kullanılan değerlendirme exact modele mümkün olduğunca yakın tutuldu:

```text
Amaç = distance_weight * toplam_mesafe
     + thm_weight * açılan_thm_sayısı
     + floor_weight * kullanılan_kat_sayısı
```

Varsayılan ağırlıklar:

- `distance_weight = 1.0`
- `thm_weight = 15.0`
- `floor_weight = 30.0`

Benchmark sırasında karşılaştırma için bazen şu değerler de kullanıldı:

- `distance_weight = 1`
- `thm_weight = 1`
- `floor_weight = 1`

Bu yapı sayesinde çözüm sadece mesafeyi değil, operasyonel maliyetleri de dikkate alır.

## 4. Algoritmanın Genel Akışı

`grasp_heuristic.py` içindeki akış yüksek seviyede şöyledir:

1. Sipariş ve stok verilerini oku.
2. İlgili ürünleri ve katları filtrele.
3. Ürünler için bir temel öncelik sırası üret.
4. Çoklu başlatma döngüsünü çalıştır.
5. Her iterasyonda bir çözüm kur.
6. Kurulan çözüm için rotaları iyileştir.
7. En iyi çözümü sakla.

Bu akışın önemli tarafı şudur:

- Kurulum aşaması hızlıdır.
- Her iterasyon bağımsızdır.
- Daha uzun süre verirseniz daha iyi çözüm bulma ihtimali artar.

## 5. "Multi-Start" Ne Demek?

Multi-start, aynı problemi birden fazla kez farklı başlangıç kararlarıyla çözmek demektir.

Tek bir deterministik açgözlü yöntem:

- aynı girdi için hep aynı çözümü üretir,
- ilk yapılan seçimler kötü ise sonuca mahkum kalabilir.

GRASP multi-start ise:

- ilk iterasyonda güçlü bir deterministik başlangıç kullanır,
- sonraki iterasyonlarda kontrollü rastgelelik ekler,
- farklı çözüm bölgelerini tarar,
- en iyi bulunan çözümde karar kılar.

Bizim implementasyonda:

- `1. iterasyon` bir `elite seed` olarak deterministiktir.
- Sonraki iterasyonlar `RCL` üzerinden rastgele seçim içerir.

Bu sayede algoritma, en azından deterministik baseline'dan daha kötü başlamaz.

## 6. Ürün Sıralaması Nasıl Yapılıyor?

Önce ürünler için bir temel zorluk sırası hesaplanır.

Kullanılan fikir:

- az sayıda aday lokasyonu olan ürünler daha zordur,
- az sayıda katta bulunan ürünler daha kritiktir,
- en iyi ve ikinci en iyi aday arasındaki fark büyükse ürün daha risklidir,
- talebi yüksek ürünlerin yanlış yönetilmesi daha maliyetli olabilir.

Bu yüzden ürünler, yaklaşık olarak şu mantıkla sıralanır:

1. Daha az adaylı ürün önce
2. Daha az kat alternatifi olan ürün önce
3. Regret değeri yüksek ürün önce
4. Daha dar stok esnekliği olan ürün önce

Buradaki `regret`, en iyi seçenek ile ikinci en iyi seçenek arasındaki farktır.

Bu çok önemlidir. Çünkü bir ürün için tek iyi seçenek varsa, o kararı erken almak gerekir.

## 7. Aday Lokasyon Skoru Nasıl Hesaplanıyor?

Her ürün için bir lokasyon seçmeden önce her aday lokasyonun marjinal etkisi hesaplanır.

Bir lokasyonun açılmasının etkileri:

- rotaya ne kadar ek mesafe getiriyor,
- yeni bir THM mi açıyor,
- yeni bir kat mı açıyor,
- yeni bir fiziksel düğüm mü ekliyor,
- o lokasyondan ne kadar miktar toplanabiliyor.

Bu nedenle adaylar için aşağıdaki türde bir skor hesaplanır:

```text
marginal_cost =
    distance_weight * route_delta
  + thm_weight      * yeni_thm_maliyeti
  + floor_weight    * yeni_kat_maliyeti
```

Sonra bu maliyet, alınabilecek miktara bölünerek birim maliyete çevrilir:

```text
unit_cost = marginal_cost / alınabilecek_miktar
```

Bu çok güçlü bir sezgiseldir. Çünkü:

- aynı THM içindeki iyi lokasyonlar doğal olarak öne çıkar,
- mevcut rotaya yakın lokasyonlar avantajlı olur,
- küçük miktar için büyük operasyonel ceza getiren lokasyonlar geriye düşer.

## 8. RCL Nedir?

RCL, `Restricted Candidate List` demektir.

Mantık şu:

- tüm adayları sırala,
- sadece en iyi birkaç tanesini al,
- seçimi bunların içinden yap.

Yani algoritma tamamen rastgele değildir.
Sadece "makul derecede iyi" adaylar arasından rastgele seçim yapar.

Bu, iki fayda sağlar:

1. Kötü çözümlere düşme riski azalır.
2. Tek bir açgözlü karara kilitlenme engellenir.

Bizim implementasyonda iki seviyede RCL vardır:

- ürün seçimi için,
- lokasyon seçimi için.

## 9. `alpha` Parametresi Ne İşe Yarıyor?

`alpha`, RCL genişliğini kontrol eder.

Kısaca:

- `alpha = 0` ise davranış neredeyse tamamen açgözlü olur.
- `alpha` büyüdükçe rastgelelik artar.

Kodda eşik mantığı şöyle çalışır:

```text
threshold = best_cost + alpha * (worst_cost - best_cost)
```

Bu eşik altında kalan adaylar RCL'ye girer.

Pratik yorum:

- küçük `alpha`: daha stabil, daha deterministik
- orta `alpha`: kalite/çeşitlilik dengesi
- büyük `alpha`: daha fazla çeşitlilik, bazen daha oynak sonuç

Varsayılan değer:

- `alpha = 0.25`

Bu genelde iyi bir orta noktadır.

## 10. Ürün ve Lokasyon İçin Ayrı RCL Boyutları

Kodda ayrıca iki ayrı sınır vardır:

- `article_rcl_size`
- `location_rcl_size`

### `article_rcl_size`

Bir sonraki ürün, öncelik sırasındaki ilk birkaç ürün arasından seçilir.

Örnek:

- değer `6` ise algoritma öncelik listesindeki ilk 6 üründen birini seçebilir.

Bu, "zor ürünler önce" mantığını tamamen bozmadan kontrollü çeşitlilik sağlar.

### `location_rcl_size`

Bir ürün için lokasyon seçerken, sadece en iyi birkaç lokasyon arasından rastgele seçim yapılır.

Bu da çözüm çeşitliliğini arttırır.

Varsayılanlar:

- `article_rcl_size = 6`
- `location_rcl_size = 5`

## 11. Adaptiflik Nerede?

GRASP'ın ortasındaki `Adaptive` kelimesi önemlidir.

Algoritma sabit bir skor tablosuna göre gitmez. Her seçimden sonra durum değişir:

- hangi THM'ler açık,
- hangi katlar aktif,
- rota hangi düğümlerden geçiyor,
- kalan stok ne kadar,
- kalan talep ne kadar.

Dolayısıyla aynı lokasyon, çözümün başında pahalı olabilirken sonunda çok ucuz hale gelebilir.

Bu yüzden skorlar her adımda yeniden hesaplanır.

## 12. Rota Nasıl Hesaplanıyor?

Seçim aşamasında rota tam çözülmez ama artımsal olarak izlenir.

Lokasyon eklendiğinde:

- eğer düğüm zaten rotadaysa rota maliyeti artmaz,
- yeni düğümse en iyi ekleme noktasına bakılır,
- o düğümün marjinal rota etkisi (`route_delta`) hesaplanır.

Bu sayede kurulum aşaması hızlı kalır.

Çözüm tamamlandıktan sonra her kat için rota iyileştirilir:

1. Regret-insertion tabanlı kurulum
2. 2-opt ile yerel iyileştirme

Bu iki aşama:

- hızlıdır,
- pratikte iyi rotalar üretir,
- exact çözüme yaklaşan sonuçlar verebilir.

## 13. Neden İlk İterasyon Deterministik?

Kodda ilk iterasyon özellikle deterministik tutuldu.

Buna dokümanda `elite seed` diyebiliriz.

Avantajları:

- Algoritma en azından iyi bir baseline ile başlar.
- Rastgele iterasyonlar kötü kalsa bile başlangıç çözümü korunur.
- Multi-start yapının "en kötü ihtimali" iyileşir.

Bu yüzden ilk iterasyonda:

- ürün seçimi rastgele değil,
- lokasyon seçimi rastgele değil,
- doğrudan en iyi aday seçilir.

Sonraki iterasyonlar ise keşif yapar.

## 14. Durma Kriterleri

Algoritma iki ana sınırla kontrol edilir:

- `iterations`
- `time_limit`

Yani:

- maksimum kaç iterasyon çalışacağı,
- toplamda kaç saniye arayacağı belirlenebilir.

Pratik davranış:

- küçük örneklerde çok iterasyon rahatça çalışır,
- büyük örneklerde tek iterasyon bile anlamlı maliyetli olabilir,
- bu yüzden zaman bütçesi çoğu durumda daha önemli kontroldür.

## 15. Neden Bu Yaklaşım İyi Sonuç Verdi?

25 ürün / 3 kat benchmark'ında bu yaklaşım iyi performans verdi çünkü:

- THM ve kat açma cezasını doğrudan skorun içine koyuyor,
- rota etkisini seçim anında hesaba katıyor,
- tek bir açgözlü karar zincirine kilitlenmiyor,
- çok kısa süre içinde çok sayıda alternatif kurabiliyor,
- ilk iyi çözümü koruyup daha iyisini arayabiliyor.

Bu yüzden:

- mevcut eski heuristiğe göre belirgin şekilde daha iyi,
- deterministik regret heuristic'ten de daha iyi,
- exact çözüme nispeten yakın sonuç verebiliyor.

## 16. Güçlü Yanları

- Çok esnek
- Hızlı
- Parametrelenebilir
- Büyük problemlerde pratik
- Exact modele yakın bir maliyet mantığı kullanıyor
- Tek bir çözüm yerine çözüm ailesi tarıyor

## 17. Zayıf Yanları

- Global optimum garantisi vermez
- Parametre seçimi kaliteyi etkiler
- Çok büyük örneklerde tek iterasyon bile pahalı olabilir
- RCL çok dar olursa çeşitlilik azalır
- RCL çok geniş olursa kalite düşebilir

## 18. Deterministik Regret Heuristic ile Farkı

`regret_based_heuristic.py`:

- deterministiktir,
- hep aynı çözümü üretir,
- çok hızlıdır,
- iyi bir baseline'dır.

`grasp_heuristic.py`:

- aynı skor mantığını kullanır,
- ama rastgele kontrollü seçimlerle farklı çözüm bölgelerini tarar,
- biraz daha uzun sürer,
- genelde daha iyi çözüm bulur.

Kısacası:

- regret heuristic = hızlı ve stabil
- GRASP = biraz daha pahalı ama daha güçlü arama

## 19. Kod İçindeki Ana Parametreler

`grasp_heuristic.py` dosyasında öne çıkan CLI parametreleri:

- `--iterations`
- `--time-limit`
- `--alpha`
- `--article-rcl-size`
- `--location-rcl-size`
- `--seed`
- `--distance-weight`
- `--thm-weight`
- `--floor-weight`

Örnek kullanım:

```bash
.venv/bin/python grasp_heuristic.py \
  --orders 25item3floor/PickOrder.csv \
  --stock 25item3floor/StockData.csv \
  --floors MZN1,MZN2,MZN3 \
  --articles 567,577,606,609,699,788,791,866,977,993,997,999,1019,1020,1030,1051,1055,1061,1066,1068,1087,1088,1093,1118,1122 \
  --distance-weight 1 \
  --thm-weight 1 \
  --floor-weight 1 \
  --iterations 100 \
  --time-limit 5
```

## 20. Parametre Ayarı İçin Pratik Öneri

Başlangıç için şu aralıklar mantıklıdır:

- `alpha`: `0.15 - 0.35`
- `article_rcl_size`: `4 - 8`
- `location_rcl_size`: `3 - 6`

Pratik ayar yaklaşımı:

1. Önce `time_limit` belirlenir.
2. Sonra `alpha` ile keşif seviyesi ayarlanır.
3. Sonra RCL boyutları çözüm çeşitliliğine göre büyütülür veya küçültülür.

Eğer çözüm çok stabil ama zayıfsa:

- `alpha` biraz artırılabilir,
- `location_rcl_size` biraz artırılabilir.

Eğer çözüm çok oynaksa:

- `alpha` düşürülebilir,
- RCL daraltılabilir.

## 21. Kısa Özet

Bu projedeki GRASP multi-start yaklaşımı şunu yapar:

- iyi adayları açgözlü biçimde tanımlar,
- kötü adayları dışarıda bırakır,
- iyi adaylar arasından kontrollü rastgele seçim yapar,
- bunu birçok kez tekrarlar,
- rota kalitesini yerel iyileştirmeyle güçlendirir,
- en iyi çözümü döndürür.

Bu nedenle, depo toplama problemi gibi:

- kombinatoryel olarak büyük,
- yerel kararların global etki yaptığı,
- exact çözümün pahalı olabildiği

durumlarda çok uygun bir pratiktir.

## 22. İlgili Dosyalar

- Ana implementasyon: `grasp_heuristic.py`
- Ortak yardımcılar: `heuristic_common.py`
- Deterministik baseline: `regret_based_heuristic.py`
- Benchmark karşılaştırması: `25item3floor/BENCHMARK_COMPARISON.md`

