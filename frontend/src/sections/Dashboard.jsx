import React, { useEffect, useState, useCallback } from 'react';
import {
  Box, VStack, SimpleGrid, Card, CardBody, CardHeader, Flex, Heading,
  Text, HStack, Icon, Stat, StatLabel, StatNumber, StatHelpText,
  Select, Spinner, Alert, AlertIcon, Badge, Collapse, Button, Grid, GridItem, Tooltip, IconButton, useToast,
  Skeleton, SkeletonText, SkeletonCircle, Checkbox,
  Modal, ModalOverlay, ModalContent, ModalHeader, ModalBody, ModalCloseButton, ModalFooter,
  Table, Thead, Tbody, Tr, Th, Td, TableContainer,
  Input, InputGroup, InputLeftElement, Tag, TagLabel, TagCloseButton, Wrap, WrapItem,
  Menu, MenuButton, MenuList, MenuItem
} from '@chakra-ui/react';
import { FiUsers, FiShoppingBag, FiMessageCircle, FiDollarSign, FiTrendingUp, FiTrendingDown, FiCalendar, FiChevronDown, FiChevronRight, FiChevronLeft, FiRefreshCw, FiSearch, FiX, FiDownload, FiAward, FiTag } from 'react-icons/fi';
import Chart from 'chart.js/auto';
import { PieChart, Pie, Cell, Legend, Tooltip as RechartsTooltip, ResponsiveContainer } from 'recharts';
import { colors, sizes, styles, typography, spacing } from '../styles/styles';
import { createLogger } from '../utils/logger.js';

const logger = createLogger('Dashboard');

