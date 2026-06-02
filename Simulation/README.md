# 🏭 Depo Simülasyonu / Warehouse Simulation

[🇹🇷 Türkçe](#-türkçe) | [🇬🇧 English](#-english)

Buradan Deneyebilirsiniz / Try Here:
[Warehouse Simulation](https://oguzalpcakmak.github.io/warehouse-simulation/)

---

## 🇹🇷 Türkçe

Toplama süreci verilerini kullanarak depo içi toplama süreçlerini görselleştiren bir web uygulaması. Bu uygulama, ODTÜ Sistem Tasarımı dersi dönem projesi kapsamında geliştirilmiştir.

![React](https://img.shields.io/badge/React-18.2.0-61DAFB?logo=react)
![Vite](https://img.shields.io/badge/Vite-5.0.0-646CFF?logo=vite)
![Ant Design](https://img.shields.io/badge/Ant%20Design-6.2.3-0170FE?logo=antdesign)

### 📋 Özellikler

- 📊 **Excel Dosyası Desteği**: `.xlsx` ve `.xls` formatındaki dosyaları okuyabilir
- 🗺️ **Depo Layout Görselleştirmesi**: 27 koridor x 20 sütunluk depo haritası
- 🚶 **Rota Animasyonu**: Toplama rotalarını adım adım izleyebilme
- 📈 **İstatistikler**: Toplam mesafe, grup sayısı, satır sayısı
- 🌙 **Karanlık/Aydınlık Tema**: Göz yormayan arayüz seçenekleri
- 🌐 **Çoklu Dil Desteği**: Türkçe ve İngilizce
- ⬇️ **Excel Çıktısı**: İşlenmiş verileri Excel formatında indirebilme
- 🧪 **Test Verisi**: Hızlı test için gömülü örnek veri
- ⚙️ **Seçilebilir Solver Modları**: Client-side WASM veya native server çözümünü seçebilme

### 🏗️ Depo Layout Parametreleri

| Parametre | Değer | Açıklama |
|-----------|-------|----------|
| Koridor Genişliği | 1.36m | Aisle width |
| Raf Sütunu Uzunluğu | 2.90m | Column length |
| Raf Derinliği | 1.16m | Shelf depth |
| Cross Aisle Genişliği | 2.70m | Cross aisle width |
| Toplam Koridor | 27 | Total aisles |
| Toplam Sütun | 20 | Total columns |

### 📥 Excel Dosyası Formatı

Yüklenen Excel dosyasında **"Grup Toplama Verisi"** isimli bir sayfa (sheet) bulunmalıdır.
WASM solver çalıştırmak için aynı dosyada ayrıca **"Stok Bilgisi"** sheet'i bulunmalıdır.

#### Gerekli Kolonlar

| Kolon Adı | Açıklama |
|-----------|----------|
| `Kullanıcı Kodu` | Toplama yapan personel kodu |
| `PICKCAR_THM` | Toplama arabası THM numarası |
| `TOPLANAN_THM` | Toplanan ürün THM numarası |
| `ARTICLE_CODE` | Ürün kodu |
| `DATE_START_EXECUTION` | İşlem başlangıç tarihi/saati |
| `AREA` | Alan kodu (MZN1-MZN6) |
| `AISLE` | Koridor numarası (1-27) |
| `X` | Sütun numarası (1-20) |
| `Y` | Raf numarası |
| `Z` | Sol/Sağ (L/R) |
| `TOPLANAN_ADET` | Toplanan adet |

#### WASM Solver Stok Sheet Kolonları

| Kolon Adı | Açıklama |
|-----------|----------|
| `THM_ID` | Stok THM numarası |
| `ARTICLE_CODE` | Ürün kodu |
| `ACT_AREA` | Alan kodu (MZN1-MZN6) |
| `ACT_AISLE` | Koridor numarası |
| `ACT_X` | Sütun numarası |
| `ACT_Y` | Raf numarası |
| `ACT_Z` | Sol/Sağ (L/R) |
| `Stok` | Mevcut stok |

### 🚀 Kurulum

#### Gereksinimler

- Node.js 18+
- npm veya yarn
- Emscripten SDK (`~/.local/share/emsdk` veya `EMSDK_DIR`)

#### Adımlar

```bash
# Repoyu klonlayın
git clone https://github.com/oguzalpcakmak/WarehouseSimulation.git

# Proje dizinine gidin
cd WarehouseSimulation

# Bağımlılıkları yükleyin
npm install

# Geliştirme sunucusunu başlatın
npm run dev
```

Uygulama varsayılan olarak `http://localhost:5173` adresinde çalışacaktır.

#### Client-side WASM solver ile çalıştırma

```bash
npm run wasm:sync
npm run dev
```

UI, Excel workbook'ünü client-side modlarda bir Web Worker'a aktarır. Worker solver input
CSV'lerini hazırlar ve seçime göre LKH'siz ana modülü veya ayrı `lkh.wasm` modülünü çalıştırır;
çözüm sırasında ana UI thread'i kullanılabilir kalır. Server-side modlar için native API akışını
`npm run api` komutuyla başlatın.

Dropdown dört çözüm modu sunar:

- `Client-side LKH'li`
- `Client-side LKH'siz`
- `Server-side kaliteli çözüm`
- `Server-side hızlı çözüm`

`npm run build`, WASM asset'lerini otomatik olarak yeniden üretip `public/wasm` altına kopyalar.
Lokal smoke Excel'i `npm run fixture:wasm`, full stres Excel'i ise `npm run fixture:wasm:full`
komutuyla yeniden üretilebilir.

#### Production feature flag ve deploy

LKH'nin repo içindeki lisans notu araştırma kullanımıyla sınırlıdır. Redistribüsyon izni
onaylanmadan production build'i şu şekilde alın:

```bash
VITE_ENABLE_CLIENT_LKH=false npm run build
```

Bu flag dropdown'daki client-side LKH seçeneğini kapatır ve `lkh.mjs/lkh.wasm` asset'lerini
production bundle'dan çıkarır. Onay sonrası `VITE_ENABLE_CLIENT_LKH=true npm run build`
kullanılabilir. Örnek production ayarı `.env.production.example` dosyasındadır.

Worker çıktısındaki runtime metadata; toplam süreyi, seed-route optimizer modunu, LKH instance
hazırlama süresini, LKH çözüm süresini ve çözülen kat sayısını içerir. Server yanıtı da native
request süresini döndürür. Production hata takibi bu metadata ve `[solver-worker]` logları
üzerinden izleme sistemine aktarılabilir.

### 📦 Üretim Derlemesi

```bash
# Üretim için derleyin
npm run build

# Derlemeyi önizleyin
npm run preview
```

### 📖 Kullanım

1. **Excel Yükleme**: Ana sayfada Excel dosyanızı sürükle-bırak veya tıklayarak yükleyin
2. **Otomatik İşleme**: Dosya yüklendikten sonra otomatik olarak işlenir
3. **Görselleştirme**: İşlenen veriler harita üzerinde görselleştirilir
4. **Grup Seçimi**: Sol panelden picker ve pickcar seçerek grupları filtreleyin
5. **Animasyon**: Play/Pause butonlarıyla toplama rotasını izleyin
6. **İndirme**: İşlenmiş verileri Excel formatında indirin

---

## 🇬🇧 English

A web application that visualizes warehouse picking processes using picking data. This application was developed as part of the METU Systems Design course term project.

![React](https://img.shields.io/badge/React-18.2.0-61DAFB?logo=react)
![Vite](https://img.shields.io/badge/Vite-5.0.0-646CFF?logo=vite)
![Ant Design](https://img.shields.io/badge/Ant%20Design-6.2.3-0170FE?logo=antdesign)

### 📋 Features

- 📊 **Excel File Support**: Can read `.xlsx` and `.xls` format files
- 🗺️ **Warehouse Layout Visualization**: 27 aisles x 20 columns warehouse map
- 🚶 **Route Animation**: Step-by-step picking route visualization
- 📈 **Statistics**: Total distance, group count, row count
- 🌙 **Dark/Light Theme**: Eye-friendly interface options
- 🌐 **Multi-language Support**: Turkish and English
- ⬇️ **Excel Export**: Download processed data in Excel format
- 🧪 **Test Data**: Embedded sample data for quick testing
- ⚙️ **Selectable Solver Modes**: Choose client-side WASM or native server execution

### 🏗️ Warehouse Layout Parameters

| Parameter | Value | Description |
|-----------|-------|-------------|
| Aisle Width | 1.36m | Space between shelves |
| Column Length | 2.90m | Shelf column length |
| Shelf Depth | 1.16m | Shelf depth |
| Cross Aisle Width | 2.70m | Cross aisle width |
| Total Aisles | 27 | Number of aisles |
| Total Columns | 20 | Number of columns |

### 📥 Excel File Format

The uploaded Excel file must contain a sheet named **"Grup Toplama Verisi"**.
Running the WASM solver also requires a **"Stok Bilgisi"** sheet in the same workbook.

#### Required Columns

| Column Name | Description |
|-------------|-------------|
| `Kullanıcı Kodu` | Picker personnel code |
| `PICKCAR_THM` | Pick cart THM number |
| `TOPLANAN_THM` | Picked product THM number |
| `ARTICLE_CODE` | Product code |
| `DATE_START_EXECUTION` | Execution start date/time |
| `AREA` | Area code (MZN1-MZN6) |
| `AISLE` | Aisle number (1-27) |
| `X` | Column number (1-20) |
| `Y` | Shelf number |
| `Z` | Left/Right (L/R) |
| `TOPLANAN_ADET` | Picked quantity |

#### WASM Solver Stock Sheet Columns

| Column Name | Description |
|-------------|-------------|
| `THM_ID` | Stock THM id |
| `ARTICLE_CODE` | Product code |
| `ACT_AREA` | Area code (MZN1-MZN6) |
| `ACT_AISLE` | Aisle number |
| `ACT_X` | Column number |
| `ACT_Y` | Shelf number |
| `ACT_Z` | Left/Right (L/R) |
| `Stok` | Available stock |

### 🚀 Installation

#### Requirements

- Node.js 18+
- npm or yarn
- Emscripten SDK (`~/.local/share/emsdk` or `EMSDK_DIR`)

#### Steps

```bash
# Clone the repository
git clone https://github.com/oguzalpcakmak/WarehouseSimulation.git

# Navigate to project directory
cd WarehouseSimulation

# Install dependencies
npm install

# Start development server
npm run dev
```

The application will run at `http://localhost:5173` by default.

#### Running with the client-side WASM solver

```bash
npm run wasm:sync
npm run dev
```

In client-side modes, the UI transfers the Excel workbook to a Web Worker. The worker prepares
the solver input CSVs and runs either the LKH-free main module or the separate `lkh.wasm` module
while the main UI thread stays responsive. Start the native API with `npm run api` for server-side
modes. The dropdown exposes client-side with LKH, client-side without LKH, server-side quality,
and server-side fast modes. `npm run build` regenerates the WASM assets and copies them under
`public/wasm` automatically.
Regenerate the local smoke Excel with `npm run fixture:wasm`, or the full stress Excel with
`npm run fixture:wasm:full`.

#### Production feature flag and deployment

The bundled LKH license note restricts its use to research. Until redistribution permission is
confirmed, build production assets with:

```bash
VITE_ENABLE_CLIENT_LKH=false npm run build
```

This disables the client-side LKH dropdown option and omits `lkh.mjs/lkh.wasm` from the
production bundle. Runtime metadata contains the selected optimizer and timing breakdown for
performance monitoring. Forward worker error logs and server errors to the production
observability platform.

### 📦 Production Build

```bash
# Build for production
npm run build

# Preview the build
npm run preview
```

### 📖 Usage

1. **Upload Excel**: Drag and drop or click to upload your Excel file on the main page
2. **Automatic Processing**: The file is automatically processed after upload
3. **Visualization**: Processed data is visualized on the warehouse map
4. **Group Selection**: Filter groups by selecting picker and pickcar from the left panel
5. **Animation**: Watch the picking route with Play/Pause buttons
6. **Download**: Download processed data in Excel format

---

## 🛠️ Technologies / Teknolojiler

- **React 18** - UI library / UI kütüphanesi
- **Vite** - Build tool
- **Ant Design 6** - UI component library / UI bileşen kütüphanesi
- **XLSX** - Excel file read/write / Excel dosyası okuma/yazma
- **Canvas API** - Warehouse visualization / Depo görselleştirmesi

## 📁 Project Structure / Proje Yapısı

```
WarehouseSimulation/
├── public/
│   └── favicon.svg
├── src/
│   ├── components/
│   │   ├── PickVisualizer.jsx    # Warehouse visualization component
│   │   └── PickVisualizer.css
│   ├── data/
│   │   └── testData.json         # Sample test data
│   ├── locales/
│   │   └── translations.js       # Language translations
│   ├── utils/
│   │   ├── excelProcessor.js     # Excel processing functions
│   │   └── layoutConstants.js    # Warehouse layout constants
│   ├── App.jsx                   # Main application component
│   ├── main.jsx                  # React entry point
│   └── index.css                 # Global styles
├── server/
│   └── index.js                  # C++ solver API
├── index.html
├── package.json
└── vite.config.js
```

## 👨‍💻 Developer / Geliştirici

**Oğuz Alp Çakmak** - METU / ODTÜ

## 📄 License / Lisans

This project is licensed under the MIT License. / Bu proje MIT lisansı altında lisanslanmıştır.
