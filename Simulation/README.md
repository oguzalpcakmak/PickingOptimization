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

### 🚀 Kurulum

#### Gereksinimler

- Node.js 18+
- npm veya yarn

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

### 🚀 Installation

#### Requirements

- Node.js 18+
- npm or yarn

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
├── index.html
├── package.json
└── vite.config.js
```

## 👨‍💻 Developer / Geliştirici

**Oğuz Alp Çakmak** - METU / ODTÜ

## 📄 License / Lisans

This project is licensed under the MIT License. / Bu proje MIT lisansı altında lisanslanmıştır.