// Компонент Sparkline для миниатюрного графика
const Sparkline = ({ data = [], width = 80, height = 30, color = '#3B82F6', strokeWidth = 1.5 }) => {
  if (!data || data.length === 0) {
    return null;
  }

  const max = Math.max(...data, 1); // Минимум 1 чтобы избежать деления на 0
  const min = Math.min(...data, 0);
  const range = max - min || 1;

  // Вычисляем точки для SVG path
  const points = data.map((value, index) => {
    const x = (index / (data.length - 1 || 1)) * width;
    const y = height - ((value - min) / range) * height;
    return `${x},${y}`;
  }).join(' ');

  const pathD = `M ${points}`;

  return (
    <svg
      width={width}
      height={height}
      style={{ opacity: 0.7 }}
      viewBox={`0 0 ${width} ${height}`}
      preserveAspectRatio="none"
    >
      {/* Область под линией (заливка) */}
      <defs>
        <linearGradient id={`gradient-${color}`} x1="0%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%" style={{ stopColor: color, stopOpacity: 0.3 }} />
          <stop offset="100%" style={{ stopColor: color, stopOpacity: 0.05 }} />
        </linearGradient>
      </defs>

      {/* Заливка под линией */}
      <path
        d={`${pathD} L ${width},${height} L 0,${height} Z`}
        fill={`url(#gradient-${color})`}
      />

      {/* Линия графика */}
      <path
        d={pathD}
        fill="none"
        stroke={color}
        strokeWidth={strokeWidth}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
};

const Dashboard = ({
  stats,
  chartRef,
  chartInstanceRef,
  section,
  setSection
}) => {
  const [chartData, setChartData] = useState(null);
  const [availablePeriods, setAvailablePeriods] = useState([]);
  const [selectedPeriod, setSelectedPeriod] = useState({ year: new Date().getFullYear(), month: new Date().getMonth() + 1 });
  const [isLoadingChart, setIsLoadingChart] = useState(false);
  const [chartError, setChartError] = useState(null);
  
  // Состояния для аккордеонов с сохранением в localStorage
  const [isChartOpen, setIsChartOpen] = useState(() => {
    const saved = localStorage.getItem('dashboard_chart_open');
    return saved !== null ? JSON.parse(saved) : true;
  });
  const [isCalendarOpen, setIsCalendarOpen] = useState(() => {
    const saved = localStorage.getItem('dashboard_calendar_open');
    return saved !== null ? JSON.parse(saved) : false;
  });
  
  // Состояния для календаря бронирований
  const [calendarDate, setCalendarDate] = useState(new Date());
  const [bookingsData, setBookingsData] = useState([]);
  const [isLoadingBookings, setIsLoadingBookings] = useState(false);
  const [bookingsError, setBookingsError] = useState(null);

  // Состояния для модального окна с деталями дня
  const [selectedDate, setSelectedDate] = useState(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [selectedDayBookings, setSelectedDayBookings] = useState([]);

  // Состояния для фильтров календаря
  const [availableTariffs, setAvailableTariffs] = useState([]);
  const [selectedTariffIds, setSelectedTariffIds] = useState([]);
  const [userSearchText, setUserSearchText] = useState('');
  const [totalBookingsCount, setTotalBookingsCount] = useState(0);
  const [filteredBookingsCount, setFilteredBookingsCount] = useState(0);

  // Состояния для обновления данных
  const [lastRefreshTime, setLastRefreshTime] = useState(new Date());
  const [isRefreshing, setIsRefreshing] = useState(false);
  const toast = useToast();

  // Состояния для управления видимостью линий графика
  const [visibleDatasets, setVisibleDatasets] = useState(() => {
    const saved = localStorage.getItem('dashboard_visible_datasets');
    return saved !== null ? JSON.parse(saved) : {
      users: true,
      tickets: true,
      bookings: true
    };
  });

  // Состояния для топ-клиентов
  const [topClientsData, setTopClientsData] = useState(null);
  const [isLoadingTopClients, setIsLoadingTopClients] = useState(false);
  const [topClientsError, setTopClientsError] = useState(null);
  const [isTopClientsOpen, setIsTopClientsOpen] = useState(() => {
    const saved = localStorage.getItem('dashboard_top_clients_open');
    return saved !== null ? JSON.parse(saved) : false;
  });

  // Состояния для распределения тарифов
  const [tariffDistribution, setTariffDistribution] = useState(null);
  const [isLoadingTariffs, setIsLoadingTariffs] = useState(false);
  const [tariffError, setTariffError] = useState(null);
  const [isTariffChartOpen, setIsTariffChartOpen] = useState(() => {
    const saved = localStorage.getItem('dashboard_tariff_chart_open');
    return saved !== null ? JSON.parse(saved) : false;
  });

  // Состояния для статистики промокодов
  const [promocodeStats, setPromocodeStats] = useState(null);
  const [isLoadingPromocodes, setIsLoadingPromocodes] = useState(false);
  const [promocodeError, setPromocodeError] = useState(null);
  const [isPromocodesOpen, setIsPromocodesOpen] = useState(() => {
    const saved = localStorage.getItem('dashboard_promocodes_open');
    return saved !== null ? JSON.parse(saved) : false;
  });

  // Состояния для сравнения периодов
  const [isCompareMode, setIsCompareMode] = useState(false);
  const [comparePeriod, setComparePeriod] = useState({ year: new Date().getFullYear(), month: new Date().getMonth() });
  const [comparisonData, setComparisonData] = useState(null);

  // Функция для получения токена из разных источников
  const getAuthToken = () => {
    // Проверяем разные варианты хранения токена
    const tokenSources = [
      localStorage.getItem('token'),
      localStorage.getItem('authToken'),
      localStorage.getItem('access_token'),
      sessionStorage.getItem('token'),
      sessionStorage.getItem('authToken'),
      document.cookie.match(/token=([^;]+)/)?.[1]
    ];

    logger.debug('Поиск токена в источниках:', {
      localStorage_token: localStorage.getItem('token'),
      localStorage_authToken: localStorage.getItem('authToken'),
      localStorage_access_token: localStorage.getItem('access_token'),
      sessionStorage_token: sessionStorage.getItem('token'),
      sessionStorage_authToken: sessionStorage.getItem('authToken'),
      cookie_token: document.cookie.match(/token=([^;]+)/)?.[1],
      all_localStorage: Object.keys(localStorage),
      all_sessionStorage: Object.keys(sessionStorage)
    });

    // Возвращаем первый найденный токен
    for (const token of tokenSources) {
      if (token && token.trim()) {
        logger.debug('Найден токен:', token.substring(0, 20) + '...');
        return token;
      }
    }

    logger.warn('Токен не найден ни в одном из источников');
    return null;
  };

  // Загрузка доступных периодов
  const loadAvailablePeriods = useCallback(async () => {
    try {
      const token = getAuthToken();
      if (!token) {
        logger.warn('Токен авторизации не найден');
        setChartError('Ошибка авторизации. Пожалуйста, войдите в систему.');
        return;
      }

      const response = await fetch('/api/dashboard/available-periods', {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        if (response.status === 401) {
          logger.warn('Токен недействителен, требуется повторная авторизация');
          setChartError('Сессия истекла. Пожалуйста, войдите в систему заново.');
          return;
        }
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();
      setAvailablePeriods(data.periods || []);

      // Устанавливаем текущий месяц как выбранный по умолчанию
      if (data.current) {
        setSelectedPeriod(data.current);
      }
    } catch (error) {
      logger.error('Ошибка загрузки доступных периодов:', error);
      setChartError(`Ошибка загрузки периодов: ${error.message}`);
    }
  }, []);

  // Загрузка данных для графика
  const loadChartData = useCallback(async (year, month) => {
    setIsLoadingChart(true);
    setChartError(null);

    try {
      const token = getAuthToken();
      if (!token) {
        throw new Error('Токен авторизации не найден. Пожалуйста, войдите в систему.');
      }

      const response = await fetch(`/api/dashboard/chart-data?year=${year}&month=${month}`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        if (response.status === 401) {
          throw new Error('Сессия истекла. Пожалуйста, войдите в систему заново.');
        }
        const errorText = await response.text();
        throw new Error(`HTTP ${response.status}: ${errorText || response.statusText}`);
      }

      const data = await response.json();
      setChartData(data);
    } catch (error) {
      logger.error('Ошибка загрузки данных графика:', error);
      setChartError(error.message);
    } finally {
      setIsLoadingChart(false);
    }
  }, []);

  // Загрузка данных распределения тарифов
  const loadTariffDistribution = useCallback(async (year, month) => {
    setIsLoadingTariffs(true);
    setTariffError(null);

    try {
      const token = getAuthToken();
      if (!token) {
        throw new Error('Токен авторизации не найден. Пожалуйста, войдите в систему.');
      }

      // Вычисляем начало и конец периода
      const periodStart = new Date(year, month - 1, 1);
      const periodEnd = new Date(year, month, 0, 23, 59, 59);

      const response = await fetch(
        `/api/dashboard/tariff-distribution?period_start=${periodStart.toISOString()}&period_end=${periodEnd.toISOString()}`,
        {
          method: 'GET',
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
        }
      );

      if (!response.ok) {
        if (response.status === 401) {
          throw new Error('Сессия истекла. Пожалуйста, войдите в систему заново.');
        }
        const errorText = await response.text();
        throw new Error(`HTTP ${response.status}: ${errorText || response.statusText}`);
      }

      const data = await response.json();
      setTariffDistribution(data);
    } catch (error) {
      logger.error('Ошибка загрузки данных распределения тарифов:', error);
      setTariffError(error.message);
    } finally {
      setIsLoadingTariffs(false);
    }
  }, []);

  // Загрузка данных сравнения периодов
  const loadComparisonData = useCallback(async (period1Year, period1Month, period2Year, period2Month) => {
    setIsLoadingChart(true);
    setChartError(null);

    try {
      const token = getAuthToken();
      if (!token) {
        throw new Error('Токен авторизации не найден. Пожалуйста, войдите в систему.');
      }

      const response = await fetch(
        `/api/dashboard/compare-periods?period1_year=${period1Year}&period1_month=${period1Month}&period2_year=${period2Year}&period2_month=${period2Month}`,
        {
          method: 'GET',
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
        }
      );

      if (!response.ok) {
        if (response.status === 401) {
          throw new Error('Сессия истекла. Пожалуйста, войдите в систему заново.');
        }
        const errorText = await response.text();
        throw new Error(`HTTP ${response.status}: ${errorText || response.statusText}`);
      }

      const data = await response.json();
      setComparisonData(data);
      setChartData(null); // Очищаем обычные данные графика
    } catch (error) {
      logger.error('Ошибка загрузки данных сравнения:', error);
      setChartError(error.message);
    } finally {
      setIsLoadingChart(false);
    }
  }, []);

  // Экспорт данных в CSV
  const handleExportCSV = useCallback(async () => {
    try {
      const token = getAuthToken();
      if (!token) {
        toast({
          title: 'Ошибка',
          description: 'Токен авторизации не найден',
          status: 'error',
          duration: 3000,
          isClosable: true,
        });
        return;
      }

      // Формируем URL с параметрами периода
      const params = new URLSearchParams();
      if (selectedPeriod && selectedPeriod.year && selectedPeriod.month) {
        const startDate = new Date(selectedPeriod.year, selectedPeriod.month - 1, 1);
        const endDate = new Date(selectedPeriod.year, selectedPeriod.month, 0, 23, 59, 59);
        params.append('period_start', startDate.toISOString());
        params.append('period_end', endDate.toISOString());
      }

      const response = await fetch(`/api/dashboard/export-csv?${params.toString()}`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      if (!response.ok) {
        throw new Error('Ошибка экспорта данных');
      }

      // Скачиваем файл
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `dashboard_${new Date().toISOString().split('T')[0]}.csv`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);

      toast({
        title: 'Успешно',
        description: 'Данные экспортированы в CSV',
        status: 'success',
        duration: 3000,
        isClosable: true,
      });
    } catch (error) {
      logger.error('Ошибка экспорта CSV:', error);
      toast({
        title: 'Ошибка',
        description: 'Не удалось экспортировать данные',
        status: 'error',
        duration: 3000,
        isClosable: true,
      });
    }
  }, [selectedPeriod, toast]);

  // Экспорт данных в Excel
  const handleExportExcel = useCallback(async () => {
    try {
      const token = getAuthToken();
      if (!token) {
        toast({
          title: 'Ошибка',
          description: 'Токен авторизации не найден',
          status: 'error',
          duration: 3000,
          isClosable: true,
        });
        return;
      }

      // Формируем URL с параметрами периода
      const params = new URLSearchParams();
      if (selectedPeriod && selectedPeriod.year && selectedPeriod.month) {
        const startDate = new Date(selectedPeriod.year, selectedPeriod.month - 1, 1);
        const endDate = new Date(selectedPeriod.year, selectedPeriod.month, 0, 23, 59, 59);
        params.append('period_start', startDate.toISOString());
        params.append('period_end', endDate.toISOString());
      }

      const response = await fetch(`/api/dashboard/export-excel?${params.toString()}`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      if (!response.ok) {
        throw new Error('Ошибка экспорта данных');
      }

      // Скачиваем файл
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `dashboard_${new Date().toISOString().split('T')[0]}.xlsx`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);

      toast({
        title: 'Успешно',
        description: 'Данные экспортированы в Excel',
        status: 'success',
        duration: 3000,
        isClosable: true,
      });
    } catch (error) {
      logger.error('Ошибка экспорта Excel:', error);
      toast({
        title: 'Ошибка',
        description: 'Не удалось экспортировать данные',
        status: 'error',
        duration: 3000,
        isClosable: true,
      });
    }
  }, [selectedPeriod, toast]);

  // Загрузка периодов при монтировании компонента
  useEffect(() => {
    if (section === 'dashboard') {
      loadAvailablePeriods();
    }
  }, [section, loadAvailablePeriods]);

  // Загрузка данных графика при изменении выбранного периода
  useEffect(() => {
    if (section === 'dashboard' && selectedPeriod.year && selectedPeriod.month) {
      if (isCompareMode && comparePeriod.year && comparePeriod.month) {
        // Режим сравнения
        loadComparisonData(selectedPeriod.year, selectedPeriod.month, comparePeriod.year, comparePeriod.month + 1);
      } else {
        // Обычный режим
        loadChartData(selectedPeriod.year, selectedPeriod.month);
        setComparisonData(null); // Очищаем данные сравнения
      }
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [section, selectedPeriod.year, selectedPeriod.month, isCompareMode, comparePeriod.year, comparePeriod.month]);

  // Загрузка топ-клиентов при изменении периода
  useEffect(() => {
    if (section === 'dashboard' && isTopClientsOpen && selectedPeriod.year && selectedPeriod.month) {
      loadTopClients();
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [section, selectedPeriod.year, selectedPeriod.month, isTopClientsOpen]);

  // Загрузка статистики промокодов при изменении периода
  useEffect(() => {
    if (section === 'dashboard' && isPromocodesOpen && selectedPeriod.year && selectedPeriod.month) {
      loadPromocodeStats();
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [section, selectedPeriod.year, selectedPeriod.month, isPromocodesOpen]);

  // Загрузка данных тарифов при изменении выбранного периода
  useEffect(() => {
    if (section === 'dashboard' && selectedPeriod.year && selectedPeriod.month && isTariffChartOpen) {
      loadTariffDistribution(selectedPeriod.year, selectedPeriod.month);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [section, selectedPeriod.year, selectedPeriod.month, isTariffChartOpen]);

  // Обработчик изменения периода
  const handlePeriodChange = (event) => {
    const selectedValue = event.target.value;
    if (selectedValue) {
      const [year, month] = selectedValue.split('-').map(Number);
      setSelectedPeriod({ year, month });
    }
  };

  // Принудительное обновление всех данных дашборда
  const handleForceRefresh = async () => {
    try {
      setIsRefreshing(true);
      logger.info('Принудительное обновление данных дашборда');

      // Перезагружаем данные графика
      if (selectedPeriod.year && selectedPeriod.month) {
        await loadChartData(selectedPeriod.year, selectedPeriod.month);
      }

      // Перезагружаем данные тарифов если открыт
      if (isTariffChartOpen && selectedPeriod.year && selectedPeriod.month) {
        await loadTariffDistribution(selectedPeriod.year, selectedPeriod.month);
      }

      // Перезагружаем календарь бронирований если открыт
      if (isCalendarOpen) {
        await loadBookingsForMonth(calendarDate.getFullYear(), calendarDate.getMonth() + 1);
      }

      // Триггерим событие для перезагрузки stats в родительском компоненте
      window.dispatchEvent(new Event('dashboard:forceRefresh'));

      // Обновляем timestamp
      setLastRefreshTime(new Date());

      // Показываем успешное уведомление
      toast({
        title: 'Данные обновлены',
        description: 'Все данные дашборда успешно обновлены',
        status: 'success',
        duration: 2000,
        isClosable: true,
        position: 'top-right'
      });

      logger.info('Данные дашборда успешно обновлены');
    } catch (error) {
      logger.error('Ошибка при обновлении данных дашборда:', error);
      toast({
        title: 'Ошибка обновления',
        description: 'Не удалось обновить данные. Попробуйте позже.',
        status: 'error',
        duration: 3000,
        isClosable: true,
        position: 'top-right'
      });
    } finally {
      setIsRefreshing(false);
    }
  };

  // Управление видимостью линий на графике
  const toggleDatasetVisibility = (datasetKey) => {
    const newVisibility = {
      ...visibleDatasets,
      [datasetKey]: !visibleDatasets[datasetKey]
    };
    setVisibleDatasets(newVisibility);
    localStorage.setItem('dashboard_visible_datasets', JSON.stringify(newVisibility));

    // Обновить видимость в Chart.js
    if (chartInstanceRef.current) {
      const datasetIndex = datasetKey === 'users' ? 0 : datasetKey === 'tickets' ? 1 : 2;
      const meta = chartInstanceRef.current.getDatasetMeta(datasetIndex);
      meta.hidden = !newVisibility[datasetKey];
      chartInstanceRef.current.update();
    }
  };

  // Создание/обновление графика
  useEffect(() => {
    if (
      chartRef.current &&
      chartData &&
      section === 'dashboard' &&
      !isLoadingChart
    ) {
      // Уничтожаем существующий график
      if (chartInstanceRef.current) {
        chartInstanceRef.current.destroy();
        chartInstanceRef.current = null;
      }

      const ctx = chartRef.current.getContext('2d');

      // Определяем datasets в зависимости от режима сравнения
      let datasets = [];

      if (isCompareMode && comparisonData) {
        // Режим сравнения: показываем оба периода
        datasets = [
          // Текущий период (основной)
          {
            label: `Пользователи (${chartData.period.month_name} ${chartData.period.year})`,
            data: chartData.datasets.user_registrations,
            borderColor: '#3B82F6',
            backgroundColor: 'rgba(59, 130, 246, 0.1)',
            tension: 0.4,
            borderWidth: 3,
            pointBackgroundColor: '#3B82F6',
            pointBorderColor: '#fff',
            pointBorderWidth: 2,
            pointRadius: 4,
            pointHoverRadius: 7,
            fill: true,
            hidden: !visibleDatasets.users
          },
          {
            label: `Тикеты (${chartData.period.month_name} ${chartData.period.year})`,
            data: chartData.datasets.ticket_creations,
            borderColor: '#F59E0B',
            backgroundColor: 'rgba(245, 158, 11, 0.1)',
            tension: 0.4,
            borderWidth: 3,
            pointBackgroundColor: '#F59E0B',
            pointBorderColor: '#fff',
            pointBorderWidth: 2,
            pointRadius: 4,
            pointHoverRadius: 7,
            fill: true,
            hidden: !visibleDatasets.tickets
          },
          {
            label: `Бронирования (${chartData.period.month_name} ${chartData.period.year})`,
            data: chartData.datasets.booking_creations,
            borderColor: '#10B981',
            backgroundColor: 'rgba(16, 185, 129, 0.1)',
            tension: 0.4,
            borderWidth: 3,
            pointBackgroundColor: '#10B981',
            pointBorderColor: '#fff',
            pointBorderWidth: 2,
            pointRadius: 4,
            pointHoverRadius: 7,
            fill: true,
            hidden: !visibleDatasets.bookings
          },
          // Период сравнения (пунктирные линии, более светлые цвета)
          {
            label: `Пользователи (${comparisonData.period.month_name} ${comparisonData.period.year})`,
            data: comparisonData.datasets.user_registrations,
            borderColor: '#93C5FD',
            backgroundColor: 'rgba(147, 197, 253, 0.05)',
            tension: 0.4,
            borderWidth: 2,
            borderDash: [5, 5],
            pointBackgroundColor: '#93C5FD',
            pointBorderColor: '#fff',
            pointBorderWidth: 2,
            pointRadius: 3,
            pointHoverRadius: 6,
            fill: false,
            hidden: !visibleDatasets.users
          },
          {
            label: `Тикеты (${comparisonData.period.month_name} ${comparisonData.period.year})`,
            data: comparisonData.datasets.ticket_creations,
            borderColor: '#FCD34D',
            backgroundColor: 'rgba(252, 211, 77, 0.05)',
            tension: 0.4,
            borderWidth: 2,
            borderDash: [5, 5],
            pointBackgroundColor: '#FCD34D',
            pointBorderColor: '#fff',
            pointBorderWidth: 2,
            pointRadius: 3,
            pointHoverRadius: 6,
            fill: false,
            hidden: !visibleDatasets.tickets
          },
          {
            label: `Бронирования (${comparisonData.period.month_name} ${comparisonData.period.year})`,
            data: comparisonData.datasets.booking_creations,
            borderColor: '#6EE7B7',
            backgroundColor: 'rgba(110, 231, 183, 0.05)',
            tension: 0.4,
            borderWidth: 2,
            borderDash: [5, 5],
            pointBackgroundColor: '#6EE7B7',
            pointBorderColor: '#fff',
            pointBorderWidth: 2,
            pointRadius: 3,
            pointHoverRadius: 6,
            fill: false,
            hidden: !visibleDatasets.bookings
          }
        ];
      } else {
        // Обычный режим: показываем только текущий период
        datasets = [
          {
            label: 'Регистрации пользователей',
            data: chartData.datasets.user_registrations,
            borderColor: '#3B82F6',
            backgroundColor: 'rgba(59, 130, 246, 0.1)',
            tension: 0.4,
            borderWidth: 3,
            pointBackgroundColor: '#3B82F6',
            pointBorderColor: '#fff',
            pointBorderWidth: 2,
            pointRadius: 4,
            pointHoverRadius: 7,
            fill: true,
            hidden: !visibleDatasets.users
          },
          {
            label: 'Создание тикетов',
            data: chartData.datasets.ticket_creations,
            borderColor: '#F59E0B',
            backgroundColor: 'rgba(245, 158, 11, 0.1)',
            tension: 0.4,
            borderWidth: 3,
            pointBackgroundColor: '#F59E0B',
            pointBorderColor: '#fff',
            pointBorderWidth: 2,
            pointRadius: 4,
            pointHoverRadius: 7,
            fill: true,
            hidden: !visibleDatasets.tickets
          },
          {
            label: 'Бронирования',
            data: chartData.datasets.booking_creations,
            borderColor: '#10B981',
            backgroundColor: 'rgba(16, 185, 129, 0.1)',
            tension: 0.4,
            borderWidth: 3,
            pointBackgroundColor: '#10B981',
            pointBorderColor: '#fff',
            pointBorderWidth: 2,
            pointRadius: 4,
            pointHoverRadius: 7,
            fill: true,
            hidden: !visibleDatasets.bookings
          }
        ];
      }

      chartInstanceRef.current = new Chart(ctx, {
        type: 'line',
        data: {
          labels: chartData.labels,
          datasets: datasets
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          interaction: {
            mode: 'index',
            intersect: false,
          },
          scales: {
            x: {
              display: true,
              title: {
                display: true,
                text: 'День месяца',
                font: {
                  size: 14,
                  weight: 'bold'
                }
              },
              grid: {
                color: 'rgba(0, 0, 0, 0.05)'
              }
            },
            y: {
              type: 'linear',
              display: true,
              position: 'left',
              title: {
                display: true,
                text: 'Количество',
                font: {
                  size: 14,
                  weight: 'bold'
                },
                color: '#666'
              },
              grid: {
                color: 'rgba(0, 0, 0, 0.1)'
              },
              ticks: {
                color: '#666',
                beginAtZero: true,
                precision: 0
              }
            }
          },
          plugins: {
            tooltip: {
              backgroundColor: 'rgba(0, 0, 0, 0.8)',
              titleColor: '#fff',
              bodyColor: '#fff',
              borderColor: 'rgba(255, 255, 255, 0.1)',
              borderWidth: 1,
              cornerRadius: 8,
              displayColors: true,
              callbacks: {
                title: function(context) {
                  return `${context[0].label} число`;
                },
                label: function(context) {
                  const label = context.dataset.label || '';
                  const value = context.parsed.y;
                  let unit = ' шт.';
                  if (label.includes('Пользователи')) unit = ' чел.';
                  if (label.includes('Бронирования')) unit = ' брон.';
                  return `${label}: ${value}${unit}`;
                }
              }
            },
            legend: {
              display: true,
              position: 'top',
              align: 'center',
              labels: {
                usePointStyle: true,
                pointStyle: 'circle',
                padding: 15,
                font: {
                  size: 12,
                  weight: '500'
                }
              }
            }
          },
          elements: {
            point: {
              hoverBorderWidth: 3
            }
          }
        }
      });
    }
  }, [chartData, comparisonData, isCompareMode, chartRef, chartInstanceRef, section, isLoadingChart, visibleDatasets]);

  // Очистка графика при размонтировании
  useEffect(() => {
    return () => {
      if (chartInstanceRef.current) {
        chartInstanceRef.current.destroy();
        chartInstanceRef.current = null;
      }
    };
  }, []);

  // Загрузка списка тарифов
  const loadTariffs = useCallback(async () => {
    try {
      const token = getAuthToken();
      if (!token) return;

      const response = await fetch('/api/tariffs', {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (response.ok) {
        const data = await response.json();
        setAvailableTariffs(data || []);
      }
    } catch (error) {
      logger.error('Ошибка загрузки тарифов:', error);
    }
  }, []);

  // Загрузка данных бронирований для календаря
  const loadBookingsData = useCallback(async (year, month) => {
    setIsLoadingBookings(true);
    setBookingsError(null);

    try {
      const token = getAuthToken();
      if (!token) {
        throw new Error('Токен авторизации не найден. Пожалуйста, войдите в систему.');
      }

      // Строим URL с параметрами фильтрации
      const params = new URLSearchParams({
        year: year.toString(),
        month: month.toString()
      });

      if (selectedTariffIds.length > 0) {
        params.append('tariff_ids', selectedTariffIds.join(','));
      }

      if (userSearchText.trim()) {
        params.append('user_search', userSearchText.trim());
      }

      const response = await fetch(`/api/dashboard/bookings-calendar?${params.toString()}`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        if (response.status === 401) {
          throw new Error('Сессия истекла. Пожалуйста, войдите в систему заново.');
        }
        const errorText = await response.text();
        throw new Error(`HTTP ${response.status}: ${errorText || response.statusText}`);
      }

      const data = await response.json();
      setBookingsData(data.bookings || []);
      setFilteredBookingsCount(data.bookings?.length || 0);

      // Если нет фильтров, сохраняем total count
      if (selectedTariffIds.length === 0 && !userSearchText.trim()) {
        setTotalBookingsCount(data.bookings?.length || 0);
      }
    } catch (error) {
      logger.error('Ошибка загрузки данных календаря:', error);
      setBookingsError(error.message);
    } finally {
      setIsLoadingBookings(false);
    }
  }, [selectedTariffIds, userSearchText]);

  // Загрузка тарифов при открытии календаря
  useEffect(() => {
    if (section === 'dashboard' && isCalendarOpen && availableTariffs.length === 0) {
      loadTariffs();
    }
  }, [section, isCalendarOpen, availableTariffs.length, loadTariffs]);

  // Загрузка календаря при открытии аккордеона или изменении фильтров
  useEffect(() => {
    if (section === 'dashboard' && isCalendarOpen) {
      loadBookingsData(calendarDate.getFullYear(), calendarDate.getMonth() + 1);
    }
  }, [section, isCalendarOpen, calendarDate, loadBookingsData]);

  // Функции для навигации по календарю
  const navigateMonth = (direction) => {
    const newDate = new Date(calendarDate);
    if (direction === 'prev') {
      newDate.setMonth(newDate.getMonth() - 1);
    } else {
      newDate.setMonth(newDate.getMonth() + 1);
    }
    setCalendarDate(newDate);
  };

  // Функция для получения календарной сетки
  const getCalendarDays = () => {
    const year = calendarDate.getFullYear();
    const month = calendarDate.getMonth();
    
    const firstDay = new Date(year, month, 1);
    const lastDay = new Date(year, month + 1, 0);
    const startDate = new Date(firstDay);
    startDate.setDate(startDate.getDate() - firstDay.getDay());
    
    const days = [];
    const currentDate = new Date(startDate);
    
    for (let i = 0; i < 42; i++) {
      days.push(new Date(currentDate));
      currentDate.setDate(currentDate.getDate() + 1);
    }
    
    return days;
  };

  // Функция для получения бронирований на конкретную дату
  const getBookingsForDate = (date) => {
    const dateString = date.toISOString().split('T')[0];
    return bookingsData.filter(booking => booking.visit_date === dateString);
  };

  // Функция для сохранения состояния аккордеонов
  const toggleChartOpen = () => {
    const newState = !isChartOpen;
    setIsChartOpen(newState);
    localStorage.setItem('dashboard_chart_open', JSON.stringify(newState));
  };

  const toggleCalendarOpen = () => {
    const newState = !isCalendarOpen;
    setIsCalendarOpen(newState);
    localStorage.setItem('dashboard_calendar_open', JSON.stringify(newState));

    // При открытии календаря принудительно обновляем данные
    if (newState && section === 'dashboard') {
      loadBookingsData(calendarDate.getFullYear(), calendarDate.getMonth() + 1);
    }
  };

  const toggleTopClientsOpen = () => {
    const newState = !isTopClientsOpen;
    setIsTopClientsOpen(newState);
    localStorage.setItem('dashboard_top_clients_open', JSON.stringify(newState));

    // При открытии загружаем данные, если еще не загружены
    if (newState && section === 'dashboard' && !topClientsData) {
      loadTopClients();
    }
  };

  // Загрузка топ-клиентов
  const loadTopClients = useCallback(async (limit = 5) => {
    setIsLoadingTopClients(true);
    setTopClientsError(null);

    try {
      const token = getAuthToken();
      if (!token) {
        throw new Error('Токен авторизации не найден');
      }

      // Формируем URL с параметрами периода
      const params = new URLSearchParams();
      params.append('limit', limit);

      if (selectedPeriod && selectedPeriod.year && selectedPeriod.month) {
        const startDate = new Date(selectedPeriod.year, selectedPeriod.month - 1, 1);
        const endDate = new Date(selectedPeriod.year, selectedPeriod.month, 0, 23, 59, 59);
        params.append('period_start', startDate.toISOString());
        params.append('period_end', endDate.toISOString());
      }

      const response = await fetch(`/api/dashboard/top-clients?${params.toString()}`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        if (response.status === 401) {
          throw new Error('Сессия истекла. Пожалуйста, войдите в систему заново.');
        }
        const errorText = await response.text();
        throw new Error(`HTTP ${response.status}: ${errorText || response.statusText}`);
      }

      const data = await response.json();
      setTopClientsData(data);
      logger.info('Топ-клиенты загружены:', data.clients.length);
    } catch (error) {
      logger.error('Ошибка загрузки топ-клиентов:', error);
      setTopClientsError(error.message);
    } finally {
      setIsLoadingTopClients(false);
    }
  }, [selectedPeriod]);

  // Загрузка статистики промокодов
  const loadPromocodeStats = useCallback(async () => {
    setIsLoadingPromocodes(true);
    setPromocodeError(null);

    try {
      const token = getAuthToken();
      if (!token) {
        throw new Error('Токен авторизации не найден');
      }

      // Формируем URL с параметрами периода
      const params = new URLSearchParams();

      if (selectedPeriod && selectedPeriod.year && selectedPeriod.month) {
        const startDate = new Date(selectedPeriod.year, selectedPeriod.month - 1, 1);
        const endDate = new Date(selectedPeriod.year, selectedPeriod.month, 0, 23, 59, 59);
        params.append('period_start', startDate.toISOString());
        params.append('period_end', endDate.toISOString());
      }

      const response = await fetch(`/api/dashboard/promocode-stats?${params.toString()}`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        if (response.status === 401) {
          throw new Error('Сессия истекла. Пожалуйста, войдите в систему заново.');
        }
        const errorText = await response.text();
        throw new Error(`HTTP ${response.status}: ${errorText || response.statusText}`);
      }

      const data = await response.json();
      setPromocodeStats(data);
      logger.info('Статистика промокодов загружена:', data.promocodes.length);
    } catch (error) {
      logger.error('Ошибка загрузки статистики промокодов:', error);
      setPromocodeError(error.message);
    } finally {
      setIsLoadingPromocodes(false);
    }
  }, [selectedPeriod]);

  const togglePromocodesOpen = () => {
    const newState = !isPromocodesOpen;
    setIsPromocodesOpen(newState);
    localStorage.setItem('dashboard_promocodes_open', JSON.stringify(newState));

    // При открытии загружаем данные, если еще не загружены
    if (newState && section === 'dashboard' && !promocodeStats) {
      loadPromocodeStats();
    }
  };

  // Функция для перехода к конкретному бронированию
  const handleBookingClick = (booking) => {
    logger.debug('Клик на бронирование:', booking);

    // Сохраняем ID бронирования для фильтра
    localStorage.setItem('bookings_filter_id', booking.id.toString());

    // Переходим к разделу бронирований
    if (setSection) {
      setSection('bookings');
    } else {
      // Fallback: используем событие для навигации
      const event = new CustomEvent('navigate-to-booking', {
        detail: { bookingId: booking.id, section: 'bookings' }
      });
      window.dispatchEvent(event);
    }
  };

  // Открыть модальное окно с бронированиями дня
  const handleDayClick = (date) => {
    const bookings = getBookingsForDate(date);
    if (bookings.length === 0) return; // Не открываем модальное окно если нет бронирований

    // Сортируем бронирования по времени
    const sortedBookings = [...bookings].sort((a, b) => {
      const timeA = a.visit_time || '00:00';
      const timeB = b.visit_time || '00:00';
      return timeA.localeCompare(timeB);
    });

    setSelectedDate(date);
    setSelectedDayBookings(sortedBookings);
    setIsModalOpen(true);
    logger.debug('Открытие модального окна для даты:', date, 'Бронирований:', sortedBookings.length);
  };

  // Закрыть модальное окно
  const handleModalClose = () => {
    setIsModalOpen(false);
    setSelectedDate(null);
    setSelectedDayBookings([]);
  };

  // Обработчики фильтров
  const handleTariffToggle = (tariffId) => {
    setSelectedTariffIds(prev =>
      prev.includes(tariffId)
        ? prev.filter(id => id !== tariffId)
        : [...prev, tariffId]
    );
  };

  const handleUserSearchChange = (e) => {
    setUserSearchText(e.target.value);
  };

  const handleClearFilters = () => {
    setSelectedTariffIds([]);
    setUserSearchText('');
  };

  const hasActiveFilters = selectedTariffIds.length > 0 || userSearchText.trim().length > 0;

  return (
    <Box p={spacing.lg} bg={colors.background.main} minH={sizes.content.minHeight}>
      <VStack spacing={8} align="stretch">
        {/* Заголовок с кнопкой обновления и timestamp */}
        <Flex justify="space-between" align="center" wrap="wrap" gap={4}>
          <Heading size="lg" color={colors.text.primary}>
            Дашборд
          </Heading>
          <HStack spacing={3}>
            <VStack spacing={0} align="flex-end">
              <Text fontSize="xs" color={colors.text.secondary}>
                Последнее обновление
              </Text>
              <Text fontSize="sm" color={colors.text.primary} fontWeight="medium">
                {lastRefreshTime.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })}
              </Text>
            </VStack>
            <Tooltip label="Обновить данные" placement="left">
              <IconButton
                icon={<Icon as={FiRefreshCw} />}
                onClick={handleForceRefresh}
                isLoading={isRefreshing}
                aria-label="Обновить данные"
                colorScheme="blue"
                variant="ghost"
                size="md"
                _hover={{
                  bg: 'blue.50',
                  transform: 'rotate(180deg)',
                  transition: 'all 0.3s ease'
                }}
              />
            </Tooltip>
          </HStack>
        </Flex>

        {/* Статистические карточки */}
        <SimpleGrid columns={{ base: 1, md: 2, lg: 4 }} spacing={spacing.md}>
          {!stats ? (
            // Skeleton для карточек при загрузке
            <>
              {[1, 2, 3, 4].map((index) => (
                <Card
                  key={index}
                  borderRadius={styles.card.borderRadius}
                  boxShadow="lg"
                >
                  <CardBody p={spacing.md}>
                    <Flex justify="space-between" align="flex-start">
                      <Box flex="1">
                        <Skeleton height="16px" width="120px" mb={3} />
                        <Skeleton height="36px" width="80px" mb={3} />
                        <SkeletonText noOfLines={1} spacing="2" skeletonHeight="14px" width="140px" />
                      </Box>
                      <Skeleton height="40px" width="80px" ml={2} />
                    </Flex>
                  </CardBody>
                </Card>
              ))}
            </>
          ) : (
            // Реальные карточки с данными
            <>
              <Card
                bgGradient={colors.stats.users.gradient}
                color="white"
                borderRadius={styles.card.borderRadius}
                boxShadow="lg"
                transition="all 0.3s ease"
                _hover={{
                  transform: styles.card.hoverTransform,
                  boxShadow: styles.card.hoverShadow
                }}
              >
                <CardBody p={spacing.md}>
                  <Flex justify="space-between" align="flex-start">
                    <Stat flex="1">
                      <StatLabel fontSize={typography.fontSizes.sm} fontWeight={typography.fontWeights.medium} opacity={0.9}>
                        Всего пользователей
                      </StatLabel>
                      <StatNumber fontSize={typography.fontSizes['3xl']} fontWeight={typography.fontWeights.bold} my={spacing.xs}>
                        {stats?.total_users || 0}
                      </StatNumber>
                      <StatHelpText opacity={0.9}>
                        <VStack align="start" spacing={1}>
                          {stats?.users?.trend ? (
                            <HStack spacing={1}>
                              <Icon
                                as={stats.users.trend.direction === 'up' ? FiTrendingUp : stats.users.trend.direction === 'down' ? FiTrendingDown : FiUsers}
                                color={stats.users.trend.is_positive ? 'green.300' : 'red.300'}
                              />
                              <Text color={stats.users.trend.is_positive ? 'green.300' : 'red.300'}>
                                {stats.users.trend.direction !== 'neutral' && (stats.users.trend.direction === 'up' ? '+' : '-')}
                                {Math.abs(stats.users.change_percentage || 0).toFixed(1)}% за период
                              </Text>
                            </HStack>
                          ) : (
                            <HStack spacing={1}>
                              <Icon as={FiUsers} />
                              <Text>Активные пользователи</Text>
                            </HStack>
                          )}
                          {stats?.conversion_rate && (
                            <HStack spacing={1} fontSize="xs">
                              <Icon as={FiShoppingBag} />
                              <Text>
                                Конверсия: {stats.conversion_rate.current_value}%
                                {stats.conversion_rate.change_percentage !== 0 && (
                                  <Text as="span" ml={1} color={stats.conversion_rate.change_percentage > 0 ? 'green.300' : 'red.300'}>
                                    ({stats.conversion_rate.change_percentage > 0 ? '+' : ''}{stats.conversion_rate.change_percentage.toFixed(1)}%)
                                  </Text>
                                )}
                              </Text>
                            </HStack>
                          )}
                        </VStack>
                      </StatHelpText>
                    </Stat>
                    {stats?.users?.sparkline?.values?.length > 0 && (
                      <Box ml={2} mt={-1}>
                        <Sparkline
                          data={stats.users.sparkline.values}
                          width={80}
                          height={40}
                          color="rgba(255, 255, 255, 0.8)"
                          strokeWidth={2}
                        />
                      </Box>
                    )}
                  </Flex>
                </CardBody>
              </Card>

              <Card
                bgGradient={colors.stats.bookings.gradient}
                color="white"
                borderRadius={styles.card.borderRadius}
                boxShadow="lg"
                transition="all 0.3s ease"
                _hover={{
                  transform: styles.card.hoverTransform,
                  boxShadow: styles.card.hoverShadow
                }}
              >
                <CardBody p={spacing.md}>
                  <Flex justify="space-between" align="flex-start">
                    <Stat flex="1">
                      <StatLabel fontSize={typography.fontSizes.sm} fontWeight={typography.fontWeights.medium} opacity={0.9}>
                        Всего бронирований
                      </StatLabel>
                      <StatNumber fontSize={typography.fontSizes['3xl']} fontWeight={typography.fontWeights.bold} my={spacing.xs}>
                        {stats?.total_bookings || 0}
                      </StatNumber>
                      <StatHelpText opacity={0.9}>
                        {stats?.bookings?.trend ? (
                          <HStack spacing={1}>
                            <Icon
                              as={stats.bookings.trend.direction === 'up' ? FiTrendingUp : stats.bookings.trend.direction === 'down' ? FiTrendingDown : FiShoppingBag}
                              color={stats.bookings.trend.is_positive ? 'green.300' : 'red.300'}
                            />
                            <Text color={stats.bookings.trend.is_positive ? 'green.300' : 'red.300'}>
                              {stats.bookings.trend.direction !== 'neutral' && (stats.bookings.trend.direction === 'up' ? '+' : '-')}
                              {Math.abs(stats.bookings.change_percentage || 0).toFixed(1)}% за период
                            </Text>
                          </HStack>
                        ) : (
                          <HStack spacing={1}>
                            <Icon as={FiShoppingBag} />
                            <Text>Все бронирования</Text>
                          </HStack>
                        )}
                      </StatHelpText>
                    </Stat>
                    {stats?.bookings?.sparkline?.values?.length > 0 && (
                      <Box ml={2} mt={-1}>
                        <Sparkline
                          data={stats.bookings.sparkline.values}
                          width={80}
                          height={40}
                          color="rgba(255, 255, 255, 0.8)"
                          strokeWidth={2}
                        />
                      </Box>
                    )}
                  </Flex>
                </CardBody>
              </Card>

              <Card
                bgGradient={colors.stats.average_booking_value.gradient}
                color="white"
                borderRadius={styles.card.borderRadius}
                boxShadow="lg"
                transition="all 0.3s ease"
                _hover={{
                  transform: styles.card.hoverTransform,
                  boxShadow: styles.card.hoverShadow
                }}
              >
                <CardBody p={spacing.md}>
                  <Flex justify="space-between" align="flex-start">
                    <Stat flex="1">
                      <StatLabel fontSize={typography.fontSizes.sm} fontWeight={typography.fontWeights.medium} opacity={0.9}>
                        Средний чек
                      </StatLabel>
                      <StatNumber fontSize={typography.fontSizes['3xl']} fontWeight={typography.fontWeights.bold} my={spacing.xs}>
                        ₽{stats?.average_booking_value?.current_value?.toLocaleString('ru-RU', { minimumFractionDigits: 0, maximumFractionDigits: 0 }) || 0}
                      </StatNumber>
                      <StatHelpText opacity={0.9}>
                        {stats?.average_booking_value?.trend ? (
                          <HStack spacing={1}>
                            <Icon
                              as={stats.average_booking_value.trend.direction === 'up' ? FiTrendingUp : stats.average_booking_value.trend.direction === 'down' ? FiTrendingDown : FiDollarSign}
                              color={stats.average_booking_value.trend.is_positive ? 'green.300' : 'red.300'}
                            />
                            <Text color={stats.average_booking_value.trend.is_positive ? 'green.300' : 'red.300'}>
                              {stats.average_booking_value.trend.direction !== 'neutral' && (stats.average_booking_value.trend.direction === 'up' ? '+' : '-')}
                              {Math.abs(stats.average_booking_value.change_percentage || 0).toFixed(1)}% за период
                            </Text>
                          </HStack>
                        ) : (
                          <HStack spacing={1}>
                            <Icon as={FiDollarSign} />
                            <Text>Средняя сумма</Text>
                          </HStack>
                        )}
                      </StatHelpText>
                    </Stat>
                    {stats?.average_booking_value?.sparkline?.values?.length > 0 && (
                      <Box ml={2} mt={-1}>
                        <Sparkline
                          data={stats.average_booking_value.sparkline.values}
                          width={80}
                          height={40}
                          color="rgba(255, 255, 255, 0.8)"
                          strokeWidth={2}
                        />
                      </Box>
                    )}
                  </Flex>
                </CardBody>
              </Card>

              <Card
                bgGradient={colors.stats.tickets.gradient}
                color="white"
                borderRadius={styles.card.borderRadius}
                boxShadow="lg"
                transition="all 0.3s ease"
                _hover={{
                  transform: styles.card.hoverTransform,
                  boxShadow: styles.card.hoverShadow
                }}
              >
                <CardBody p={spacing.md}>
                  <Flex justify="space-between" align="flex-start">
                    <Stat flex="1">
                      <StatLabel fontSize={typography.fontSizes.sm} fontWeight={typography.fontWeights.medium} opacity={0.9}>
                        Открытые заявки
                      </StatLabel>
                      <StatNumber fontSize={typography.fontSizes['3xl']} fontWeight={typography.fontWeights.bold} my={spacing.xs}>
                        {stats?.open_tickets || 0}
                      </StatNumber>
                      <StatHelpText opacity={0.9}>
                        {stats?.tickets?.trend ? (
                          <HStack spacing={1}>
                            <Icon
                              as={stats.tickets.trend.direction === 'up' ? FiTrendingUp : stats.tickets.trend.direction === 'down' ? FiTrendingDown : FiMessageCircle}
                              color={stats.tickets.trend.is_positive ? 'green.300' : 'red.300'}
                            />
                            <Text color={stats.tickets.trend.is_positive ? 'green.300' : 'red.300'}>
                              {stats.tickets.trend.direction !== 'neutral' && (stats.tickets.trend.direction === 'up' ? '+' : '-')}
                              {Math.abs(stats.tickets.change_percentage || 0).toFixed(1)}% за период
                            </Text>
                          </HStack>
                        ) : (
                          <HStack spacing={1}>
                            <Icon as={FiMessageCircle} />
                            <Text>Требуют внимания</Text>
                          </HStack>
                        )}
                      </StatHelpText>
                    </Stat>
                    {stats?.tickets?.sparkline?.values?.length > 0 && (
                      <Box ml={2} mt={-1}>
                        <Sparkline
                          data={stats.tickets.sparkline.values}
                          width={80}
                          height={40}
                          color="rgba(255, 255, 255, 0.8)"
                          strokeWidth={2}
                        />
                      </Box>
                    )}
                  </Flex>
                </CardBody>
              </Card>
            </>
          )}
        </SimpleGrid>

        {/* Аккордеон с графиком */}
        <Card
          bg={styles.card.bg}
          borderRadius={styles.card.borderRadius}
          boxShadow="lg"
          overflow="hidden"
        >
          <CardHeader
            bg="white"
            borderBottom="2px"
            borderColor="gray.100"
            p={6}
            cursor="pointer"
            onClick={toggleChartOpen}
            _hover={{ bg: "gray.50" }}
          >
            <Flex align="center" justify="space-between">
              <Flex align="center">
                <Icon as={FiTrendingUp} boxSize={6} color="purple.500" mr={3} />
                <Heading size="md" color={colors.text.primary} fontSize={typography.fontSizes.lg} fontWeight={typography.fontWeights.bold}>
                  Активность за месяц
                </Heading>
                {chartData && (
                  <Badge ml={3} colorScheme="purple" variant="subtle">
                    {chartData.period.month_name} {chartData.period.year}
                  </Badge>
                )}
              </Flex>
              <Icon 
                as={FiChevronRight} 
                boxSize={5} 
                color="gray.500"
                transition="transform 0.2s"
                transform={isChartOpen ? 'rotate(90deg)' : 'rotate(0deg)'}
              />
            </Flex>
          </CardHeader>

          <Collapse in={isChartOpen} animateOpacity>
            <CardBody p={6} bg="white">
              <Flex align="center" justify="space-between" mb={4} wrap="wrap" gap={4}>
                {/* Итоги за месяц */}
                {chartData && chartData.totals && (
                  <HStack spacing={4} fontSize="sm" color="gray.600">
                    <Text>
                      <Icon as={FiUsers} mr={1} />
                      {chartData.totals.users} чел.
                    </Text>
                    <Text>
                      <Icon as={FiMessageCircle} mr={1} />
                      {chartData.totals.tickets} тик.
                    </Text>
                    <Text>
                      <Icon as={FiShoppingBag} mr={1} />
                      {chartData.totals.bookings} брон.
                    </Text>
                  </HStack>
                )}

                {/* Выбор месяца */}
                <Flex align="center" gap={2}>
                  <Icon as={FiCalendar} color="gray.500" />
                  <Select
                    value={`${selectedPeriod.year}-${selectedPeriod.month}`}
                    onChange={handlePeriodChange}
                    size="sm"
                    w="200px"
                    bg="white"
                    disabled={isLoadingChart}
                  >
                    {availablePeriods.map((period) => (
                      <option
                        key={`${period.year}-${period.month}`}
                        value={`${period.year}-${period.month}`}
                      >
                        {period.display}
                      </option>
                    ))}
                  </Select>

                  {/* Checkbox для включения режима сравнения */}
                  <Checkbox
                    isChecked={isCompareMode}
                    onChange={(e) => setIsCompareMode(e.target.checked)}
                    size="sm"
                    colorScheme="purple"
                    disabled={isLoadingChart}
                  >
                    Сравнить с периодом
                  </Checkbox>

                  {/* Dropdown для выбора второго периода */}
                  {isCompareMode && (
                    <Flex align="center" gap={2}>
                      <Icon as={FiCalendar} color="gray.500" />
                      <Select
                        value={`${comparePeriod.year}-${comparePeriod.month + 1}`}
                        onChange={(e) => {
                          const [year, month] = e.target.value.split('-').map(Number);
                          setComparePeriod({ year, month: month - 1 });
                        }}
                        size="sm"
                        w="200px"
                        bg="white"
                        disabled={isLoadingChart}
                      >
                        {availablePeriods.map((period) => (
                          <option
                            key={`compare-${period.year}-${period.month}`}
                            value={`${period.year}-${period.month}`}
                          >
                            {period.display}
                          </option>
                        ))}
                      </Select>
                    </Flex>
                  )}

                  {/* Кнопка экспорта */}
                  <Menu>
                    <MenuButton
                      as={Button}
                      leftIcon={<Icon as={FiDownload} />}
                      size="sm"
                      colorScheme="purple"
                      variant="outline"
                      disabled={isLoadingChart}
                    >
                      Экспорт
                    </MenuButton>
                    <MenuList>
                      <MenuItem
                        icon={<Icon as={FiDownload} />}
                        onClick={handleExportCSV}
                      >
                        Экспорт в CSV
                      </MenuItem>
                      <MenuItem
                        icon={<Icon as={FiDownload} />}
                        onClick={handleExportExcel}
                      >
                        Экспорт в Excel
                      </MenuItem>
                    </MenuList>
                  </Menu>
                </Flex>
              </Flex>

              {chartError && (
                <Alert status="error" mb={4}>
                  <AlertIcon />
                  Ошибка загрузки данных: {chartError}
                </Alert>
              )}

              <Box h={styles.chart.height} position="relative">
                {isLoadingChart ? (
                  // Skeleton для графика
                  <VStack spacing={4} align="stretch" h="100%">
                    <HStack spacing={4} justify="center">
                      <Skeleton height="12px" width="120px" />
                      <Skeleton height="12px" width="120px" />
                      <Skeleton height="12px" width="120px" />
                    </HStack>
                    <Box flex="1" position="relative">
                      <Skeleton height="100%" width="100%" startColor="purple.50" endColor="purple.100" />
                      <Box position="absolute" bottom="0" left="0" right="0" h="60%" opacity={0.3}>
                        <svg width="100%" height="100%" viewBox="0 0 400 200" preserveAspectRatio="none">
                          <path
                            d="M 0,180 L 50,150 L 100,170 L 150,120 L 200,140 L 250,100 L 300,130 L 350,90 L 400,110"
                            stroke="purple"
                            strokeWidth="3"
                            fill="none"
                            opacity="0.4"
                          />
                        </svg>
                      </Box>
                    </Box>
                    <HStack spacing={4} justify="space-between">
                      {[...Array(7)].map((_, i) => (
                        <Skeleton key={i} height="8px" width="30px" />
                      ))}
                    </HStack>
                  </VStack>
                ) : (
                  <canvas ref={chartRef}></canvas>
                )}
              </Box>

              {/* Чекбоксы для управления видимостью линий */}
              {!isLoadingChart && chartData && (
                <Flex mt={4} gap={6} justify="center" wrap="wrap">
                  <Checkbox
                    isChecked={visibleDatasets.users}
                    onChange={() => toggleDatasetVisibility('users')}
                    colorScheme="blue"
                  >
                    <HStack spacing={2}>
                      <Box w={3} h={3} bg="#3B82F6" borderRadius="full" />
                      <Text fontSize="sm" fontWeight="medium">
                        Регистрации пользователей
                      </Text>
                    </HStack>
                  </Checkbox>
                  <Checkbox
                    isChecked={visibleDatasets.tickets}
                    onChange={() => toggleDatasetVisibility('tickets')}
                    colorScheme="orange"
                  >
                    <HStack spacing={2}>
                      <Box w={3} h={3} bg="#F59E0B" borderRadius="full" />
                      <Text fontSize="sm" fontWeight="medium">
                        Создание тикетов
                      </Text>
                    </HStack>
                  </Checkbox>
                  <Checkbox
                    isChecked={visibleDatasets.bookings}
                    onChange={() => toggleDatasetVisibility('bookings')}
                    colorScheme="green"
                  >
                    <HStack spacing={2}>
                      <Box w={3} h={3} bg="#10B981" borderRadius="full" />
                      <Text fontSize="sm" fontWeight="medium">
                        Бронирования
                      </Text>
                    </HStack>
                  </Checkbox>
                </Flex>
              )}
            </CardBody>
          </Collapse>
        </Card>

        {/* Аккордеон с календарем бронирований */}
        <Card
          bg={styles.card.bg}
          borderRadius={styles.card.borderRadius}
          boxShadow="lg"
          overflow="hidden"
        >
          <CardHeader
            bg="white"
            borderBottom="2px"
            borderColor="gray.100"
            p={6}
            cursor="pointer"
            onClick={toggleCalendarOpen}
            _hover={{ bg: "gray.50" }}
          >
            <Flex align="center" justify="space-between">
              <Flex align="center">
                <Icon as={FiCalendar} boxSize={6} color="green.500" mr={3} />
                <Heading size="md" color={colors.text.primary} fontSize={typography.fontSizes.lg} fontWeight={typography.fontWeights.bold}>
                  Календарь бронирований
                </Heading>
                <Badge ml={3} colorScheme="green" variant="subtle">
                  {calendarDate.toLocaleDateString('ru-RU', { month: 'long', year: 'numeric' })}
                </Badge>
              </Flex>
              <Icon 
                as={FiChevronRight} 
                boxSize={5} 
                color="gray.500"
                transition="transform 0.2s"
                transform={isCalendarOpen ? 'rotate(90deg)' : 'rotate(0deg)'}
              />
            </Flex>
          </CardHeader>

          <Collapse in={isCalendarOpen} animateOpacity>
            <CardBody p={6} bg="white">
              {/* Навигация по месяцам */}
              <Flex align="center" justify="space-between" mb={6}>
                <Button
                  leftIcon={<FiChevronLeft />}
                  variant="ghost"
                  size="sm"
                  onClick={() => navigateMonth('prev')}
                  disabled={isLoadingBookings}
                >
                  Предыдущий
                </Button>
                <Heading size="md" color={colors.text.primary}>
                  {calendarDate.toLocaleDateString('ru-RU', { month: 'long', year: 'numeric' })}
                </Heading>
                <Button
                  rightIcon={<FiChevronRight />}
                  variant="ghost"
                  size="sm"
                  onClick={() => navigateMonth('next')}
                  disabled={isLoadingBookings}
                >
                  Следующий
                </Button>
              </Flex>

              {/* Фильтры */}
              <Box mb={4} p={4} bg="gray.50" borderRadius="md">
                <VStack spacing={3} align="stretch">
                  {/* Поиск по пользователю */}
                  <Box>
                    <Text fontSize="sm" fontWeight="medium" mb={2}>
                      Поиск по пользователю
                    </Text>
                    <InputGroup size="sm">
                      <InputLeftElement pointerEvents="none">
                        <Icon as={FiSearch} color="gray.400" />
                      </InputLeftElement>
                      <Input
                        placeholder="Имя пользователя или Telegram ID..."
                        value={userSearchText}
                        onChange={handleUserSearchChange}
                        bg="white"
                      />
                    </InputGroup>
                  </Box>

                  {/* Фильтр по тарифам */}
                  <Box>
                    <Flex justify="space-between" align="center" mb={2}>
                      <Text fontSize="sm" fontWeight="medium">
                        Фильтр по тарифам
                      </Text>
                      {hasActiveFilters && (
                        <Button
                          size="xs"
                          variant="ghost"
                          colorScheme="blue"
                          leftIcon={<Icon as={FiX} />}
                          onClick={handleClearFilters}
                        >
                          Очистить фильтры
                        </Button>
                      )}
                    </Flex>
                    <Wrap spacing={2}>
                      {availableTariffs.map((tariff) => (
                        <WrapItem key={tariff.id}>
                          <Tag
                            size="md"
                            variant={selectedTariffIds.includes(tariff.id) ? 'solid' : 'outline'}
                            colorScheme="blue"
                            cursor="pointer"
                            onClick={() => handleTariffToggle(tariff.id)}
                            _hover={{
                              transform: 'translateY(-2px)',
                              boxShadow: 'sm'
                            }}
                            transition="all 0.2s"
                          >
                            <TagLabel>{tariff.name}</TagLabel>
                            {selectedTariffIds.includes(tariff.id) && (
                              <TagCloseButton onClick={(e) => {
                                e.stopPropagation();
                                handleTariffToggle(tariff.id);
                              }} />
                            )}
                          </Tag>
                        </WrapItem>
                      ))}
                    </Wrap>
                  </Box>

                  {/* Счетчик бронирований */}
                  {hasActiveFilters && totalBookingsCount > 0 && (
                    <Flex justify="flex-end">
                      <Text fontSize="sm" color="gray.600">
                        Показано <Text as="span" fontWeight="bold" color="blue.600">{filteredBookingsCount}</Text> из{' '}
                        <Text as="span" fontWeight="bold">{totalBookingsCount}</Text> бронирований
                      </Text>
                    </Flex>
                  )}
                </VStack>
              </Box>

              {bookingsError && (
                <Alert status="error" mb={4}>
                  <AlertIcon />
                  Ошибка загрузки календаря: {bookingsError}
                </Alert>
              )}

              {/* Календарная сетка */}
              <Box position="relative">
                {isLoadingBookings ? (
                  // Skeleton для календаря
                  <Box>
                    <Grid templateColumns="repeat(7, 1fr)" gap={1} mb={2}>
                      {['Вс', 'Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб'].map((day) => (
                        <GridItem key={day} p={2} textAlign="center">
                          <Text fontSize="sm" fontWeight="bold" color="gray.600">
                            {day}
                          </Text>
                        </GridItem>
                      ))}
                    </Grid>
                    <Grid templateColumns="repeat(7, 1fr)" gap={1}>
                      {[...Array(35)].map((_, index) => (
                        <GridItem key={index}>
                          <Box
                            p={2}
                            minH="60px"
                            border="1px"
                            borderColor="gray.200"
                            borderRadius="md"
                            bg="white"
                          >
                            <Skeleton height="14px" width="20px" mb={2} />
                            <VStack spacing={1} align="stretch">
                              <Skeleton height="20px" width="100%" />
                              <Skeleton height="20px" width="100%" />
                            </VStack>
                          </Box>
                        </GridItem>
                      ))}
                    </Grid>
                  </Box>
                ) : (
                  <>
                    <Grid templateColumns="repeat(7, 1fr)" gap={1} mb={2}>
                  {['Вс', 'Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб'].map((day) => (
                    <GridItem key={day} p={2} textAlign="center">
                      <Text fontSize="sm" fontWeight="bold" color="gray.600">
                        {day}
                      </Text>
                    </GridItem>
                  ))}
                </Grid>

                <Grid templateColumns="repeat(7, 1fr)" gap={1}>
                  {getCalendarDays().map((date, index) => {
                    const bookings = getBookingsForDate(date);
                    const isCurrentMonth = date.getMonth() === calendarDate.getMonth();
                    const isToday = date.toDateString() === new Date().toDateString();
                    
                    return (
                      <GridItem key={index}>
                        <Box
                          p={2}
                          minH="60px"
                          border="1px"
                          borderColor={isToday ? "blue.300" : "gray.200"}
                          borderRadius="md"
                          bg={isToday ? "blue.50" : isCurrentMonth ? "white" : "gray.50"}
                          opacity={isCurrentMonth ? 1 : 0.5}
                          position="relative"
                          cursor={bookings.length > 0 ? "pointer" : "default"}
                          _hover={{
                            bg: bookings.length > 0 ? (isToday ? "blue.100" : "gray.100") : (isCurrentMonth ? "white" : "gray.50"),
                            borderColor: bookings.length > 0 ? "blue.400" : (isToday ? "blue.300" : "gray.200")
                          }}
                          onClick={() => bookings.length > 0 && handleDayClick(date)}
                        >
                          <Text
                            fontSize="sm"
                            fontWeight={isToday ? "bold" : "normal"}
                            color={isCurrentMonth ? "gray.800" : "gray.500"}
                            mb={1}
                          >
                            {date.getDate()}
                          </Text>

                          {bookings.length > 0 && (
                            <VStack spacing={1} align="stretch">
                              {bookings.slice(0, 3).map((booking) => (
                                <Tooltip
                                  key={booking.id}
                                  label={`Бронирование #${booking.id} - ${booking.user_name || 'Без имени'}`}
                                  placement="top"
                                >
                                  <Box
                                    fontSize="xs"
                                    p={1}
                                    bg={booking.confirmed ? "green.100" : "yellow.100"}
                                    color={booking.confirmed ? "green.800" : "yellow.800"}
                                    borderRadius="sm"
                                    cursor="pointer"
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      handleBookingClick(booking);
                                    }}
                                    _hover={{
                                      bg: booking.confirmed ? "green.200" : "yellow.200"
                                    }}
                                    noOfLines={1}
                                  >
                                    #{booking.id}
                                  </Box>
                                </Tooltip>
                              ))}
                              {bookings.length > 3 && (
                                <Box
                                  fontSize="xs"
                                  color="blue.600"
                                  textAlign="center"
                                  fontWeight="medium"
                                  _hover={{ color: "blue.800", textDecoration: "underline" }}
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    handleDayClick(date);
                                  }}
                                >
                                  +{bookings.length - 3} еще...
                                </Box>
                              )}
                            </VStack>
                          )}
                        </Box>
                      </GridItem>
                    );
                  })}
                </Grid>

                    {/* Легенда */}
                    <Flex mt={4} gap={4} justify="center" fontSize="sm" color="gray.600">
                      <Flex align="center" gap={1}>
                        <Box w={3} h={3} bg="green.100" borderRadius="sm" />
                        <Text>Подтвержденные</Text>
                      </Flex>
                      <Flex align="center" gap={1}>
                        <Box w={3} h={3} bg="yellow.100" borderRadius="sm" />
                        <Text>Ожидают подтверждения</Text>
                      </Flex>
                      <Flex align="center" gap={1}>
                        <Box w={3} h={3} bg="blue.50" border="1px" borderColor="blue.300" borderRadius="sm" />
                        <Text>Сегодня</Text>
                      </Flex>
                    </Flex>
                  </>
                )}
              </Box>
            </CardBody>
          </Collapse>
        </Card>

        {/* Распределение тарифов */}
        <Card borderRadius={styles.card.borderRadius} boxShadow="lg" mb={spacing.md}>
          <CardHeader
            cursor="pointer"
            onClick={() => {
              const newValue = !isTariffChartOpen;
              setIsTariffChartOpen(newValue);
              localStorage.setItem('dashboard_tariff_chart_open', JSON.stringify(newValue));
            }}
            bg={colors.background.card}
            _hover={{ bg: colors.background.main }}
            transition="all 0.2s"
            borderRadius={styles.card.borderRadius}
          >
            <Flex justify="space-between" align="center">
              <HStack spacing={spacing.sm}>
                <Icon as={FiChevronDown}
                  transform={isTariffChartOpen ? 'rotate(0deg)' : 'rotate(-90deg)'}
                  transition="transform 0.2s"
                />
                <Heading size="md" color={colors.text.primary}>Популярные тарифы</Heading>
              </HStack>
            </Flex>
          </CardHeader>
          <Collapse in={isTariffChartOpen} animateOpacity>
            <CardBody>
              <Box>
                {isLoadingTariffs ? (
                  <Flex justify="center" align="center" h="300px">
                    <Spinner size="xl" color="purple.500" />
                  </Flex>
                ) : tariffError ? (
                  <Alert status="error" borderRadius="md">
                    <AlertIcon />
                    {tariffError}
                  </Alert>
                ) : tariffDistribution?.data?.length === 0 ? (
                  <Flex justify="center" align="center" h="300px">
                    <VStack spacing={3}>
                      <Icon as={FiShoppingBag} boxSize={12} color="gray.400" />
                      <Text color="gray.600" fontSize="lg">Нет данных о бронированиях за выбранный период</Text>
                    </VStack>
                  </Flex>
                ) : (
                  <>
                    <Box h="400px" mb={6}>
                      <ResponsiveContainer width="100%" height="100%">
                        <PieChart>
                          <Pie
                            data={tariffDistribution?.data || []}
                            cx="50%"
                            cy="50%"
                            labelLine={false}
                            label={({ name, percentage }) => `${name}: ${percentage}%`}
                            outerRadius={120}
                            fill="#8884d8"
                            dataKey="value"
                          >
                            {(tariffDistribution?.data || []).map((entry, index) => {
                              const COLORS = ['#3182CE', '#38A169', '#805AD5', '#DD6B20', '#E53E3E'];
                              return <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />;
                            })}
                          </Pie>
                          <RechartsTooltip
                            content={({ active, payload }) => {
                              if (active && payload && payload.length) {
                                const data = payload[0].payload;
                                return (
                                  <Box
                                    bg="white"
                                    p={3}
                                    borderRadius="md"
                                    boxShadow="lg"
                                    border="1px"
                                    borderColor="gray.200"
                                  >
                                    <Text fontWeight="bold" mb={1}>{data.name}</Text>
                                    <Text fontSize="sm" color="gray.600">Бронирований: {data.value}</Text>
                                    <Text fontSize="sm" color="gray.600">Доход: ₽{data.revenue?.toLocaleString('ru-RU')}</Text>
                                    <Text fontSize="sm" color="gray.600">Процент: {data.percentage}%</Text>
                                  </Box>
                                );
                              }
                              return null;
                            }}
                          />
                          <Legend
                            verticalAlign="bottom"
                            height={36}
                            formatter={(value, entry) => {
                              const data = entry.payload;
                              return `${value} (${data.value})`;
                            }}
                          />
                        </PieChart>
                      </ResponsiveContainer>
                    </Box>

                    {/* Статистика */}
                    <Box mt={6} p={4} bg="gray.50" borderRadius="md">
                      <SimpleGrid columns={{ base: 1, md: 3 }} spacing={4}>
                        <Stat>
                          <StatLabel>Всего бронирований</StatLabel>
                          <StatNumber>{tariffDistribution?.total_bookings || 0}</StatNumber>
                        </Stat>
                        <Stat>
                          <StatLabel>Общий доход</StatLabel>
                          <StatNumber>₽{tariffDistribution?.total_revenue?.toLocaleString('ru-RU', { minimumFractionDigits: 0, maximumFractionDigits: 0 }) || 0}</StatNumber>
                        </Stat>
                        <Stat>
                          <StatLabel>Активных тарифов</StatLabel>
                          <StatNumber>{tariffDistribution?.data?.length || 0}</StatNumber>
                        </Stat>
                      </SimpleGrid>
                    </Box>
                  </>
                )}
              </Box>
            </CardBody>
          </Collapse>
        </Card>

        {/* Аккордеон с топ-клиентами */}
        <Card
          bg={styles.card.bg}
          borderRadius={styles.card.borderRadius}
          boxShadow="lg"
          overflow="hidden"
        >
          <CardHeader
            bg="white"
            borderBottom="2px"
            borderColor="gray.100"
            p={6}
            cursor="pointer"
            onClick={toggleTopClientsOpen}
            _hover={{ bg: "gray.50" }}
          >
            <Flex align="center" justify="space-between">
              <Flex align="center">
                <Icon as={FiAward} boxSize={6} color="orange.500" mr={3} />
                <Heading size="md" color={colors.text.primary}>Топ клиенты</Heading>
                {topClientsData && (
                  <Badge ml={3} colorScheme="orange" variant="subtle">
                    {topClientsData.period.month_name} {topClientsData.period.year}
                  </Badge>
                )}
              </Flex>
              <Icon
                as={FiChevronRight}
                boxSize={5}
                color="gray.500"
                transition="transform 0.2s"
                transform={isTopClientsOpen ? 'rotate(90deg)' : 'rotate(0deg)'}
              />
            </Flex>
          </CardHeader>

          <Collapse in={isTopClientsOpen} animateOpacity>
            <CardBody p={6} bg="white">
              {topClientsError && (
                <Alert status="error" mb={4}>
                  <AlertIcon />
                  {topClientsError}
                </Alert>
              )}

              <Box>
                {isLoadingTopClients ? (
                  // Skeleton для таблицы
                  <VStack spacing={3} align="stretch">
                    {[...Array(5)].map((_, i) => (
                      <Skeleton key={i} height="60px" borderRadius="md" />
                    ))}
                  </VStack>
                ) : topClientsData && topClientsData.clients.length > 0 ? (
                  <>
                    {/* Таблица топ-клиентов */}
                    <TableContainer>
                      <Table variant="simple" size="sm">
                        <Thead bg="gray.50">
                          <Tr>
                            <Th w="60px">#</Th>
                            <Th>Клиент</Th>
                            <Th isNumeric>Бронирований</Th>
                            <Th isNumeric>Оплачено</Th>
                            <Th isNumeric>Общая сумма</Th>
                            <Th isNumeric>Средний чек</Th>
                            <Th isNumeric>% от дохода</Th>
                            <Th>Последнее бронирование</Th>
                          </Tr>
                        </Thead>
                        <Tbody>
                          {topClientsData.clients.map((client, index) => (
                            <Tr key={client.user_id} _hover={{ bg: 'gray.50' }} transition="background 0.2s">
                              <Td>
                                <Flex align="center" justify="center">
                                  <Icon
                                    as={FiAward}
                                    color={index === 0 ? 'yellow.500' : index === 1 ? 'gray.400' : index === 2 ? 'orange.600' : 'gray.300'}
                                    boxSize={5}
                                  />
                                  <Text ml={2} fontWeight="bold">{index + 1}</Text>
                                </Flex>
                              </Td>
                              <Td>
                                <VStack align="start" spacing={0}>
                                  <Text fontWeight="medium">{client.username}</Text>
                                  <Text fontSize="xs" color="gray.500">ID: {client.telegram_id}</Text>
                                </VStack>
                              </Td>
                              <Td isNumeric>
                                <Badge colorScheme="blue" variant="subtle">{client.total_bookings}</Badge>
                              </Td>
                              <Td isNumeric>
                                <Badge colorScheme="green" variant="subtle">{client.paid_bookings}</Badge>
                              </Td>
                              <Td isNumeric>
                                <Text fontWeight="bold" color="green.600">
                                  ₽{client.total_spent.toLocaleString('ru-RU', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
                                </Text>
                              </Td>
                              <Td isNumeric>
                                <Text>
                                  ₽{client.avg_booking_value.toLocaleString('ru-RU', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
                                </Text>
                              </Td>
                              <Td isNumeric>
                                <Badge
                                  colorScheme={client.revenue_share > 20 ? 'orange' : client.revenue_share > 10 ? 'yellow' : 'gray'}
                                  variant="solid"
                                >
                                  {client.revenue_share.toFixed(1)}%
                                </Badge>
                              </Td>
                              <Td>
                                <Text fontSize="sm" color="gray.600">
                                  {client.last_booking_date
                                    ? new Date(client.last_booking_date).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' })
                                    : '-'}
                                </Text>
                              </Td>
                            </Tr>
                          ))}
                        </Tbody>
                      </Table>
                    </TableContainer>

                    {/* Общая статистика */}
                    {topClientsData.stats && (
                      <Box mt={6} p={4} bg="orange.50" borderRadius="md" borderLeft="4px solid" borderColor="orange.500">
                        <SimpleGrid columns={{ base: 1, md: 4 }} spacing={4}>
                          <Stat>
                            <StatLabel fontSize="sm">Всего клиентов с бронированиями</StatLabel>
                            <StatNumber fontSize="2xl">{topClientsData.stats.total_clients_with_bookings}</StatNumber>
                          </Stat>
                          <Stat>
                            <StatLabel fontSize="sm">Общий доход</StatLabel>
                            <StatNumber fontSize="2xl">₽{topClientsData.stats.total_revenue.toLocaleString('ru-RU', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}</StatNumber>
                          </Stat>
                          <Stat>
                            <StatLabel fontSize="sm">Доход от топ-{topClientsData.clients.length}</StatLabel>
                            <StatNumber fontSize="2xl">₽{topClientsData.stats.top_clients_revenue.toLocaleString('ru-RU', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}</StatNumber>
                          </Stat>
                          <Stat>
                            <StatLabel fontSize="sm">Доля топ-клиентов</StatLabel>
                            <StatNumber fontSize="2xl" color="orange.600">{topClientsData.stats.top_clients_share.toFixed(1)}%</StatNumber>
                            <StatHelpText>от общего дохода</StatHelpText>
                          </Stat>
                        </SimpleGrid>
                      </Box>
                    )}
                  </>
                ) : (
                  // Empty state
                  <VStack py={8} spacing={3}>
                    <Icon as={FiAward} boxSize={12} color="gray.300" />
                    <Text color="gray.500">Нет данных о клиентах за выбранный период</Text>
                  </VStack>
                )}
              </Box>
            </CardBody>
          </Collapse>
        </Card>

        {/* Аккордеон со статистикой промокодов */}
        <Card
          bg={styles.card.bg}
          borderRadius={styles.card.borderRadius}
          boxShadow="lg"
          overflow="hidden"
        >
          <CardHeader
            bg="white"
            borderBottom="2px"
            borderColor="gray.100"
            p={6}
            cursor="pointer"
            onClick={togglePromocodesOpen}
            _hover={{ bg: "gray.50" }}
          >
            <Flex align="center" justify="space-between">
              <Flex align="center">
                <Icon as={FiTag} boxSize={6} color="green.500" mr={3} />
                <Heading size="md" color={colors.text.primary}>Эффективность промокодов</Heading>
                {promocodeStats && (
                  <Badge ml={3} colorScheme="green" variant="subtle">
                    {promocodeStats.period.label}
                  </Badge>
                )}
              </Flex>
              <Icon
                as={FiChevronRight}
                boxSize={5}
                color="gray.500"
                transition="transform 0.2s"
                transform={isPromocodesOpen ? 'rotate(90deg)' : 'rotate(0deg)'}
              />
            </Flex>
          </CardHeader>

          <Collapse in={isPromocodesOpen} animateOpacity>
            <CardBody p={6} bg="white">
              {promocodeError && (
                <Alert status="error" mb={4}>
                  <AlertIcon />
                  {promocodeError}
                </Alert>
              )}

              <Box>
                {isLoadingPromocodes ? (
                  // Skeleton для таблицы
                  <VStack spacing={3} align="stretch">
                    {[...Array(5)].map((_, i) => (
                      <Skeleton key={i} height="60px" borderRadius="md" />
                    ))}
                  </VStack>
                ) : promocodeStats && promocodeStats.promocodes.length > 0 ? (
                  <>
                    {/* Таблица промокодов */}
                    <TableContainer>
                      <Table variant="simple" size="sm">
                        <Thead bg="gray.50">
                          <Tr>
                            <Th>Промокод</Th>
                            <Th isNumeric>Скидка</Th>
                            <Th>Статус</Th>
                            <Th isNumeric>Использований</Th>
                            <Th isNumeric>Оплачено</Th>
                            <Th isNumeric>Общий доход</Th>
                            <Th isNumeric>Сумма скидок</Th>
                            <Th isNumeric>Средний чек</Th>
                            <Th isNumeric>Доход/исп.</Th>
                            <Th isNumeric>% от дохода</Th>
                            <Th>Последнее использование</Th>
                          </Tr>
                        </Thead>
                        <Tbody>
                          {promocodeStats.promocodes.map((promo) => (
                            <Tr key={promo.id} _hover={{ bg: 'gray.50' }} transition="background 0.2s">
                              <Td>
                                <Flex align="center">
                                  <Icon as={FiTag} color="green.500" mr={2} />
                                  <Text fontWeight="medium">{promo.name}</Text>
                                </Flex>
                              </Td>
                              <Td isNumeric>
                                <Badge colorScheme="purple" variant="solid">
                                  -{promo.discount_percent}%
                                </Badge>
                              </Td>
                              <Td>
                                <Badge colorScheme={promo.is_active ? 'green' : 'gray'} variant="subtle">
                                  {promo.is_active ? 'Активен' : 'Неактивен'}
                                </Badge>
                              </Td>
                              <Td isNumeric>
                                <Badge colorScheme="blue" variant="subtle">{promo.total_uses}</Badge>
                              </Td>
                              <Td isNumeric>
                                <Badge colorScheme="green" variant="subtle">{promo.paid_uses}</Badge>
                              </Td>
                              <Td isNumeric>
                                <Text fontWeight="bold" color="green.600">
                                  ₽{promo.total_revenue.toLocaleString('ru-RU', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
                                </Text>
                              </Td>
                              <Td isNumeric>
                                <Text color="red.600">
                                  -₽{promo.total_discount_given.toLocaleString('ru-RU', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
                                </Text>
                              </Td>
                              <Td isNumeric>
                                <Text>
                                  ₽{promo.avg_booking_value.toLocaleString('ru-RU', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
                                </Text>
                              </Td>
                              <Td isNumeric>
                                <Text fontWeight="medium" color="blue.600">
                                  ₽{promo.revenue_per_use.toLocaleString('ru-RU', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
                                </Text>
                              </Td>
                              <Td isNumeric>
                                <Badge
                                  colorScheme={promo.revenue_share > 15 ? 'green' : promo.revenue_share > 5 ? 'blue' : 'gray'}
                                  variant="solid"
                                >
                                  {promo.revenue_share.toFixed(1)}%
                                </Badge>
                              </Td>
                              <Td>
                                <Text fontSize="sm" color="gray.600">
                                  {promo.last_used_date
                                    ? new Date(promo.last_used_date).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short', year: 'numeric' })
                                    : '-'}
                                </Text>
                              </Td>
                            </Tr>
                          ))}
                        </Tbody>
                      </Table>
                    </TableContainer>

                    {/* Общая статистика */}
                    {promocodeStats.summary && (
                      <Box mt={6} p={4} bg="green.50" borderRadius="md" borderLeft="4px solid" borderColor="green.500">
                        <SimpleGrid columns={{ base: 1, md: 3, lg: 6 }} spacing={4}>
                          <Stat>
                            <StatLabel fontSize="sm">Всего промокодов</StatLabel>
                            <StatNumber fontSize="2xl">{promocodeStats.summary.total_promocodes}</StatNumber>
                            <StatHelpText fontSize="xs">
                              Активных: {promocodeStats.summary.active_promocodes}
                            </StatHelpText>
                          </Stat>
                          <Stat>
                            <StatLabel fontSize="sm">Использований</StatLabel>
                            <StatNumber fontSize="2xl">{promocodeStats.summary.total_uses}</StatNumber>
                          </Stat>
                          <Stat>
                            <StatLabel fontSize="sm">Общий доход</StatLabel>
                            <StatNumber fontSize="2xl" color="green.600">
                              ₽{promocodeStats.summary.total_revenue_with_promocodes.toLocaleString('ru-RU', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
                            </StatNumber>
                          </Stat>
                          <Stat>
                            <StatLabel fontSize="sm">Сумма скидок</StatLabel>
                            <StatNumber fontSize="2xl" color="red.600">
                              -₽{promocodeStats.summary.total_discount_given.toLocaleString('ru-RU', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
                            </StatNumber>
                          </Stat>
                          <Stat>
                            <StatLabel fontSize="sm">Средняя скидка</StatLabel>
                            <StatNumber fontSize="2xl">
                              ₽{promocodeStats.summary.avg_discount_per_booking.toLocaleString('ru-RU', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
                            </StatNumber>
                            <StatHelpText fontSize="xs">на бронирование</StatHelpText>
                          </Stat>
                          <Stat>
                            <StatLabel fontSize="sm">Экономия клиентов</StatLabel>
                            <StatNumber fontSize="2xl" color="orange.600">
                              {((promocodeStats.summary.total_discount_given / (promocodeStats.summary.total_revenue_with_promocodes + promocodeStats.summary.total_discount_given)) * 100).toFixed(1)}%
                            </StatNumber>
                            <StatHelpText fontSize="xs">от полной цены</StatHelpText>
                          </Stat>
                        </SimpleGrid>
                      </Box>
                    )}
                  </>
                ) : (
                  // Empty state
                  <VStack py={8} spacing={3}>
                    <Icon as={FiTag} boxSize={12} color="gray.300" />
                    <Text color="gray.500">Нет данных о промокодах за выбранный период</Text>
                  </VStack>
                )}
              </Box>
            </CardBody>
          </Collapse>
        </Card>

        {/* Модальное окно с деталями бронирований дня */}
        <Modal isOpen={isModalOpen} onClose={handleModalClose} size="4xl">
          <ModalOverlay />
          <ModalContent>
            <ModalHeader>
              <Flex align="center" gap={3}>
                <Icon as={FiCalendar} color="blue.500" boxSize={6} />
                <Box>
                  <Heading size="md">
                    Бронирования на {selectedDate?.toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', year: 'numeric' })}
                  </Heading>
                  <Text fontSize="sm" color="gray.600" fontWeight="normal">
                    Всего бронирований: {selectedDayBookings.length}
                  </Text>
                </Box>
              </Flex>
            </ModalHeader>
            <ModalCloseButton />
            <ModalBody pb={6}>
              <TableContainer>
                <Table variant="simple" size="sm">
                  <Thead>
                    <Tr>
                      <Th>Время</Th>
                      <Th>Клиент</Th>
                      <Th>Тариф</Th>
                      <Th isNumeric>Сумма</Th>
                      <Th>Статус</Th>
                      <Th></Th>
                    </Tr>
                  </Thead>
                  <Tbody>
                    {selectedDayBookings.map((booking) => (
                      <Tr
                        key={booking.id}
                        _hover={{ bg: 'gray.50' }}
                        transition="background 0.2s"
                      >
                        <Td>
                          <Text fontWeight="medium">
                            {booking.visit_time || '—'}
                          </Text>
                        </Td>
                        <Td>
                          <VStack align="flex-start" spacing={0}>
                            <Text fontWeight="medium">
                              {booking.user_name || 'Без имени'}
                            </Text>
                            <Text fontSize="xs" color="gray.600">
                              ID: {booking.telegram_id}
                            </Text>
                          </VStack>
                        </Td>
                        <Td>
                          <Text fontSize="sm">
                            {booking.tariff_name || '—'}
                          </Text>
                        </Td>
                        <Td isNumeric>
                          <Text fontWeight="semibold" color={booking.paid ? 'green.600' : 'gray.800'}>
                            ₽{booking.amount.toFixed(2)}
                          </Text>
                        </Td>
                        <Td>
                          <VStack align="flex-start" spacing={1}>
                            <Badge
                              colorScheme={booking.confirmed ? 'green' : 'yellow'}
                              variant="subtle"
                            >
                              {booking.confirmed ? 'Подтверждено' : 'Ожидает'}
                            </Badge>
                            {booking.paid && (
                              <Badge colorScheme="blue" variant="subtle" fontSize="xs">
                                Оплачено
                              </Badge>
                            )}
                          </VStack>
                        </Td>
                        <Td>
                          <Button
                            size="sm"
                            colorScheme="blue"
                            variant="ghost"
                            onClick={() => {
                              handleBookingClick(booking);
                              handleModalClose();
                            }}
                          >
                            Перейти
                          </Button>
                        </Td>
                      </Tr>
                    ))}
                  </Tbody>
                </Table>
              </TableContainer>

              {selectedDayBookings.length === 0 && (
                <Flex justify="center" align="center" py={8}>
                  <VStack spacing={2}>
                    <Icon as={FiCalendar} boxSize={12} color="gray.400" />
                    <Text color="gray.600">Нет бронирований на эту дату</Text>
                  </VStack>
                </Flex>
              )}
            </ModalBody>
            <ModalFooter>
              <Button onClick={handleModalClose}>Закрыть</Button>
            </ModalFooter>
          </ModalContent>
        </Modal>
      </VStack>
    </Box>
  );
};

export default Dashboard;