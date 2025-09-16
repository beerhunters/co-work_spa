import React, { useEffect, useState, useCallback } from 'react';
import {
  Box, VStack, SimpleGrid, Card, CardBody, CardHeader, Flex, Heading,
  Text, HStack, Icon, Stat, StatLabel, StatNumber, StatHelpText,
  Select, Spinner, Alert, AlertIcon, Badge, Collapse, Button, Grid, GridItem, Tooltip
} from '@chakra-ui/react';
import { FiUsers, FiShoppingBag, FiMessageCircle, FiTrendingUp, FiCalendar, FiChevronDown, FiChevronRight, FiChevronLeft } from 'react-icons/fi';
import Chart from 'chart.js/auto';
import { colors, sizes, styles, typography, spacing } from '../styles/styles';
import { createLogger } from '../utils/logger.js';

const logger = createLogger('Dashboard');

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

  // Загрузка периодов при монтировании компонента
  useEffect(() => {
    if (section === 'dashboard') {
      loadAvailablePeriods();
    }
  }, [section, loadAvailablePeriods]);

  // Загрузка данных графика при изменении выбранного периода
  useEffect(() => {
    if (section === 'dashboard' && selectedPeriod.year && selectedPeriod.month) {
      loadChartData(selectedPeriod.year, selectedPeriod.month);
    }
  }, [section, selectedPeriod, loadChartData]);

  // Обработчик изменения периода
  const handlePeriodChange = (event) => {
    const selectedValue = event.target.value;
    if (selectedValue) {
      const [year, month] = selectedValue.split('-').map(Number);
      setSelectedPeriod({ year, month });
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

      chartInstanceRef.current = new Chart(ctx, {
        type: 'line',
        data: {
          labels: chartData.labels,
          datasets: [
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
              fill: true
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
              fill: true
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
              fill: true
            }
          ]
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
                  return `${context[0].label} ${chartData.period.month_name}`;
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
                padding: 20,
                font: {
                  size: 13,
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
  }, [chartData, chartRef, chartInstanceRef, section, isLoadingChart]);

  // Очистка графика при размонтировании
  useEffect(() => {
    return () => {
      if (chartInstanceRef.current) {
        chartInstanceRef.current.destroy();
        chartInstanceRef.current = null;
      }
    };
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

      const response = await fetch(`/api/dashboard/bookings-calendar?year=${year}&month=${month}`, {
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
    } catch (error) {
      logger.error('Ошибка загрузки данных календаря:', error);
      setBookingsError(error.message);
    } finally {
      setIsLoadingBookings(false);
    }
  }, []);

  // Загрузка календаря при открытии аккордеона
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

  return (
    <Box p={spacing.lg} bg={colors.background.main} minH={sizes.content.minHeight}>
      <VStack spacing={8} align="stretch">
        {/* Статистические карточки */}
        <SimpleGrid columns={{ base: 1, md: 3 }} spacing={spacing.md}>
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
              <Stat>
                <StatLabel fontSize={typography.fontSizes.sm} fontWeight={typography.fontWeights.medium} opacity={0.9}>
                  Всего пользователей
                </StatLabel>
                <StatNumber fontSize={typography.fontSizes['3xl']} fontWeight={typography.fontWeights.bold} my={spacing.xs}>
                  {stats?.total_users || 0}
                </StatNumber>
                <StatHelpText opacity={0.9}>
                  <HStack spacing={1}>
                    <Icon as={FiUsers} />
                    <Text>Активные пользователи</Text>
                  </HStack>
                </StatHelpText>
              </Stat>
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
              <Stat>
                <StatLabel fontSize={typography.fontSizes.sm} fontWeight={typography.fontWeights.medium} opacity={0.9}>
                  Всего бронирований
                </StatLabel>
                <StatNumber fontSize={typography.fontSizes['3xl']} fontWeight={typography.fontWeights.bold} my={spacing.xs}>
                  {stats?.total_bookings || 0}
                </StatNumber>
                <StatHelpText opacity={0.9}>
                  <HStack spacing={1}>
                    <Icon as={FiShoppingBag} />
                    <Text>Все бронирования</Text>
                  </HStack>
                </StatHelpText>
              </Stat>
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
              <Stat>
                <StatLabel fontSize={typography.fontSizes.sm} fontWeight={typography.fontWeights.medium} opacity={0.9}>
                  Открытые заявки
                </StatLabel>
                <StatNumber fontSize={typography.fontSizes['3xl']} fontWeight={typography.fontWeights.bold} my={spacing.xs}>
                  {stats?.open_tickets || 0}
                </StatNumber>
                <StatHelpText opacity={0.9}>
                  <HStack spacing={1}>
                    <Icon as={FiMessageCircle} />
                    <Text>Требуют внимания</Text>
                  </HStack>
                </StatHelpText>
              </Stat>
            </CardBody>
          </Card>
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
                </Flex>
              </Flex>

              {chartError && (
                <Alert status="error" mb={4}>
                  <AlertIcon />
                  Ошибка загрузки данных: {chartError}
                </Alert>
              )}

              <Box h={styles.chart.height} position="relative">
                {isLoadingChart && (
                  <Flex
                    position="absolute"
                    top="0"
                    left="0"
                    right="0"
                    bottom="0"
                    align="center"
                    justify="center"
                    bg="rgba(255, 255, 255, 0.8)"
                    zIndex={10}
                  >
                    <VStack spacing={2}>
                      <Spinner size="lg" color="purple.500" />
                      <Text fontSize="sm" color="gray.600">
                        Загрузка данных...
                      </Text>
                    </VStack>
                  </Flex>
                )}
                <canvas ref={chartRef}></canvas>
              </Box>
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

              {bookingsError && (
                <Alert status="error" mb={4}>
                  <AlertIcon />
                  Ошибка загрузки календаря: {bookingsError}
                </Alert>
              )}

              {/* Календарная сетка */}
              <Box position="relative">
                {isLoadingBookings && (
                  <Flex
                    position="absolute"
                    top="0"
                    left="0"
                    right="0"
                    bottom="0"
                    align="center"
                    justify="center"
                    bg="rgba(255, 255, 255, 0.8)"
                    zIndex={10}
                    borderRadius="md"
                  >
                    <VStack spacing={2}>
                      <Spinner size="lg" color="green.500" />
                      <Text fontSize="sm" color="gray.600">
                        Загрузка календаря...
                      </Text>
                    </VStack>
                  </Flex>
                )}

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
                          _hover={{ bg: isCurrentMonth ? "gray.50" : "gray.100" }}
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
                              {bookings.slice(0, 5).map((booking) => (
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
                                    onClick={() => handleBookingClick(booking)}
                                    _hover={{ 
                                      bg: booking.confirmed ? "green.200" : "yellow.200"
                                    }}
                                    noOfLines={1}
                                  >
                                    #{booking.id}
                                  </Box>
                                </Tooltip>
                              ))}
                              {bookings.length > 5 && (
                                <Text fontSize="xs" color="gray.600" textAlign="center">
                                  +{bookings.length - 5}
                                </Text>
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
              </Box>
            </CardBody>
          </Collapse>
        </Card>
      </VStack>
    </Box>
  );
};

export default Dashboard;