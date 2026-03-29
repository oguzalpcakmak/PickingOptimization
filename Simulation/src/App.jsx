import { useState, useCallback } from 'react';
import * as XLSX from 'xlsx';
import Papa from 'papaparse';
import { 
  ConfigProvider, 
  theme, 
  Layout, 
  Card, 
  Upload, 
  Button, 
  Typography, 
  Switch, 
  Progress, 
  Statistic, 
  Row, 
  Col, 
  Table, 
  message, 
  Alert,
  Flex,
  Tag
} from 'antd';
import { 
  CloudUploadOutlined, 
  ExperimentOutlined, 
  DownloadOutlined, 
  ReloadOutlined, 
  LineChartOutlined,
  SunOutlined,
  MoonOutlined,
  FileTextOutlined,
  TableOutlined,
  TeamOutlined,
  NodeIndexOutlined,
  ShopOutlined,
  GlobalOutlined
} from '@ant-design/icons';
import { processExcel, inspectPickData, PICK_DATA_FORMATS } from './utils/excelProcessor';
import { processStockData, mergeStockWithPicks } from './utils/stockProcessor';
import { 
  ELEVATOR_1_AISLE, 
  ELEVATOR_2_AISLE, 
  getNearestElevator, 
  getElevatorToPickDistance,
  getNearestStairToElevator,
  getStairToElevatorDistance
} from './utils/layoutConstants';
import PickVisualizer from './components/PickVisualizer';
import testData from './data/testData.json';
import { t } from './locales/translations';

const { Header, Content, Footer } = Layout;
const { Title, Text } = Typography;
const { Dragger } = Upload;

