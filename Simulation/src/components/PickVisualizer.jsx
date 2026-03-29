import { useState, useEffect, useMemo, useRef, useCallback } from 'react';
import { Button, Tooltip, Checkbox } from 'antd';
import {
  StepBackwardOutlined,
  StepForwardOutlined,
  FastBackwardOutlined,
  FastForwardOutlined,
  PlayCircleOutlined,
  PauseCircleOutlined
} from '@ant-design/icons';
import {
  AISLE_WIDTH,
  COLUMN_LENGTH,
  SHELF_DEPTH,
  CROSS_AISLE_WIDTH,
  TOTAL_AISLES,
  TOTAL_COLUMNS,
  LAYOUT_WIDTH,
  LAYOUT_HEIGHT,
  CROSS_AISLE_1_Y,
  CROSS_AISLE_2_Y,
  CROSS_AISLE_3_Y,
  getXCoordinate,
  getYCoordinate,
  getManhattanPath,
  getReversedAisleIndex,
  ELEVATOR_1_AISLE,
  ELEVATOR_2_AISLE,
  ELEVATOR_WIDTH,
  ELEVATOR_DEPTH,
  getNearestElevator,
  STAIRS,
  STAIR_WIDTH,
  STAIR_DEPTH,
  getStairPosition
} from '../utils/layoutConstants.js';
import { t } from '../locales/translations.js';
import './PickVisualizer.css';

