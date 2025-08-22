import React, { useEffect, useState, useCallback } from 'react';
import {
  Box, VStack, SimpleGrid, Card, CardBody, CardHeader, Flex, Heading,
  Text, HStack, Icon, Stat, StatLabel, StatNumber, StatHelpText,
  Select, Spinner, Alert, AlertIcon, Badge
} from '@chakra-ui/react';
import { FiUsers, FiShoppingBag, FiMessageCircle, FiTrendingUp, FiCalendar } from 'react-icons/fi';
import Chart from 'chart.js/auto';
import { colors, sizes, styles } from '../styles/styles';
import { createLogger } from '../utils/logger.js';

const logger = createLogger('Dashboard');

const Dashboard = ({
  stats,
  chartRef,
  chartInstanceRef,
  section
}) => {
  const [chartData, setChartData] = useState(null);
  const [availablePeriods, setAvailablePeriods] = useState([]);
  const [selectedPeriod, setSelectedPeriod] = useState({ year: new Date().getFullYear(), month: new Date().getMonth() + 1 });
  const [isLoadingChart, setIsLoadingChart] = useState(false);
  const [chartError, setChartError] = useState(null);

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

  return (
    <Box p={sizes.content.padding} bg="gray.50" minH={sizes.content.minHeight}>
      <VStack spacing={8} align="stretch">
        {/* Статистические карточки */}
        <SimpleGrid columns={{ base: 1, md: 3 }} spacing={6}>
          <Card
            bgGradient={colors.stats.users.gradient}
            color="white"
            boxShadow={styles.card.boxShadow}
            borderRadius={styles.card.borderRadius}
            transition={styles.card.transition}
            _hover={{
              transform: styles.card.hoverTransform,
              boxShadow: styles.card.hoverShadow
            }}
          >
            <CardBody p={6}>
              <Stat>
                <StatLabel fontSize="sm" fontWeight="medium" opacity={0.9}>
                  Всего пользователей
                </StatLabel>
                <StatNumber fontSize="3xl" fontWeight="bold" my={2}>
                  {stats.total_users}
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
            boxShadow={styles.card.boxShadow}
            borderRadius={styles.card.borderRadius}
            transition={styles.card.transition}
            _hover={{
              transform: styles.card.hoverTransform,
              boxShadow: styles.card.hoverShadow
            }}
          >
            <CardBody p={6}>
              <Stat>
                <StatLabel fontSize="sm" fontWeight="medium" opacity={0.9}>
                  Всего бронирований
                </StatLabel>
                <StatNumber fontSize="3xl" fontWeight="bold" my={2}>
                  {stats.total_bookings}
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
            boxShadow={styles.card.boxShadow}
            borderRadius={styles.card.borderRadius}
            transition={styles.card.transition}
            _hover={{
              transform: styles.card.hoverTransform,
              boxShadow: styles.card.hoverShadow
            }}
          >
            <CardBody p={6}>
              <Stat>
                <StatLabel fontSize="sm" fontWeight="medium" opacity={0.9}>
                  Открытые заявки
                </StatLabel>
                <StatNumber fontSize="3xl" fontWeight="bold" my={2}>
                  {stats.open_tickets}
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

        {/* График */}
        <Card
          boxShadow={styles.card.boxShadow}
          borderRadius={styles.card.borderRadius}
          overflow="hidden"
        >
          <CardHeader
            bg="white"
            borderBottom="2px"
            borderColor="gray.100"
            p={6}
          >
            <Flex align="center" justify="space-between" wrap="wrap" gap={4}>
              <Flex align="center">
                <Icon as={FiTrendingUp} boxSize={6} color="purple.500" mr={3} />
                <Heading size="md" color="gray.800">
                  Активность за месяц
                </Heading>
                {chartData && (
                  <Badge ml={3} colorScheme="purple" variant="subtle">
                    {chartData.period.month_name} {chartData.period.year}
                  </Badge>
                )}
              </Flex>

              <Flex align="center" gap={4}>
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
            </Flex>
          </CardHeader>

          <CardBody p={6} bg="white">
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
        </Card>
      </VStack>
    </Box>
  );
};

export default Dashboard;