function App() {
  const [isDarkMode, setIsDarkMode] = useState(true);
  const [lang, setLang] = useState('tr');
  const [file, setFile] = useState(null);
  const [rawData, setRawData] = useState(null);
  const [processedData, setProcessedData] = useState(null);
  const [stats, setStats] = useState(null);
  const [processing, setProcessing] = useState(false);
  const [progress, setProgress] = useState({ stage: '', progress: 0 });
  const [showVisualizer, setShowVisualizer] = useState(false);
  const [isTestData, setIsTestData] = useState(false);
  const [selectedGroupData, setSelectedGroupData] = useState([]);
  const [currentSimStep, setCurrentSimStep] = useState(0);
  const [updatedStockData, setUpdatedStockData] = useState(null);
  const [stockStats, setStockStats] = useState(null);
  const [inputFormat, setInputFormat] = useState(null);
  const [messageApi, contextHolder] = message.useMessage();

  // Theme configuration
  const themeConfig = {
    algorithm: isDarkMode ? theme.darkAlgorithm : theme.defaultAlgorithm,
    token: {
      colorPrimary: '#1890ff',
      borderRadius: 8,
    },
  };

  const loadTestData = useCallback(() => {
    setFile({ name: t(lang, 'testDataName') });
    setRawData(null);
    setInputFormat(null);
    
    // PICKED_AMOUNT'a göre satırları çoğalt
    const expandedData = [];
    for (const row of testData) {
      const amount = parseInt(row.PICKED_AMOUNT) || 1;
      for (let i = 0; i < amount; i++) {
        expandedData.push({ ...row, PICKED_AMOUNT: '1' });
      }
    }
    
    // PICK_ORDER'ları yeniden hesapla (grup bazında)
    const groups = new Map();
    for (const row of expandedData) {
      const key = `${row.PICKER_CODE}|${row.PICKCAR_THM}`;
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key).push(row);
    }
    
    // Son veriler (merdiven + asansör başlangıç ve bitiş dahil)
    const finalData = [];
    
    // Her grup için PICK_ORDER ve mesafeleri yeniden hesapla
    for (const [, picks] of groups) {
      if (picks.length === 0) continue;
      
      // İlk pick'e göre başlangıç asansörünü belirle
      const firstPick = picks[0];
      const firstAisle = parseInt(firstPick.AISLE);
      const firstColumn = parseInt(firstPick.COLUMN);
      const nearestElevatorForStart = getNearestElevator(firstAisle);
      const startElevatorAisle = nearestElevatorForStart === 1 ? ELEVATOR_1_AISLE : ELEVATOR_2_AISLE;
      
      // Başlangıç asansörüne en yakın merdiveni bul
      const startStairId = getNearestStairToElevator(nearestElevatorForStart);
      const stairToElevatorDist = getStairToElevatorDistance(startStairId, nearestElevatorForStart);
      
      // === ADIM 0: Merdivende başlangıç ===
      const stairStartRow = {
        'PICKER_CODE': firstPick.PICKER_CODE,
        'PICKCAR_THM': firstPick.PICKCAR_THM,
        'DATE': firstPick.DATE,
        'TIME': '-',
        'AREA': firstPick.AREA,
        'AISLE': '-',
        'COLUMN': '0',
        'SHELF': '-',
        'LEFT_OR_RIGHT': '-',
        'PICKED_THM': '-',
        'ARTICLE_CODE': 'START_AT_STAIR',
        'PICKED_AMOUNT': '0',
        'PICK_ORDER': 0,
        'STEP_DIST': '0.0',
        'TOTAL_DIST': '0.0',
        'IS_STAIR_START': true,
        'STAIR_NUM': startStairId,
        'ELEVATOR_NUM': nearestElevatorForStart
      };
      
      finalData.push(stairStartRow);
      
      // === ADIM 1: Asansöre varış ===
      const elevatorStartRow = {
        'PICKER_CODE': firstPick.PICKER_CODE,
        'PICKCAR_THM': firstPick.PICKCAR_THM,
        'DATE': firstPick.DATE,
        'TIME': '-',
        'AREA': firstPick.AREA,
        'AISLE': String(startElevatorAisle),
        'COLUMN': '0',
        'SHELF': '-',
        'LEFT_OR_RIGHT': '-',
        'PICKED_THM': '-',
        'ARTICLE_CODE': 'START_AT_ELEVATOR',
        'PICKED_AMOUNT': '0',
        'PICK_ORDER': 1,
        'STEP_DIST': stairToElevatorDist.toFixed(1),
        'TOTAL_DIST': stairToElevatorDist.toFixed(1),
        'IS_START': true,
        'ELEVATOR_NUM': nearestElevatorForStart
      };
      
      finalData.push(elevatorStartRow);
      
      let order = 2;
      let totalDist = stairToElevatorDist;
      let prevAisle = null;
      let prevColumn = null;
      let isFirstPick = true;
      
      for (const pick of picks) {
        pick.PICK_ORDER = order;
        const currAisle = parseInt(pick.AISLE);
        const currColumn = parseInt(pick.COLUMN);
        
        if (isFirstPick) {
          // İlk pick: Asansörden mesafe hesapla
          const elevatorDist = getElevatorToPickDistance(startElevatorAisle, currAisle, currColumn);
          pick.STEP_DIST = elevatorDist.toFixed(1);
          isFirstPick = false;
        } else if (prevAisle === pick.AISLE && prevColumn === pick.COLUMN) {
          // Aynı lokasyonda ise STEP_DIST = 0
          pick.STEP_DIST = '0.0';
        }
        
        totalDist += parseFloat(pick.STEP_DIST || 0);
        pick.TOTAL_DIST = totalDist.toFixed(1);
        
        prevAisle = pick.AISLE;
        prevColumn = pick.COLUMN;
        order++;
        
        finalData.push(pick);
      }
      
      // Son pick'ten asansöre dönüş
      const lastPick = picks[picks.length - 1];
      const lastAisle = parseInt(lastPick.AISLE);
      const lastColumn = parseInt(lastPick.COLUMN);
      
      const nearestElevatorForEnd = getNearestElevator(lastAisle);
      const endElevatorAisle = nearestElevatorForEnd === 1 ? ELEVATOR_1_AISLE : ELEVATOR_2_AISLE;
      const returnDist = getElevatorToPickDistance(endElevatorAisle, lastAisle, lastColumn);
      totalDist += returnDist;
      
      // === ADIM N+2: Asansöre dönüş ===
      const elevatorReturnRow = {
        'PICKER_CODE': lastPick.PICKER_CODE,
        'PICKCAR_THM': lastPick.PICKCAR_THM,
        'DATE': lastPick.DATE,
        'TIME': '-',
        'AREA': lastPick.AREA,
        'AISLE': String(endElevatorAisle),
        'COLUMN': '0',
        'SHELF': '-',
        'LEFT_OR_RIGHT': '-',
        'PICKED_THM': '-',
        'ARTICLE_CODE': 'RETURN_TO_ELEVATOR',
        'PICKED_AMOUNT': '0',
        'PICK_ORDER': order,
        'STEP_DIST': returnDist.toFixed(1),
        'TOTAL_DIST': totalDist.toFixed(1),
        'IS_RETURN': true,
        'ELEVATOR_NUM': nearestElevatorForEnd
      };
      
      finalData.push(elevatorReturnRow);
      order++;
      
      // Bitiş asansörüne en yakın merdiveni bul
      const endStairId = getNearestStairToElevator(nearestElevatorForEnd);
      const elevatorToStairDist = getStairToElevatorDistance(endStairId, nearestElevatorForEnd);
      totalDist += elevatorToStairDist;
      
      // === ADIM N+3: Merdivene dönüş ===
      const stairReturnRow = {
        'PICKER_CODE': lastPick.PICKER_CODE,
        'PICKCAR_THM': lastPick.PICKCAR_THM,
        'DATE': lastPick.DATE,
        'TIME': '-',
        'AREA': lastPick.AREA,
        'AISLE': '-',
        'COLUMN': '0',
        'SHELF': '-',
        'LEFT_OR_RIGHT': '-',
        'PICKED_THM': '-',
        'ARTICLE_CODE': 'RETURN_TO_STAIR',
        'PICKED_AMOUNT': '0',
        'PICK_ORDER': order,
        'STEP_DIST': elevatorToStairDist.toFixed(1),
        'TOTAL_DIST': totalDist.toFixed(1),
        'IS_STAIR_RETURN': true,
        'STAIR_NUM': endStairId,
        'ELEVATOR_NUM': nearestElevatorForEnd
      };
      
      finalData.push(stairReturnRow);
    }
    
    setProcessedData(finalData);
    setIsTestData(true);
    
    const mznRows = finalData.filter(r => r.AREA && r.AREA.startsWith('MZN') && !r.IS_RETURN && !r.IS_START && !r.IS_STAIR_START && !r.IS_STAIR_RETURN).length;
    const groupCount = groups.size;
    const totalDist = finalData.reduce((sum, r) => sum + parseFloat(r.STEP_DIST || 0), 0);
    
    setStats({
      totalRows: expandedData.length,
      mznRows,
      totalGroups: groupCount,
      totalDistance: totalDist.toFixed(2)
    });
    
    messageApi.success(t(lang, 'testDataLoaded'));
    setShowVisualizer(true);
  }, [messageApi, lang]);

  const handleFileUpload = useCallback((uploadedFile) => {
    if (!uploadedFile) return false;

    setFile(uploadedFile);
    setRawData(null);
    setProcessedData(null);
    setStats(null);
    setIsTestData(false);
    setShowVisualizer(false);
    setSelectedGroupData([]);
    setCurrentSimStep(0);
    setUpdatedStockData(null);
    setStockStats(null);
    setInputFormat(null);
    setProgress({ stage: '', progress: 0 });
    setProcessing(true);

    (async () => {
      let hasParsedInput = false;

      try {
        const lowerFileName = uploadedFile.name?.toLowerCase() || '';
        const stockSheetName = 'Stok Bilgisi';
        let pickJsonData = [];
        let stockJsonData = null;
        if (lowerFileName.endsWith('.csv')) {
          const csvText = await uploadedFile.text();
          const parsedCsv = Papa.parse(csvText, {
            header: true,
            skipEmptyLines: true,
            transformHeader: (header) => header.replace(/^\uFEFF/, '').trim()
          });

          const parseErrors = parsedCsv.errors.filter((error) => error.code !== 'UndetectableDelimiter');
          if (parseErrors.length > 0) {
            throw new Error(parseErrors[0].message);
          }

          pickJsonData = parsedCsv.data;
        } else {
          const workbookData = await uploadedFile.arrayBuffer();
          const workbook = XLSX.read(workbookData, { type: 'array' });
          const sheetName = workbook.SheetNames.includes('Grup Toplama Verisi')
            ? 'Grup Toplama Verisi'
            : workbook.SheetNames[0];

          if (!sheetName) {
            throw new Error(t(lang, 'fileReadError'));
          }

          const worksheet = workbook.Sheets[sheetName];
          pickJsonData = XLSX.utils.sheet_to_json(worksheet, { defval: '' });

          if (workbook.SheetNames.includes(stockSheetName)) {
            const stockWorksheet = workbook.Sheets[stockSheetName];
            stockJsonData = XLSX.utils.sheet_to_json(stockWorksheet, { defval: '' });
            messageApi.info(`${stockJsonData.length} ${t(lang, 'stockRowsRead')}`);
          }
        }

        const inspection = inspectPickData(pickJsonData);
        if (!inspection.format) {
          messageApi.error(`${t(lang, 'missingColumns')}: ${inspection.missingColumns.join(', ')}`);
          return;
        }

        hasParsedInput = true;
        setInputFormat(inspection.format);
        messageApi.success(`${inspection.rows.length} ${t(lang, 'rowsRead')}`);

        await new Promise((resolve) => setTimeout(resolve, 100));

        const { data: processedResult, stats: processStats } = processExcel(inspection.rows, (p) => {
          setProgress(p);
        });

        setProcessedData(processedResult);
        setStats(processStats);
        setRawData(inspection.rows);
        
        if (stockJsonData) {
          const processedStock = processStockData(stockJsonData);
          const { data: mergedStock, stats: mergeStats } = mergeStockWithPicks(processedStock, processedResult);
          setUpdatedStockData(mergedStock);
          setStockStats(mergeStats);
          messageApi.success(t(lang, 'stockProcessed'));
        }
        
        messageApi.success(t(lang, 'conversionComplete'));
        setShowVisualizer(true);
      } catch (error) {
        const errorKey = hasParsedInput ? 'conversionError' : 'excelReadError';
        messageApi.error(`${t(lang, errorKey)}: ${error.message}`);
        console.error(error);
      } finally {
        setProcessing(false);
      }
    })();
    
    return false; // Prevent default upload behavior
  }, [messageApi, lang]);

  const downloadExcel = useCallback(() => {
    if (!processedData) return;

    // Excel için worksheet oluştur
    const worksheet = XLSX.utils.json_to_sheet(processedData);
    const workbook = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(workbook, worksheet, 'Grup Toplama Verisi');
    
    // Excel dosyasını indir
    XLSX.writeFile(workbook, 'Grup_Toplama_Verisi_Out.xlsx');
    messageApi.success(t(lang, 'excelDownloaded'));
  }, [processedData, messageApi, lang]);

  const downloadStockExcel = useCallback(() => {
    if (!updatedStockData) return;

    // Excel için worksheet oluştur
    const worksheet = XLSX.utils.json_to_sheet(updatedStockData);
    const workbook = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(workbook, worksheet, 'Güncellenmiş Stok');
    
    // Excel dosyasını indir
    XLSX.writeFile(workbook, 'Guncellenmis_Stok_Verisi.xlsx');
    messageApi.success(t(lang, 'stockExcelDownloaded'));
  }, [updatedStockData, messageApi, lang]);

  const reset = useCallback(() => {
    setFile(null);
    setRawData(null);
    setProcessedData(null);
    setStats(null);
    setProgress({ stage: '', progress: 0 });
    setShowVisualizer(false);
    setIsTestData(false);
    setSelectedGroupData([]);
    setCurrentSimStep(0);
    setUpdatedStockData(null);
    setStockStats(null);
    setInputFormat(null);
    messageApi.info(t(lang, 'reset'));
  }, [messageApi, lang]);

  /**
   * İşleme aşamasına göre etiket döndürür
   */
  const getStageLabel = (stage) => {
    const labels = {
      transform: t(lang, 'stageTransform'),
      filter: t(lang, 'stageFilter'),
      group: t(lang, 'stageGroup'),
      order: t(lang, 'stageOrder'),
      complete: t(lang, 'stageComplete')
    };
    return labels[stage] || stage;
  };

  const handleGroupSelect = useCallback((groupData, step) => {
    setSelectedGroupData(groupData);
    setCurrentSimStep(step);
  }, []);

  /** Seçili grup tablosu için sütun tanımları */
  const outputColumns = [
    { title: t(lang, 'colPicker'), dataIndex: 'PICKER_CODE', key: 'picker', width: 80 },
    { title: t(lang, 'colPickcar'), dataIndex: 'PICKCAR_THM', key: 'pickcar', width: 110 },
    { title: t(lang, 'colDate'), dataIndex: 'DATE', key: 'date', width: 100 },
    { title: t(lang, 'colTime'), dataIndex: 'TIME', key: 'time', width: 60 },
    { title: t(lang, 'colArea'), dataIndex: 'AREA', key: 'area', width: 70, render: (text) => <Tag color="blue">{text}</Tag> },
    { title: t(lang, 'colAisle'), dataIndex: 'AISLE', key: 'aisle', width: 70 },
    { title: t(lang, 'colColumn'), dataIndex: 'COLUMN', key: 'column', width: 70 },
    { title: t(lang, 'colShelf'), dataIndex: 'SHELF', key: 'shelf', width: 50 },
    { title: t(lang, 'colLR'), dataIndex: 'LEFT_OR_RIGHT', key: 'lr', width: 50, render: (text) => <Tag color={text === 'L' ? 'red' : 'cyan'}>{text}</Tag> },
    { title: t(lang, 'colOrder'), dataIndex: 'PICK_ORDER', key: 'order', width: 60, render: (text) => <Text strong style={{ color: '#1890ff' }}>{text}</Text> },
    { title: t(lang, 'colStep'), dataIndex: 'STEP_DIST', key: 'step', width: 80, render: (text) => <Text type="success">{text}m</Text> },
    { title: t(lang, 'colTotal'), dataIndex: 'TOTAL_DIST', key: 'total', width: 90, render: (text) => <Text type="warning">{text}m</Text> },
  ];

  return (
    <ConfigProvider theme={themeConfig}>
      {contextHolder}
      <Layout style={{ minHeight: '100vh' }}>
        <Header style={{ 
          display: 'flex', 
          alignItems: 'center', 
          justifyContent: 'space-between',
          padding: '0 24px',
          background: isDarkMode ? '#141414' : '#fff',
          borderBottom: `1px solid ${isDarkMode ? '#303030' : '#f0f0f0'}`
        }}>
          <Flex align="center" gap={12}>
            <ShopOutlined style={{ fontSize: '24px' }} />
            <Title level={4} style={{ margin: 0 }}>{t(lang, 'appTitle')}</Title>
          </Flex>
          <Flex align="center" gap={16}>
            {/* Language Switch */}
            <Flex align="center" gap={4}>
              <GlobalOutlined style={{ color: '#1890ff' }} />
              <Switch 
                checked={lang === 'en'} 
                onChange={(checked) => setLang(checked ? 'en' : 'tr')}
                checkedChildren="EN"
                unCheckedChildren="TR"
                size="small"
              />
            </Flex>
            {/* Theme Switch */}
            <Flex align="center" gap={8}>
              <SunOutlined style={{ color: isDarkMode ? '#666' : '#faad14' }} />
              <Switch 
                checked={isDarkMode} 
                onChange={setIsDarkMode}
                checkedChildren={<MoonOutlined />}
                unCheckedChildren={<SunOutlined />}
              />
              <MoonOutlined style={{ color: isDarkMode ? '#1890ff' : '#666' }} />
            </Flex>
          </Flex>
        </Header>

        <Content style={{ padding: '24px', maxWidth: 1400, margin: '0 auto', width: '100%' }}>

          {/* Upload Section */}
          <Card style={{ marginBottom: 24 }}>
            <Row gutter={[24, 24]}>
              <Col xs={24} md={14}>
                <Dragger
                  name="file"
                  accept=".xlsx,.xls,.csv"
                  showUploadList={false}
                  beforeUpload={handleFileUpload}
                  style={{ padding: '20px 0' }}
                >
                  <p className="ant-upload-drag-icon">
                    <CloudUploadOutlined style={{ fontSize: 48, color: '#1890ff' }} />
                  </p>
                  <p className="ant-upload-text">{t(lang, 'uploadTitle')}</p>
                  <p className="ant-upload-hint">{t(lang, 'uploadHint')}</p>
                </Dragger>
              </Col>
              <Col xs={24} md={10}>
                <Card 
                  style={{ 
                    height: '100%', 
                    display: 'flex', 
                    flexDirection: 'column', 
                    justifyContent: 'center',
                    background: isDarkMode ? '#1f1f1f' : '#fafafa',
                    border: '2px dashed #faad14'
                  }}
                >
                  <Flex vertical align="center" gap={16}>
                    <ExperimentOutlined style={{ fontSize: 48, color: '#faad14' }} />
                    <Button 
                      type="primary" 
                      icon={<ExperimentOutlined />} 
                      size="large"
                      onClick={loadTestData}
                      style={{ background: '#faad14', borderColor: '#faad14' }}
                    >
                      {t(lang, 'loadTestData')}
                    </Button>
                  </Flex>
                </Card>
              </Col>
            </Row>

            {file && (
              <Alert
                style={{ marginTop: 16 }}
                message={`${t(lang, 'uploadedFile')}: ${file.name}`}
                type="success"
                showIcon
                icon={<FileTextOutlined />}
              />
            )}
          </Card>

          {/* Progress Section */}
          {processing && (
            <Card style={{ marginBottom: 24 }}>
              <Text>{getStageLabel(progress.stage)}</Text>
              <Progress percent={Math.round(progress.progress)} status="active" />
            </Card>
          )}

          {/* Stats Section */}
          {stats && (
            <Card style={{ marginBottom: 24 }}>
              <Row gutter={[16, 16]}>
                <Col xs={12} sm={6}>
                  <Statistic 
                    title={t(lang, 'totalRows')} 
                    value={stats.totalRows} 
                    prefix={<FileTextOutlined />}
                    valueStyle={{ color: '#1890ff' }}
                  />
                </Col>
                <Col xs={12} sm={6}>
                  <Statistic 
                    title={t(lang, 'mznRows')} 
                    value={stats.mznRows} 
                    prefix={<TableOutlined />}
                    valueStyle={{ color: '#52c41a' }}
                  />
                </Col>
                <Col xs={12} sm={6}>
                  <Statistic 
                    title={t(lang, 'pickGroups')} 
                    value={stats.totalGroups} 
                    prefix={<TeamOutlined />}
                    valueStyle={{ color: '#722ed1' }}
                  />
                </Col>
                <Col xs={12} sm={6}>
                  <Statistic 
                    title={t(lang, 'totalDistance')} 
                    value={(stats.totalDistance / 1000).toFixed(2)} 
                    suffix="km"
                    prefix={<NodeIndexOutlined />}
                    valueStyle={{ color: '#fa8c16' }}
                  />
                </Col>
              </Row>
            </Card>
          )}

          {/* Stock Stats Section */}
          {stockStats && (
            <Card style={{ marginBottom: 24 }} title={t(lang, 'stockStatsTitle')}>
              <Row gutter={[16, 16]}>
                <Col xs={12} sm={6}>
                  <Statistic 
                    title={t(lang, 'originalStock')} 
                    value={stockStats.originalStockCount} 
                    prefix={<TableOutlined />}
                    valueStyle={{ color: '#1890ff' }}
                  />
                </Col>
                <Col xs={12} sm={6}>
                  <Statistic 
                    title={t(lang, 'updatedItems')} 
                    value={stockStats.updatedCount} 
                    prefix={<FileTextOutlined />}
                    valueStyle={{ color: '#52c41a' }}
                  />
                </Col>
                <Col xs={12} sm={6}>
                  <Statistic 
                    title={t(lang, 'newStockItems')} 
                    value={stockStats.newStockCount} 
                    prefix={<TeamOutlined />}
                    valueStyle={{ color: '#722ed1' }}
                  />
                </Col>
                <Col xs={12} sm={6}>
                  <Statistic 
                    title={t(lang, 'totalAddedBack')} 
                    value={stockStats.totalAddedBack} 
                    suffix={t(lang, 'units')}
                    prefix={<NodeIndexOutlined />}
                    valueStyle={{ color: '#fa8c16' }}
                  />
                </Col>
              </Row>
            </Card>
          )}

          {/* Action Buttons */}
          <Card style={{ marginBottom: 24 }}>
            <Flex wrap="wrap" gap={12} justify="center">
              {processedData && (
                <Button 
                  type="primary" 
                  icon={<DownloadOutlined />} 
                  size="large"
                  onClick={downloadExcel}
                >
                  {t(lang, 'downloadExcel')}
                </Button>
              )}
              {updatedStockData && (
                <Button 
                  type="primary" 
                  icon={<DownloadOutlined />} 
                  size="large"
                  onClick={downloadStockExcel}
                  style={{ background: '#52c41a', borderColor: '#52c41a' }}
                >
                  {t(lang, 'downloadStockExcel')}
                </Button>
              )}
              {processedData && (
                <Button 
                  type={showVisualizer ? 'primary' : 'default'}
                  icon={<LineChartOutlined />} 
                  size="large"
                  onClick={() => setShowVisualizer(!showVisualizer)}
                >
                  {showVisualizer ? t(lang, 'hideVisualization') : t(lang, 'visualize')}
                </Button>
              )}
              {(file || processedData) && (
                <Button 
                  danger
                  icon={<ReloadOutlined />} 
                  size="large"
                  onClick={reset}
                >
                  {t(lang, 'resetBtn')}
                </Button>
              )}
            </Flex>
          </Card>

          {/* Visualizer */}
          {showVisualizer && processedData && (
            <Card style={{ marginBottom: 24 }}>
              <PickVisualizer
                data={processedData}
                isDarkMode={isDarkMode}
                onGroupSelect={handleGroupSelect}
                lang={lang}
                skipNoTimeFilter={inputFormat === PICK_DATA_FORMATS.SOLVER_OUTPUT}
              />
            </Card>
          )}

          {/* Selected Group Data Table */}
          {showVisualizer && selectedGroupData.length > 0 && (
            <Card 
              title={
                <Flex align="center" gap={8}>
                  <TableOutlined />
                  <span>{t(lang, 'selectedGroupTitle')} ({selectedGroupData.length} {t(lang, 'rows')})</span>
                </Flex>
              }
            >
              <Table 
                dataSource={selectedGroupData.map((row, i) => ({ ...row, key: i }))} 
                columns={outputColumns}
                size="small"
                scroll={{ x: 'max-content', y: 400 }}
                pagination={false}
                rowClassName={(record, index) => index === currentSimStep ? 'ant-table-row-selected' : ''}
              />
            </Card>
          )}
        </Content>

        <Footer style={{ textAlign: 'center', background: 'transparent' }}>
          <Text type="secondary">{t(lang, 'footerText')}</Text>
        </Footer>
      </Layout>
    </ConfigProvider>
  );
}

export default App;