function PickVisualizer({ data, isDarkMode = true, onGroupSelect, lang = 'tr' }) {
  const [selectedPicker, setSelectedPicker] = useState('');
  const [selectedPickcar, setSelectedPickcar] = useState('');
  const [currentStep, setCurrentStep] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [playSpeed, setPlaySpeed] = useState(1000);
  const [scale, setScale] = useState(1);
  const [filterSingleFloor, setFilterSingleFloor] = useState(true);
  const [filterHasNoTime, setFilterHasNoTime] = useState(true);
  const containerRef = useRef(null);

  // Birden fazla kata giden grupları tespit et
  const multiFloorGroups = useMemo(() => {
    const groups = {};
    
    data.forEach(row => {
      // START, RETURN ve STAIR satırlarını hariç tut
      if (row.IS_START || row.IS_RETURN || row.IS_STAIR_START || row.IS_STAIR_RETURN) return;
      
      const key = `${row.PICKER_CODE}|${row.PICKCAR_THM}`;
      if (!groups[key]) {
        groups[key] = new Set();
      }
      groups[key].add(row.AREA);
    });
    
    // Birden fazla AREA'ya sahip grupları döndür
    return new Set(
      Object.entries(groups)
        .filter(([, areas]) => areas.size > 1)
        .map(([key]) => key)
    );
  }, [data]);

  // TIME verisi eksik olan grupları tespit et
  const noTimeGroups = useMemo(() => {
    const groups = {};
    
    data.forEach(row => {
      // START, RETURN ve STAIR satırlarını TIME kontrolünden hariç tut
      if (row.IS_START || row.IS_RETURN || row.IS_STAIR_START || row.IS_STAIR_RETURN) return;
      
      const key = `${row.PICKER_CODE}|${row.PICKCAR_THM}`;
      if (!groups[key]) {
        groups[key] = { hasNoTime: false };
      }
      // TIME boş, undefined veya null ise işaretle
      if (!row.TIME || row.TIME === '' || row.TIME === '-') {
        groups[key].hasNoTime = true;
      }
    });
    
    // TIME verisi eksik olan grupları döndür
    return new Set(
      Object.entries(groups)
        .filter(([, info]) => info.hasNoTime)
        .map(([key]) => key)
    );
  }, [data]);

  const [isFullscreen, setIsFullscreen] = useState(false);

  // Container boyutuna göre scale hesapla
  const calculateScale = useCallback(() => {
    if (!containerRef.current) return;
    
    const container = containerRef.current;
    const availableWidth = container.clientWidth - 32; // padding için
    
    // rem to px dönüşümü (1rem = 16px varsayımı)
    const remToPx = parseFloat(getComputedStyle(document.documentElement).fontSize);
    const layoutWidthPx = LAYOUT_WIDTH * remToPx;
    const layoutHeightPx = LAYOUT_HEIGHT * remToPx;
    
    if (isFullscreen) {
      // Fullscreen modda sadece width'e göre fit
      const newScale = availableWidth / layoutWidthPx;
      setScale(Math.max(0.1, newScale));
    } else {
      // Normal modda hem width hem height'a göre fit
      const availableHeight = window.innerHeight * 0.6;
      const scaleX = availableWidth / layoutWidthPx;
      const scaleY = availableHeight / layoutHeightPx;
      const newScale = Math.min(scaleX, scaleY);
      setScale(Math.max(0.1, newScale));
    }
  }, [isFullscreen]);

  // İlk yükleme ve resize olaylarında scale hesapla
  useEffect(() => {
    calculateScale();
    window.addEventListener('resize', calculateScale);
    return () => window.removeEventListener('resize', calculateScale);
  }, [calculateScale]);

  // Benzersiz PICKER_CODE'ları al (filtreye göre)
  const pickerCodes = useMemo(() => {
    console.log('=== pickerCodes hesaplanıyor ===');
    console.log('data length:', data.length);
    console.log('data sample:', data.slice(0, 3));
    
    // START, RETURN ve STAIR satırlarını hariç tut
    let filteredData = data.filter(row => 
      !row.IS_START && !row.IS_RETURN && !row.IS_STAIR_START && !row.IS_STAIR_RETURN
    );
    
    if (filterSingleFloor) {
      // Sadece tek katta kalan grupların picker'larını al
      filteredData = filteredData.filter(row => {
        const key = `${row.PICKER_CODE}|${row.PICKCAR_THM}`;
        return !multiFloorGroups.has(key);
      });
    }
    
    if (filterHasNoTime) {
      // TIME verisi tam olan grupların picker'larını al
      filteredData = filteredData.filter(row => {
        const key = `${row.PICKER_CODE}|${row.PICKCAR_THM}`;
        return !noTimeGroups.has(key);
      });
    }
    
    console.log('filteredData length:', filteredData.length);
    const codes = [...new Set(filteredData.map(row => row.PICKER_CODE))];
    console.log('pickerCodes:', codes);
    return codes.sort();
  }, [data, filterSingleFloor, filterHasNoTime, multiFloorGroups, noTimeGroups]);

  // Seçili picker için PICKCAR_THM'leri al (filtreye göre)
  const pickcarCodes = useMemo(() => {
    if (!selectedPicker) return [];
    
    // START, RETURN ve STAIR satırlarını hariç tut
    let filteredData = data.filter(row => 
      row.PICKER_CODE === selectedPicker && 
      !row.IS_START && !row.IS_RETURN && !row.IS_STAIR_START && !row.IS_STAIR_RETURN
    );
    
    if (filterSingleFloor) {
      filteredData = filteredData.filter(row => {
        const key = `${row.PICKER_CODE}|${row.PICKCAR_THM}`;
        return !multiFloorGroups.has(key);
      });
    }
    
    if (filterHasNoTime) {
      filteredData = filteredData.filter(row => {
        const key = `${row.PICKER_CODE}|${row.PICKCAR_THM}`;
        return !noTimeGroups.has(key);
      });
    }
    
    const codes = [...new Set(filteredData.map(row => row.PICKCAR_THM))];
    return codes.sort();
  }, [data, selectedPicker, filterSingleFloor, filterHasNoTime, multiFloorGroups, noTimeGroups]);

  // Seçili toplama işleminin verileri
  const pickData = useMemo(() => {
    if (!selectedPicker || !selectedPickcar) return [];
    return data
      .filter(row => row.PICKER_CODE === selectedPicker && row.PICKCAR_THM === selectedPickcar)
      .sort((a, b) => (a.PICK_ORDER || 0) - (b.PICK_ORDER || 0));
  }, [data, selectedPicker, selectedPickcar]);

  // Notify parent when selected group changes
  useEffect(() => {
    if (onGroupSelect) {
      onGroupSelect(pickData, currentStep);
    }
  }, [pickData, currentStep, onGroupSelect]);

  // Mevcut adımdaki pick
  const currentPick = pickData[currentStep] || null;

  // Çizgi çizmek için tüm adımlar (currentStep dahil)
  const pathPicks = pickData.slice(0, currentStep + 1);

  // Picker seçildiğinde pickcar'ı sıfırla
  useEffect(() => {
    setSelectedPickcar('');
    setCurrentStep(0);
    setIsPlaying(false);
  }, [selectedPicker]);

  // Pickcar seçildiğinde step'i sıfırla
  useEffect(() => {
    setCurrentStep(0);
    setIsPlaying(false);
  }, [selectedPickcar]);

  // Otomatik oynatma
  useEffect(() => {
    if (!isPlaying || !pickData.length) return;

    const timer = setInterval(() => {
      setCurrentStep(prev => {
        if (prev >= pickData.length - 1) {
          setIsPlaying(false);
          return prev;
        }
        return prev + 1;
      });
    }, playSpeed);

    return () => clearInterval(timer);
  }, [isPlaying, pickData.length, playSpeed]);

  // Raf gruplarını oluştur (AISLE 27 solda, AISLE 1 sağda)
  const shelves = useMemo(() => {
    const items = [];
    
    // Her AISLE için raflar
    for (let aisle = 1; aisle <= TOTAL_AISLES; aisle++) {
      // Görsel index (AISLE 27 = 1, AISLE 1 = 27)
      const visualIndex = getReversedAisleIndex(aisle);
      
      // Sol taraf rafları (AISLE 27 en solda)
      if (aisle === TOTAL_AISLES) {
        // AISLE 27 sol = tek sıra (en sol)
        for (let col = 1; col <= 20; col++) {
          if (col <= 10) {
            items.push({
              type: 'shelf',
              aisle,
              column: col,
              side: 'L',
              x: 0,
              y: CROSS_AISLE_WIDTH + (col - 1) * COLUMN_LENGTH,
              width: SHELF_DEPTH,
              height: COLUMN_LENGTH
            });
          } else {
            items.push({
              type: 'shelf',
              aisle,
              column: col,
              side: 'L',
              x: 0,
              y: CROSS_AISLE_WIDTH + 10 * COLUMN_LENGTH + CROSS_AISLE_WIDTH + (col - 11) * COLUMN_LENGTH,
              width: SHELF_DEPTH,
              height: COLUMN_LENGTH
            });
          }
        }
      }
      
      // Orta raflar (AISLE 2-27 arası)
      if (aisle > 1) {
        const shelfX = SHELF_DEPTH + AISLE_WIDTH + (visualIndex - 1) * (AISLE_WIDTH + 2 * SHELF_DEPTH);
        for (let col = 1; col <= 20; col++) {
          let y;
          if (col <= 10) {
            y = CROSS_AISLE_WIDTH + (col - 1) * COLUMN_LENGTH;
          } else {
            y = CROSS_AISLE_WIDTH + 10 * COLUMN_LENGTH + CROSS_AISLE_WIDTH + (col - 11) * COLUMN_LENGTH;
          }
          // Sol yarı (AISLE N'in R tarafı)
          items.push({
            type: 'shelf',
            aisle,
            column: col,
            side: 'R',
            x: shelfX,
            y,
            width: SHELF_DEPTH,
            height: COLUMN_LENGTH
          });
          // Sağ yarı (AISLE N-1'in L tarafı)
          items.push({
            type: 'shelf',
            aisle: aisle - 1,
            column: col,
            side: 'L',
            x: shelfX + SHELF_DEPTH,
            y,
            width: SHELF_DEPTH,
            height: COLUMN_LENGTH
          });
        }
      }
      
      // AISLE 1 sağ = tek sıra (en sağ)
      if (aisle === 1) {
        const shelfX = SHELF_DEPTH + AISLE_WIDTH + (visualIndex - 1) * (AISLE_WIDTH + 2 * SHELF_DEPTH);
        for (let col = 1; col <= 20; col++) {
          let y;
          if (col <= 10) {
            y = CROSS_AISLE_WIDTH + (col - 1) * COLUMN_LENGTH;
          } else {
            y = CROSS_AISLE_WIDTH + 10 * COLUMN_LENGTH + CROSS_AISLE_WIDTH + (col - 11) * COLUMN_LENGTH;
          }
          items.push({
            type: 'shelf',
            aisle,
            column: col,
            side: 'R',
            x: shelfX,
            y,
            width: SHELF_DEPTH,
            height: COLUMN_LENGTH
          });
        }
      }
    }
    
    return items;
  }, []);

  // Koridorları oluştur (AISLE 27 solda, AISLE 1 sağda)
  const aisles = useMemo(() => {
    const items = [];
    for (let aisle = 1; aisle <= TOTAL_AISLES; aisle++) {
      const visualIndex = getReversedAisleIndex(aisle);
      const x = SHELF_DEPTH + (visualIndex - 1) * (AISLE_WIDTH + 2 * SHELF_DEPTH);
      
      // Üst kısım (COLUMN 1-10)
      items.push({
        type: 'aisle',
        aisle,
        section: 'top',
        x,
        y: CROSS_AISLE_WIDTH,
        width: AISLE_WIDTH,
        height: 10 * COLUMN_LENGTH
      });
      
      // Alt kısım (COLUMN 11-20)
      items.push({
        type: 'aisle',
        aisle,
        section: 'bottom',
        x,
        y: CROSS_AISLE_WIDTH + 10 * COLUMN_LENGTH + CROSS_AISLE_WIDTH,
        width: AISLE_WIDTH,
        height: 10 * COLUMN_LENGTH
      });
    }
    return items;
  }, []);

  // Cross aisle'ları oluştur
  const crossAisles = useMemo(() => {
    return [
      {
        name: 'CROSS_AISLE_1',
        x: 0,
        y: 0,
        width: LAYOUT_WIDTH,
        height: CROSS_AISLE_WIDTH
      },
      {
        name: 'CROSS_AISLE_2',
        x: 0,
        y: CROSS_AISLE_WIDTH + 10 * COLUMN_LENGTH,
        width: LAYOUT_WIDTH,
        height: CROSS_AISLE_WIDTH
      },
      {
        name: 'CROSS_AISLE_3',
        x: 0,
        y: CROSS_AISLE_WIDTH + 10 * COLUMN_LENGTH + CROSS_AISLE_WIDTH + 10 * COLUMN_LENGTH,
        width: LAYOUT_WIDTH,
        height: CROSS_AISLE_WIDTH
      }
    ];
  }, []);

  // Asansörleri oluştur (Cross Aisle 1'in dışına bitişik)
  const elevators = useMemo(() => {
    return [
      {
        id: 1,
        aisle: ELEVATOR_1_AISLE,
        x: getXCoordinate(ELEVATOR_1_AISLE) - ELEVATOR_WIDTH / 2,
        y: -ELEVATOR_DEPTH,  // Cross aisle 1'in üstünde (dışında)
        width: ELEVATOR_WIDTH,
        height: ELEVATOR_DEPTH
      },
      {
        id: 2,
        aisle: ELEVATOR_2_AISLE,
        x: getXCoordinate(ELEVATOR_2_AISLE) - ELEVATOR_WIDTH / 2,
        y: -ELEVATOR_DEPTH,
        width: ELEVATOR_WIDTH,
        height: ELEVATOR_DEPTH
      }
    ];
  }, []);

  // Merdivenleri oluştur
  const stairs = useMemo(() => {
    return STAIRS.map(stair => {
      const pos = getStairPosition(stair.id);
      return {
        id: stair.id,
        x: pos.x - STAIR_WIDTH / 2,
        y: pos.crossAisle === 1 ? pos.y : pos.y - STAIR_DEPTH,  // CA1: altında, CA2: üstünde
        width: STAIR_WIDTH,
        height: STAIR_DEPTH,
        crossAisle: stair.crossAisle
      };
    });
  }, []);

  // Aktif asansörü belirle
  const activeElevator = useMemo(() => {
    if (pickData.length === 0) return null;
    
    // Mevcut adım asansör başlangıç satırı ise
    if (currentPick?.IS_START) {
      return currentPick.ELEVATOR_NUM;
    }
    
    // Mevcut adım asansör dönüş satırı ise
    if (currentPick?.IS_RETURN) {
      return currentPick.ELEVATOR_NUM;
    }
    
    // Merdiven satırlarında ilgili asansörü göster
    if (currentPick?.IS_STAIR_START || currentPick?.IS_STAIR_RETURN) {
      return currentPick.ELEVATOR_NUM;
    }
    
    // İlk satır merdiven ise, onun asansörünü göster
    const stairStartRow = pickData.find(p => p.IS_STAIR_START);
    if (stairStartRow) {
      return stairStartRow.ELEVATOR_NUM;
    }
    
    return null;
  }, [pickData, currentPick]);

  // Aktif merdiveni belirle
  const activeStair = useMemo(() => {
    if (pickData.length === 0) return null;
    
    // Mevcut adım merdiven başlangıç satırı ise
    if (currentPick?.IS_STAIR_START) {
      return currentPick.STAIR_NUM;
    }
    
    // Mevcut adım merdiven dönüş satırı ise
    if (currentPick?.IS_STAIR_RETURN) {
      return currentPick.STAIR_NUM;
    }
    
    // İlk satır merdiven ise, onu göster
    const stairStartRow = pickData.find(p => p.IS_STAIR_START);
    if (stairStartRow) {
      return stairStartRow.STAIR_NUM;
    }
    
    return null;
  }, [pickData, currentPick]);

  return (
    <div className={`pick-visualizer ${isDarkMode ? 'dark-mode' : 'light-mode'}`}>
      <div className="visualizer-controls">
        <div className="control-group filter-toggle">
          <Checkbox
            checked={filterSingleFloor}
            onChange={(e) => {
              setFilterSingleFloor(e.target.checked);
              setSelectedPicker('');
              setSelectedPickcar('');
            }}
          >
            {t(lang, 'filterMultiFloor')}
          </Checkbox>
          <span className="filter-info">
            ({multiFloorGroups.size} {t(lang, 'filteredGroups')})
          </span>
          <Checkbox
            checked={filterHasNoTime}
            onChange={(e) => setFilterHasNoTime(e.target.checked)}
          >
            {t(lang, 'filterNoTime')}
          </Checkbox>
          <span className="filter-info">
            ({noTimeGroups.size} {t(lang, 'noTimeFiltered')})
          </span>
          <button 
            className={`fullscreen-button ${isFullscreen ? 'active' : ''}`}
            onClick={() => setIsFullscreen(!isFullscreen)}
            title={isFullscreen ? t(lang, 'normalView') : t(lang, 'fullscreen')}
          >
            {isFullscreen ? '⊟' : '⊞'} {isFullscreen ? t(lang, 'normalView') : t(lang, 'fullscreen')}
          </button>
        </div>

        <div className="control-group">
          <label>{t(lang, 'pickerLabel')}</label>
          <select 
            value={selectedPicker} 
            onChange={(e) => setSelectedPicker(e.target.value)}
          >
            <option value="">{t(lang, 'selectPlaceholder')}</option>
            {pickerCodes.map(code => (
              <option key={code} value={code}>{code}</option>
            ))}
          </select>
        </div>

        <div className="control-group">
          <label>{t(lang, 'pickcarLabel')}</label>
          <select 
            value={selectedPickcar} 
            onChange={(e) => setSelectedPickcar(e.target.value)}
            disabled={!selectedPicker}
          >
            <option value="">{t(lang, 'selectPlaceholder')}</option>
            {pickcarCodes.map(code => (
              <option key={code} value={code}>{code}</option>
            ))}
          </select>
        </div>

        {pickData.length > 0 && (
          <>
            <div className="control-group">
              <label>{t(lang, 'step')}: {currentStep + 1} / {pickData.length}</label>
              <input
                type="range"
                min="0"
                max={pickData.length - 1}
                value={currentStep}
                onChange={(e) => setCurrentStep(parseInt(e.target.value))}
              />
            </div>

            <div className="control-group">
              <label>{t(lang, 'speed')}</label>
              <select value={playSpeed} onChange={(e) => setPlaySpeed(parseInt(e.target.value))}>
                <option value="2000">{t(lang, 'speedSlow')}</option>
                <option value="1000">{t(lang, 'speedNormal')}</option>
                <option value="500">{t(lang, 'speedFast')}</option>
                <option value="200">{t(lang, 'speedVeryFast')}</option>
              </select>
            </div>

            <div className="control-buttons">
              <Tooltip title={t(lang, 'goToStart')}>
                <Button 
                  icon={<FastBackwardOutlined />} 
                  onClick={() => setCurrentStep(0)}
                />
              </Tooltip>
              <Tooltip title={t(lang, 'previous')}>
                <Button 
                  icon={<StepBackwardOutlined />} 
                  onClick={() => setCurrentStep(Math.max(0, currentStep - 1))}
                />
              </Tooltip>
              <Tooltip title={isPlaying ? t(lang, 'pause') : t(lang, 'play')}>
                <Button 
                  type="primary"
                  icon={isPlaying ? <PauseCircleOutlined /> : <PlayCircleOutlined />} 
                  onClick={() => setIsPlaying(!isPlaying)}
                />
              </Tooltip>
              <Tooltip title={t(lang, 'next')}>
                <Button 
                  icon={<StepForwardOutlined />} 
                  onClick={() => setCurrentStep(Math.min(pickData.length - 1, currentStep + 1))}
                />
              </Tooltip>
              <Tooltip title={t(lang, 'goToEnd')}>
                <Button 
                  icon={<FastForwardOutlined />} 
                  onClick={() => setCurrentStep(pickData.length - 1)}
                />
              </Tooltip>
            </div>
          </>
        )}
      </div>

      {/* Merdiven Başlangıç Info */}
      {currentPick && currentPick.IS_STAIR_START && (
        <div className="current-pick-info stair-info">
          <div className="info-grid">
            <div className="info-item">
              <span className="info-label">{t(lang, 'infoOrder')}</span>
              <span className="info-value">{t(lang, 'startAtStair')}</span>
            </div>
            <div className="info-item">
              <span className="info-label">{t(lang, 'infoStair')}</span>
              <span className="info-value">S{currentPick.STAIR_NUM}</span>
            </div>
            <div className="info-item">
              <span className="info-label">{t(lang, 'infoStepDist')}</span>
              <span className="info-value">{currentPick.STEP_DIST}m</span>
            </div>
            <div className="info-item">
              <span className="info-label">{t(lang, 'infoTotalDist')}</span>
              <span className="info-value">{currentPick.TOTAL_DIST}m</span>
            </div>
          </div>
        </div>
      )}

      {/* Asansör Başlangıç Info */}
      {currentPick && currentPick.IS_START && (
        <div className="current-pick-info start-info">
          <div className="info-grid">
            <div className="info-item">
              <span className="info-label">{t(lang, 'infoOrder')}</span>
              <span className="info-value">{t(lang, 'startAtElevator')}</span>
            </div>
            <div className="info-item">
              <span className="info-label">{t(lang, 'infoElevator')}</span>
              <span className="info-value">E{currentPick.ELEVATOR_NUM}</span>
            </div>
            <div className="info-item">
              <span className="info-label">{t(lang, 'infoStepDist')}</span>
              <span className="info-value">{currentPick.STEP_DIST}m</span>
            </div>
            <div className="info-item">
              <span className="info-label">{t(lang, 'infoTotalDist')}</span>
              <span className="info-value">{currentPick.TOTAL_DIST}m</span>
            </div>
          </div>
        </div>
      )}

      {/* Normal Pick Info */}
      {currentPick && !currentPick.IS_RETURN && !currentPick.IS_START && !currentPick.IS_STAIR_START && !currentPick.IS_STAIR_RETURN && (
        <div className="current-pick-info">
          <div className="info-grid">
            <div className="info-item">
              <span className="info-label">{t(lang, 'infoOrder')}</span>
              <span className="info-value">{currentPick.PICK_ORDER}</span>
            </div>
            <div className="info-item">
              <span className="info-label">{t(lang, 'infoTime')}</span>
              <span className="info-value">{currentPick.TIME || '-'}</span>
            </div>
            <div className="info-item">
              <span className="info-label">{t(lang, 'infoArea')}</span>
              <span className="info-value">{currentPick.AREA}</span>
            </div>
            <div className="info-item">
              <span className="info-label">{t(lang, 'infoLocation')}</span>
              <span className="info-value">
                A{currentPick.AISLE} C{currentPick.COLUMN} {currentPick.LEFT_OR_RIGHT}
              </span>
            </div>
            <div className="info-item">
              <span className="info-label">{t(lang, 'infoShelf')}</span>
              <span className="info-value">{currentPick.SHELF}</span>
            </div>
            <div className="info-item">
              <span className="info-label">{t(lang, 'infoStepDist')}</span>
              <span className="info-value">{currentPick.STEP_DIST}m</span>
            </div>
            <div className="info-item">
              <span className="info-label">{t(lang, 'infoTotalDist')}</span>
              <span className="info-value">{currentPick.TOTAL_DIST}m</span>
            </div>
            <div className="info-item">
              <span className="info-label">{t(lang, 'infoProduct')}</span>
              <span className="info-value">{currentPick.ARTICLE_CODE}</span>
            </div>
          </div>
        </div>
      )}

      {/* Asansör Dönüş Info */}
      {currentPick && currentPick.IS_RETURN && (
        <div className="current-pick-info return-info">
          <div className="info-grid">
            <div className="info-item">
              <span className="info-label">{t(lang, 'infoOrder')}</span>
              <span className="info-value">{t(lang, 'returnToElevator')}</span>
            </div>
            <div className="info-item">
              <span className="info-label">{t(lang, 'infoElevator')}</span>
              <span className="info-value">E{currentPick.ELEVATOR_NUM}</span>
            </div>
            <div className="info-item">
              <span className="info-label">{t(lang, 'infoStepDist')}</span>
              <span className="info-value">{currentPick.STEP_DIST}m</span>
            </div>
            <div className="info-item">
              <span className="info-label">{t(lang, 'infoTotalDist')}</span>
              <span className="info-value">{currentPick.TOTAL_DIST}m</span>
            </div>
          </div>
        </div>
      )}

      {/* Merdiven Dönüş Info */}
      {currentPick && currentPick.IS_STAIR_RETURN && (
        <div className="current-pick-info stair-return-info">
          <div className="info-grid">
            <div className="info-item">
              <span className="info-label">{t(lang, 'infoOrder')}</span>
              <span className="info-value">{t(lang, 'returnToStair')}</span>
            </div>
            <div className="info-item">
              <span className="info-label">{t(lang, 'infoStair')}</span>
              <span className="info-value">S{currentPick.STAIR_NUM}</span>
            </div>
            <div className="info-item">
              <span className="info-label">{t(lang, 'infoStepDist')}</span>
              <span className="info-value">{currentPick.STEP_DIST}m</span>
            </div>
            <div className="info-item">
              <span className="info-label">{t(lang, 'infoTotalDist')}</span>
              <span className="info-value">{currentPick.TOTAL_DIST}m</span>
            </div>
          </div>
        </div>
      )}

      <div className="layout-container" ref={containerRef}>
        <div 
          className="layout-wrapper"
          style={{
            width: `${LAYOUT_WIDTH * scale}rem`,
            height: `${(LAYOUT_HEIGHT + ELEVATOR_DEPTH) * scale}rem`
          }}
        >
          <div 
            className="layout"
            style={{
              width: `${LAYOUT_WIDTH}rem`,
              height: `${LAYOUT_HEIGHT}rem`,
              transform: `scale(${scale})`,
              transformOrigin: 'top left',
              marginTop: `${ELEVATOR_DEPTH * scale}rem`,
              overflow: 'visible'
            }}
          >
            {/* Cross Aisle'lar */}
            {crossAisles.map((ca, i) => (
              <div
                key={`ca-${i}`}
                className="cross-aisle"
                style={{
                  left: `${ca.x}rem`,
                  top: `${ca.y}rem`,
                  width: `${ca.width}rem`,
                  height: `${ca.height}rem`
                }}
              >
                <span className="cross-aisle-label">{ca.name}</span>
              </div>
            ))}

            {/* Asansörler */}
            {elevators.map((elevator) => (
              <div
                key={`elevator-${elevator.id}`}
                className={`elevator ${activeElevator === elevator.id ? 'elevator-active' : ''}`}
                style={{
                  left: `${elevator.x}rem`,
                  top: `${elevator.y}rem`,
                  width: `${elevator.width}rem`,
                  height: `${elevator.height}rem`
                }}
              >
                <span className="elevator-label">E{elevator.id}</span>
              </div>
            ))}

            {/* Merdivenler */}
            {stairs.map((stair) => (
              <div
                key={`stair-${stair.id}`}
                className={`stair ${activeStair === stair.id ? 'stair-active' : ''}`}
                style={{
                  left: `${stair.x}rem`,
                  top: `${stair.y}rem`,
                  width: `${stair.width}rem`,
                  height: `${stair.height}rem`
                }}
              >
                <span className="stair-label">S{stair.id}</span>
              </div>
            ))}

            {/* Koridorlar */}
            {aisles.map((aisle, i) => (
              <div
                key={`aisle-${i}`}
                className="aisle"
              style={{
                left: `${aisle.x}rem`,
                top: `${aisle.y}rem`,
                width: `${aisle.width}rem`,
                height: `${aisle.height}rem`
              }}
            >
              {aisle.section === 'top' && (
                <span className="aisle-label">{aisle.aisle}</span>
              )}
            </div>
          ))}

          {/* Raflar */}
          {shelves.map((shelf, i) => {
            // Koridorlar tersine döndüğü için L/R de ters: veri L → görsel R, veri R → görsel L
            const visualSide = currentPick?.LEFT_OR_RIGHT === 'L' ? 'R' : 'L';
            const isActive = currentPick && 
              shelf.aisle === parseInt(currentPick.AISLE) && 
              shelf.column === parseInt(currentPick.COLUMN) && 
              shelf.side === visualSide;
            
            return (
              <div
                key={`shelf-${i}`}
                className={`shelf ${isActive ? (shelf.side === 'L' ? 'shelf-active-left' : 'shelf-active-right') : ''}`}
                style={{
                  left: `${shelf.x}rem`,
                  top: `${shelf.y}rem`,
                  width: `${shelf.width}rem`,
                  height: `${shelf.height}rem`
                }}
              />
            );
          })}

          {/* Önceki adımların izi (normal pick'ler için) */}
          {pathPicks.slice(0, -1).filter(p => 
            !p.IS_RETURN && !p.IS_START && !p.IS_STAIR_START && !p.IS_STAIR_RETURN
          ).map((pick, i) => {
            const x = getXCoordinate(parseInt(pick.AISLE));
            const y = getYCoordinate(parseInt(pick.COLUMN));
            return (
              <div
                key={`trail-${i}`}
                className="pick-trail"
                style={{
                  left: `${x}rem`,
                  top: `${y}rem`
                }}
              >
                <span className="trail-order">{pick.PICK_ORDER}</span>
              </div>
            );
          })}

          {/* Önceki adımlar arası çizgiler (Manhattan path) */}
          {pathPicks.length >= 1 && (
            <svg 
              className="path-lines"
              viewBox={`0 0 ${LAYOUT_WIDTH} ${LAYOUT_HEIGHT + ELEVATOR_DEPTH}`}
              preserveAspectRatio="none"
              style={{
                width: `${LAYOUT_WIDTH}rem`,
                height: `${LAYOUT_HEIGHT + ELEVATOR_DEPTH}rem`,
                top: `${-ELEVATOR_DEPTH}rem`
              }}
            >
              {/* Pick'ler arası çizgiler */}
              {pathPicks.map((pick, i) => {
                if (i === 0) return null;
                const prevPick = pathPicks[i - 1];
                
                // Merdivenden asansöre çizgi (mor)
                if (prevPick.IS_STAIR_START && pick.IS_START) {
                  const stairPos = getStairPosition(prevPick.STAIR_NUM);
                  const elevatorX = getXCoordinate(pick.ELEVATOR_NUM === 1 ? ELEVATOR_1_AISLE : ELEVATOR_2_AISLE);
                  const elevatorY = ELEVATOR_DEPTH / 2;
                  
                  const pathPoints = [
                    { x: stairPos.x, y: stairPos.y + ELEVATOR_DEPTH },
                    { x: stairPos.x, y: CROSS_AISLE_WIDTH / 2 + ELEVATOR_DEPTH },
                    { x: elevatorX, y: CROSS_AISLE_WIDTH / 2 + ELEVATOR_DEPTH },
                    { x: elevatorX, y: elevatorY }
                  ];
                  
                  const pointsStr = pathPoints.map(p => `${p.x},${p.y}`).join(' ');
                  
                  return (
                    <polyline
                      key={`line-stair-elevator-${i}`}
                      points={pointsStr}
                      fill="none"
                      stroke="rgba(156, 39, 176, 0.7)"
                      strokeWidth="0.15"
                      strokeDasharray="0.3"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  );
                }
                
                // Asansörden ilk pick'e çizgi (sarı)
                if (prevPick.IS_START && !pick.IS_STAIR_START && !pick.IS_STAIR_RETURN) {
                  const elevatorX = getXCoordinate(prevPick.ELEVATOR_NUM === 1 ? ELEVATOR_1_AISLE : ELEVATOR_2_AISLE);
                  const elevatorY = ELEVATOR_DEPTH / 2;
                  const pickX = getXCoordinate(parseInt(pick.AISLE));
                  const pickY = getYCoordinate(parseInt(pick.COLUMN)) + ELEVATOR_DEPTH;
                  
                  // Asansörden cross aisle'a, oradan koridora, oradan hedef column'a
                  const pathPoints = [
                    { x: elevatorX, y: elevatorY },
                    { x: elevatorX, y: CROSS_AISLE_WIDTH / 2 + ELEVATOR_DEPTH },
                    { x: pickX, y: CROSS_AISLE_WIDTH / 2 + ELEVATOR_DEPTH },
                    { x: pickX, y: pickY }
                  ];
                  
                  const pointsStr = pathPoints.map(p => `${p.x},${p.y}`).join(' ');
                  
                  return (
                    <polyline
                      key={`line-start-${i}`}
                      points={pointsStr}
                      fill="none"
                      stroke="rgba(255, 193, 7, 0.7)"
                      strokeWidth="0.15"
                      strokeDasharray="0.3"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  );
                }
                
                // Dönüş satırı ise asansöre çizgi çiz (kırmızı)
                if (pick.IS_RETURN) {
                  const x1 = getXCoordinate(parseInt(prevPick.AISLE));
                  const y1 = getYCoordinate(parseInt(prevPick.COLUMN)) + ELEVATOR_DEPTH;
                  const elevatorX = getXCoordinate(pick.ELEVATOR_NUM === 1 ? ELEVATOR_1_AISLE : ELEVATOR_2_AISLE);
                  const elevatorY = ELEVATOR_DEPTH / 2;
                  
                  // Son pick'ten cross aisle'a, oradan asansöre
                  const pathPoints = [
                    { x: x1, y: y1 },
                    { x: x1, y: CROSS_AISLE_WIDTH / 2 + ELEVATOR_DEPTH },
                    { x: elevatorX, y: CROSS_AISLE_WIDTH / 2 + ELEVATOR_DEPTH },
                    { x: elevatorX, y: elevatorY }
                  ];
                  
                  const pointsStr = pathPoints.map(p => `${p.x},${p.y}`).join(' ');
                  
                  return (
                    <polyline
                      key={`line-return-${i}`}
                      points={pointsStr}
                      fill="none"
                      stroke="rgba(255, 100, 100, 0.7)"
                      strokeWidth="0.15"
                      strokeDasharray="0.3"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  );
                }
                
                // Asansörden merdivene dönüş çizgisi (mor)
                if (pick.IS_STAIR_RETURN && prevPick.IS_RETURN) {
                  const elevatorX = getXCoordinate(prevPick.ELEVATOR_NUM === 1 ? ELEVATOR_1_AISLE : ELEVATOR_2_AISLE);
                  const elevatorY = ELEVATOR_DEPTH / 2;
                  const stairPos = getStairPosition(pick.STAIR_NUM);
                  
                  const pathPoints = [
                    { x: elevatorX, y: elevatorY },
                    { x: elevatorX, y: CROSS_AISLE_WIDTH / 2 + ELEVATOR_DEPTH },
                    { x: stairPos.x, y: CROSS_AISLE_WIDTH / 2 + ELEVATOR_DEPTH },
                    { x: stairPos.x, y: stairPos.y + ELEVATOR_DEPTH }
                  ];
                  
                  const pointsStr = pathPoints.map(p => `${p.x},${p.y}`).join(' ');
                  
                  return (
                    <polyline
                      key={`line-elevator-stair-${i}`}
                      points={pointsStr}
                      fill="none"
                      stroke="rgba(156, 39, 176, 0.7)"
                      strokeWidth="0.15"
                      strokeDasharray="0.3"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  );
                }
                
                // Normal pick'ler arası - sadece AISLE ve COLUMN varsa çiz
                if (!pick.AISLE || pick.AISLE === '-' || !prevPick.AISLE || prevPick.AISLE === '-') {
                  return null;
                }
                
                const x1 = getXCoordinate(parseInt(prevPick.AISLE));
                const y1 = getYCoordinate(parseInt(prevPick.COLUMN)) + ELEVATOR_DEPTH;
                const x2 = getXCoordinate(parseInt(pick.AISLE));
                const y2 = getYCoordinate(parseInt(pick.COLUMN)) + ELEVATOR_DEPTH;
                
                // Manhattan yolunu hesapla
                const pathPoints = getManhattanPath(x1, y1 - ELEVATOR_DEPTH, x2, y2 - ELEVATOR_DEPTH);
                
                // SVG polyline için points string'i oluştur (offset ekle)
                const pointsStr = pathPoints
                  .map(p => `${p.x},${p.y + ELEVATOR_DEPTH}`)
                  .join(' ');
                
                return (
                  <polyline
                    key={`line-${i}`}
                    points={pointsStr}
                    fill="none"
                    stroke="rgba(0, 255, 136, 0.5)"
                    strokeWidth="0.15"
                    strokeDasharray="0.3"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                );
              })}
            </svg>
          )}

          {/* Mevcut pozisyon - normal pick */}
          {currentPick && !currentPick.IS_RETURN && !currentPick.IS_START && !currentPick.IS_STAIR_START && !currentPick.IS_STAIR_RETURN && (
            <div
              className="current-position"
              style={{
                left: `${getXCoordinate(parseInt(currentPick.AISLE))}rem`,
                top: `${getYCoordinate(parseInt(currentPick.COLUMN))}rem`
              }}
            >
              <div className="position-marker">
                <span className="position-order">{currentPick.PICK_ORDER}</span>
              </div>
              <div className="position-pulse"></div>
            </div>
          )}
          
          {/* Merdivende başlangıç pozisyonu */}
          {currentPick && currentPick.IS_STAIR_START && (() => {
            const stairPos = getStairPosition(currentPick.STAIR_NUM);
            return (
              <div
                className="current-position stair-position"
                style={{
                  left: `${stairPos.x}rem`,
                  top: `${stairPos.y}rem`
                }}
              >
                <div className="position-marker stair-marker">
                  <span className="position-order">⬆</span>
                </div>
                <div className="position-pulse"></div>
              </div>
            );
          })()}
          
          {/* Asansörde başlangıç pozisyonu */}
          {currentPick && currentPick.IS_START && (
            <div
              className="current-position start-position"
              style={{
                left: `${getXCoordinate(currentPick.ELEVATOR_NUM === 1 ? ELEVATOR_1_AISLE : ELEVATOR_2_AISLE)}rem`,
                top: `${-ELEVATOR_DEPTH / 2}rem`
              }}
            >
              <div className="position-marker start-marker">
                <span className="position-order">▶</span>
              </div>
              <div className="position-pulse"></div>
            </div>
          )}
          
          {/* Asansöre dönüş pozisyonu */}
          {currentPick && currentPick.IS_RETURN && (
            <div
              className="current-position return-position"
              style={{
                left: `${getXCoordinate(currentPick.ELEVATOR_NUM === 1 ? ELEVATOR_1_AISLE : ELEVATOR_2_AISLE)}rem`,
                top: `${-ELEVATOR_DEPTH / 2}rem`
              }}
            >
              <div className="position-marker return-marker">
                <span className="position-order">↩</span>
              </div>
              <div className="position-pulse"></div>
            </div>
          )}
          
          {/* Merdivene dönüş pozisyonu */}
          {currentPick && currentPick.IS_STAIR_RETURN && (() => {
            const stairPos = getStairPosition(currentPick.STAIR_NUM);
            return (
              <div
                className="current-position stair-return-position"
                style={{
                  left: `${stairPos.x}rem`,
                  top: `${stairPos.y}rem`
                }}
              >
                <div className="position-marker stair-return-marker">
                  <span className="position-order">⬇</span>
                </div>
                <div className="position-pulse"></div>
              </div>
            );
          })()}
        </div>
        </div>
      </div>

      {/* Legend */}
      <div className="layout-legend">
        <div className="legend-item">
          <div className="legend-color legend-shelf"></div>
          <span>{t(lang, 'legendShelf')}</span>
        </div>
        <div className="legend-item">
          <div className="legend-color legend-aisle"></div>
          <span>{t(lang, 'legendAisle')}</span>
        </div>
        <div className="legend-item">
          <div className="legend-color legend-cross-aisle"></div>
          <span>{t(lang, 'legendCrossAisle')}</span>
        </div>
        <div className="legend-item">
          <div className="legend-color legend-elevator"></div>
          <span>{t(lang, 'legendElevator')}</span>
        </div>
        <div className="legend-item">
          <div className="legend-color legend-shelf-left"></div>
          <span>{t(lang, 'legendShelfLeft')}</span>
        </div>
        <div className="legend-item">
          <div className="legend-color legend-shelf-right"></div>
          <span>{t(lang, 'legendShelfRight')}</span>
        </div>
        <div className="legend-item">
          <div className="legend-color legend-current"></div>
          <span>{t(lang, 'legendCurrent')}</span>
        </div>
        <div className="legend-item">
          <div className="legend-color legend-trail"></div>
          <span>{t(lang, 'legendTrail')}</span>
        </div>
      </div>
    </div>
  );
}

export default PickVisualizer;
