/**
 * Dil çevirileri
 */
export const translations = {
  tr: {
    // Header
    appTitle: 'Depo Simülasyonu',
    
    // Upload Section
    uploadTitle: 'Excel veya CSV dosyasını buraya sürükleyin veya tıklayarak seçin',
    uploadHint: 'Sadece .xlsx, .xls ve .csv uzantılı dosyalar desteklenir',
    loadTestData: 'Test Verisi Yükle',
    uploadedFile: 'Yüklenen dosya',
    
    // Messages
    testDataLoaded: 'Test verisi yüklendi (6255 satır, önceden dönüştürülmüş)',
    testDataName: 'Test Verisi (Gömülü)',
    sheetNotFound: 'isimli sayfa bulunamadı. Mevcut sayfalar',
    missingColumns: 'Eksik kolonlar',
    rowsRead: 'satır okundu, dönüştürülüyor...',
    conversionComplete: 'Dönüşüm tamamlandı!',
    conversionError: 'Dönüştürme hatası',
    excelReadError: 'Excel okuma hatası',
    fileReadError: 'Dosya okunamadı',
    excelDownloaded: 'Excel dosyası indirildi',
    reset: 'Sıfırlandı',
    
    // Progress stages
    stageTransform: 'Satırlar dönüştürülüyor...',
    stageFilter: 'MZN areaları filtreleniyor...',
    stageGroup: 'Toplama grupları oluşturuluyor...',
    stageOrder: 'Sıralama ve mesafe hesaplanıyor...',
    stageComplete: 'Tamamlandı!',
    
    // Stats
    totalRows: 'Toplam Satır',
    mznRows: 'MZN Satırları',
    pickGroups: 'Toplama Grubu',
    totalDistance: 'Toplam Mesafe',
    
    // Buttons
    downloadExcel: 'Excel İndir',
    visualize: 'Görselleştir',
    hideVisualization: 'Görselleştirmeyi Kapat',
    resetBtn: 'Sıfırla',
    
    // Table columns
    colPicker: 'PICKER',
    colPickcar: 'PICKCAR',
    colDate: 'TARİH',
    colTime: 'SAAT',
    colArea: 'ALAN',
    colAisle: 'KORİDOR',
    colColumn: 'SÜTUN',
    colShelf: 'RAF',
    colLR: 'L/R',
    colOrder: 'SIRA',
    colStep: 'ADIM',
    colTotal: 'TOPLAM',
    
    // Selected group table
    selectedGroupTitle: 'Seçili Toplama Grubu Verileri',
    rows: 'satır',
    
    // Footer
    footerText: 'Oğuz Alp Çakmak | ODTÜ ©2026',
    
    // PickVisualizer
    filterMultiFloor: 'Birden fazla kata giden grupları gizle',
    filterNoTime: 'Eksik TIME verisi olan grupları gizle',
    filteredGroups: 'grup filtrelendi',
    noTimeFiltered: 'eksik TIME grubu filtrelendi',
    fullscreen: 'Tam Ekran',
    normalView: 'Normal',
    pickerLabel: 'Toplayıcı (PICKER_CODE)',
    pickcarLabel: 'Araba (PICKCAR_THM)',
    selectPlaceholder: 'Seçiniz...',
    step: 'Adım',
    speed: 'Hız (ms)',
    speedSlow: 'Yavaş (2s)',
    speedNormal: 'Normal (1s)',
    speedFast: 'Hızlı (0.5s)',
    speedVeryFast: 'Çok Hızlı (0.2s)',
    goToStart: 'Başa Dön',
    previous: 'Önceki',
    play: 'Oynat',
    pause: 'Duraklat',
    next: 'Sonraki',
    goToEnd: 'Sona Git',
    
    // Pick info
    infoOrder: 'Sıra',
    infoTime: 'Zaman',
    infoArea: 'Alan',
    infoLocation: 'Konum',
    infoShelf: 'Raf',
    infoStepDist: 'Adım Mesafe',
    infoTotalDist: 'Toplam Mesafe',
    infoProduct: 'Ürün',
    infoElevator: 'Asansör',
    infoStair: 'Merdiven',
    returnToElevator: 'Asansöre Dönüş',
    startAtElevator: 'Başlangıç (Asansör)',
    returnToStair: 'Merdivene Dönüş',
    startAtStair: 'Başlangıç (Merdiven)',
    
    // Legend
    legendShelf: 'Raf',
    legendAisle: 'Koridor (AISLE)',
    legendCrossAisle: 'Cross Aisle',
    legendElevator: 'Asansör',
    legendStair: 'Merdiven',
    legendShelfLeft: 'Sol Raf (L)',
    legendShelfRight: 'Sağ Raf (R)',
    legendCurrent: 'Mevcut Konum',
    legendTrail: 'Geçmiş Adımlar',
    
    // Stock Processing
    stockRowsRead: 'stok satırı okundu',
    stockProcessed: 'Stok verisi işlendi ve güncellendi',
    stockExcelDownloaded: 'Güncellenmiş stok dosyası indirildi',
    downloadStockExcel: 'Stok Excel İndir',
    stockStatsTitle: 'Stok İstatistikleri',
    originalStock: 'Orijinal Stok',
    updatedItems: 'Güncellenen',
    newStockItems: 'Yeni Eklenen',
    totalAddedBack: 'Toplam Eklenen',
    units: 'adet',
  },
  
  en: {
    // Header
    appTitle: 'Warehouse Simulation',
    
    // Upload Section
    uploadTitle: 'Drag and drop an Excel or CSV file here or click to select',
    uploadHint: 'Only .xlsx, .xls, and .csv files are supported',
    loadTestData: 'Load Test Data',
    uploadedFile: 'Uploaded file',
    
    // Messages
    testDataLoaded: 'Test data loaded (6255 rows, pre-processed)',
    testDataName: 'Test Data (Embedded)',
    sheetNotFound: 'sheet not found. Available sheets',
    missingColumns: 'Missing columns',
    rowsRead: 'rows read, processing...',
    conversionComplete: 'Conversion complete!',
    conversionError: 'Conversion error',
    excelReadError: 'Excel reading error',
    fileReadError: 'Could not read file',
    excelDownloaded: 'Excel file downloaded',
    reset: 'Reset complete',
    
    // Progress stages
    stageTransform: 'Transforming rows...',
    stageFilter: 'Filtering MZN areas...',
    stageGroup: 'Creating pick groups...',
    stageOrder: 'Calculating order and distance...',
    stageComplete: 'Complete!',
    
    // Stats
    totalRows: 'Total Rows',
    mznRows: 'MZN Rows',
    pickGroups: 'Pick Groups',
    totalDistance: 'Total Distance',
    
    // Buttons
    downloadExcel: 'Download Excel',
    visualize: 'Visualize',
    hideVisualization: 'Hide Visualization',
    resetBtn: 'Reset',
    
    // Table columns
    colPicker: 'PICKER',
    colPickcar: 'PICKCAR',
    colDate: 'DATE',
    colTime: 'TIME',
    colArea: 'AREA',
    colAisle: 'AISLE',
    colColumn: 'COLUMN',
    colShelf: 'SHELF',
    colLR: 'L/R',
    colOrder: 'ORDER',
    colStep: 'STEP',
    colTotal: 'TOTAL',
    
    // Selected group table
    selectedGroupTitle: 'Selected Pick Group Data',
    rows: 'rows',
    
    // Footer
    footerText: 'Oğuz Alp Çakmak | METU ©2026',
    
    // PickVisualizer
    filterMultiFloor: 'Hide multi-floor groups',
    filterNoTime: 'Hide groups with missing TIME data',
    filteredGroups: 'groups filtered',
    noTimeFiltered: 'missing TIME groups filtered',
    fullscreen: 'Fullscreen',
    normalView: 'Normal',
    pickerLabel: 'Picker (PICKER_CODE)',
    pickcarLabel: 'Cart (PICKCAR_THM)',
    selectPlaceholder: 'Select...',
    step: 'Step',
    speed: 'Speed (ms)',
    speedSlow: 'Slow (2s)',
    speedNormal: 'Normal (1s)',
    speedFast: 'Fast (0.5s)',
    speedVeryFast: 'Very Fast (0.2s)',
    goToStart: 'Go to Start',
    previous: 'Previous',
    play: 'Play',
    pause: 'Pause',
    next: 'Next',
    goToEnd: 'Go to End',
    
    // Pick info
    infoOrder: 'Order',
    infoTime: 'Time',
    infoArea: 'Area',
    infoLocation: 'Location',
    infoShelf: 'Shelf',
    infoStepDist: 'Step Distance',
    infoTotalDist: 'Total Distance',
    infoProduct: 'Product',
    infoElevator: 'Elevator',
    infoStair: 'Stair',
    returnToElevator: 'Return to Elevator',
    startAtElevator: 'Start (Elevator)',
    returnToStair: 'Return to Stair',
    startAtStair: 'Start (Stair)',
    
    // Legend
    legendShelf: 'Shelf',
    legendAisle: 'Aisle',
    legendCrossAisle: 'Cross Aisle',
    legendElevator: 'Elevator',
    legendStair: 'Stair',
    legendShelfLeft: 'Left Shelf (L)',
    legendShelfRight: 'Right Shelf (R)',
    legendCurrent: 'Current Position',
    legendTrail: 'Past Steps',
    
    // Stock Processing
    stockRowsRead: 'stock rows read',
    stockProcessed: 'Stock data processed and updated',
    stockExcelDownloaded: 'Updated stock file downloaded',
    downloadStockExcel: 'Download Stock Excel',
    stockStatsTitle: 'Stock Statistics',
    originalStock: 'Original Stock',
    updatedItems: 'Updated',
    newStockItems: 'Newly Added',
    totalAddedBack: 'Total Added',
    units: 'units',
  }
};

/**
 * Çeviri fonksiyonu
 * @param {string} lang - Dil kodu ('tr' veya 'en')
 * @param {string} key - Çeviri anahtarı
 * @returns {string} Çevrilmiş metin
 */
export function t(lang, key) {
  return translations[lang]?.[key] || translations.tr[key] || key;
}
