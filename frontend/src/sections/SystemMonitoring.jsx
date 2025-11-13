import React, { useState, useEffect, useRef } from 'react';
import {
  Box,
  VStack,
  HStack,
  Grid,
  Card,
  CardHeader,
  CardBody,
  Heading,
  Text,
  Badge,
  Progress,
  Stat,
  StatLabel,
  StatNumber,
  StatHelpText,
  Alert,
  AlertIcon,
  AlertTitle,
  AlertDescription,
  Spinner,
  useToast,
  Icon,
  Flex,
  Spacer,
  Button,
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  TableContainer,
  Code,
  Tooltip,
  CircularProgress,
  CircularProgressLabel,
  Divider
} from '@chakra-ui/react';
import {
  FiActivity,
  FiDatabase,
  FiHardDrive,
  FiCpu,
  FiServer,
  FiCheckCircle,
  FiXCircle,
  FiAlertTriangle,
  FiRefreshCw,
  FiZap,
  FiClock,
  FiBarChart
} from 'react-icons/fi';
import { colors } from '../styles/styles';
import { createLogger } from '../utils/logger';
import api from '../utils/api';

const logger = createLogger('SystemMonitoring');

// Утилиты для форматирования
const formatBytes = (bytes) => {
  if (bytes === 0) return '0 Bytes';
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
};

const formatPercentage = (value) => {
  if (value == null || isNaN(value)) return 0;
  return Math.round(value * 10) / 10;
};

const formatDuration = (ms) => {
  if (ms < 1000) return `${ms}мс`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}с`;
  return `${(ms / 60000).toFixed(1)}мин`;
};

const formatNumber = (num) => {
  return new Intl.NumberFormat('ru-RU').format(num);
};

const getHealthColor = (status) => {
  switch (status?.toLowerCase()) {
    case 'healthy': return 'green';
    case 'warning': case 'degraded': return 'yellow';
    case 'critical': case 'unhealthy': return 'red';
    default: return 'gray';
  }
};

const getHealthIcon = (status) => {
  switch (status?.toLowerCase()) {
    case 'healthy': return FiCheckCircle;
    case 'warning': case 'degraded': return FiAlertTriangle;
    case 'critical': case 'unhealthy': return FiXCircle;
    default: return FiClock;
  }
};

// Компонент для отображения статуса здоровья компонента
const HealthStatusCard = ({ title, icon: IconComponent, status, details }) => {
  const color = getHealthColor(status);
  const HealthIcon = getHealthIcon(status);

  return (
    <Card bg={colors.background.card} borderColor={`${color}.200`} borderWidth="2px">
      <CardHeader pb={2}>
        <HStack spacing={3}>
          <Icon as={IconComponent} boxSize={5} color={`${color}.500`} />
          <Heading size="sm" color={colors.text.primary}>
            {title}
          </Heading>
          <Spacer />
          <Icon as={HealthIcon} boxSize={4} color={`${color}.500`} />
        </HStack>
      </CardHeader>
      <CardBody pt={0}>
        <VStack align="stretch" spacing={2}>
          <Badge colorScheme={color} fontSize="xs" textTransform="uppercase">
            {status || 'Unknown'}
          </Badge>
          {details && (
            <Text fontSize="xs" color={colors.text.muted}>
              {details}
            </Text>
          )}
        </VStack>
      </CardBody>
    </Card>
  );
};

// Компонент для отображения метрик системы
const SystemMetricsCard = ({ title, icon: IconComponent, value, unit, percentage, threshold = 80 }) => {
  const getColorScheme = () => {
    if (percentage >= 95) return 'red';
    if (percentage >= threshold) return 'yellow';
    return 'green';
  };

  return (
    <Card bg={colors.background.card}>
      <CardBody>
        <Stat>
          <HStack mb={2}>
            <Icon as={IconComponent} boxSize={5} color="blue.400" />
            <StatLabel fontSize="sm" color={colors.text.primary}>
              {title}
            </StatLabel>
          </HStack>
          <StatNumber fontSize="2xl" color={colors.text.primary}>
            {value} {unit}
          </StatNumber>
          <Box mt={3}>
            <Progress
              value={percentage}
              colorScheme={getColorScheme()}
              size="sm"
              borderRadius="md"
            />
            <StatHelpText mt={1} mb={0}>
              {formatPercentage(percentage)}% использовано
            </StatHelpText>
          </Box>
        </Stat>
      </CardBody>
    </Card>
  );
};

// Компонент для отображения hit/miss ratio
const HitMissChart = ({ hitRate, missRate }) => {
  const hitPercentage = hitRate / (hitRate + missRate) * 100 || 0;

  const getColor = () => {
    if (hitPercentage >= 90) return 'green';
    if (hitPercentage >= 70) return 'yellow';
    return 'red';
  };

  return (
    <Card bg={colors.background.card}>
      <CardHeader>
        <HStack spacing={3}>
          <Icon as={FiBarChart} boxSize={5} color="purple.500" />
          <Heading size="sm" color={colors.text.primary}>
            Cache Hit/Miss Ratio
          </Heading>
        </HStack>
      </CardHeader>
      <CardBody>
        <VStack spacing={4}>
          <CircularProgress
            value={hitPercentage}
            color={`${getColor()}.400`}
            size="100px"
            thickness="8px"
          >
            <CircularProgressLabel fontSize="lg" fontWeight="bold">
              {hitPercentage.toFixed(1)}%
            </CircularProgressLabel>
          </CircularProgress>

          <VStack spacing={2} w="full">
            <HStack justify="space-between" w="full">
              <HStack>
                <Box w={3} h={3} borderRadius="full" bg="green.400" />
                <Text fontSize="sm" color={colors.text.muted}>Hits</Text>
              </HStack>
              <Text fontSize="sm" fontWeight="medium" color={colors.text.primary}>
                {formatNumber(hitRate)}
              </Text>
            </HStack>

            <HStack justify="space-between" w="full">
              <HStack>
                <Box w={3} h={3} borderRadius="full" bg="red.400" />
                <Text fontSize="sm" color={colors.text.muted}>Misses</Text>
              </HStack>
              <Text fontSize="sm" fontWeight="medium" color={colors.text.primary}>
                {formatNumber(missRate)}
              </Text>
            </HStack>
          </VStack>
        </VStack>
      </CardBody>
    </Card>
  );
};

const SystemMonitoring = () => {
  const [healthData, setHealthData] = useState(null);
  const [systemMetrics, setSystemMetrics] = useState(null);
  const [cacheStats, setCacheStats] = useState(null);
  const [cacheHealth, setCacheHealth] = useState(null);
  const [slowQueries, setSlowQueries] = useState([]);
  const [dbPerformanceScore, setDbPerformanceScore] = useState(null);
  const [loading, setLoading] = useState(true);
  const [lastUpdate, setLastUpdate] = useState(null);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const intervalRef = useRef(null);
  const toast = useToast();

  // Функция загрузки всех данных
  const loadAllData = async () => {
    try {
      const [healthResponse, cacheStatsResponse, cacheHealthResponse, slowQueriesResponse, dbStatsResponse] = await Promise.all([
        api.get('/monitoring/health/detailed'),
        api.get('/cache/stats').catch(() => null),
        api.get('/cache/health').catch(() => null),
        api.get('/optimization/slow-queries').catch(() => null),
        api.get('/optimization/database-stats').catch(() => null)
      ]);

      // Health data
      setHealthData(healthResponse.data);
      if (healthResponse.data?.checks?.system_resources) {
        setSystemMetrics(healthResponse.data.checks.system_resources);
      }

      // Cache data
      if (cacheStatsResponse) {
        setCacheStats(cacheStatsResponse.data.cache_stats || cacheStatsResponse.data);
      }
      if (cacheHealthResponse) {
        setCacheHealth(cacheHealthResponse.data);
      }

      // Performance data
      if (slowQueriesResponse) {
        setSlowQueries(slowQueriesResponse.data.slow_queries || []);
      }
      if (dbStatsResponse) {
        const dbStats = dbStatsResponse.data;
        const systemRes = healthResponse.data?.checks?.system_resources || {};

        // Calculate performance score
        let score = 100;
        if (dbStats.total_tables > 0) {
          const indexRatio = dbStats.total_indexes / dbStats.total_tables;
          if (indexRatio < 1) score -= 20;
          else if (indexRatio < 2) score -= 10;
        }
        if (systemRes.cpu?.percent > 80) score -= 15;
        if (systemRes.memory?.percent > 85) score -= 15;
        if (systemRes.disk?.percent > 90) score -= 20;

        setDbPerformanceScore(Math.max(score, 0));
      }

      setLastUpdate(new Date().toISOString());
      logger.debug('All monitoring data loaded successfully');
    } catch (error) {
      logger.error('Failed to load monitoring data', error);
      toast({
        title: 'Ошибка загрузки',
        description: 'Не удалось загрузить данные мониторинга',
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    } finally {
      setLoading(false);
    }
  };

  // Первоначальная загрузка и автообновление
  useEffect(() => {
    loadAllData();

    if (autoRefresh) {
      intervalRef.current = setInterval(loadAllData, 30000); // Обновление каждые 30 секунд
    }

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, [autoRefresh]);

  // Обработка включения/выключения автообновления
  const toggleAutoRefresh = () => {
    setAutoRefresh(!autoRefresh);
    if (!autoRefresh) {
      loadAllData();
    }
  };

  if (loading) {
    return (
      <Box p={6} textAlign="center">
        <VStack spacing={6}>
          <Spinner size="xl" color="purple.500" />
          <Text color={colors.text.muted}>Загрузка данных мониторинга...</Text>
        </VStack>
      </Box>
    );
  }

  const getPerformanceColor = (score) => {
    if (score >= 80) return 'green';
    if (score >= 60) return 'yellow';
    return 'red';
  };

  return (
    <Box p={6} minH="100vh" bg={colors.background}>
      <VStack align="stretch" spacing={6}>
        {/* Заголовок с управлением */}
        <Flex align="center" justify="space-between">
          <HStack spacing={4}>
            <Icon as={FiActivity} boxSize={8} color="purple.400" />
            <Heading size="lg" color={colors.text.primary}>
              Мониторинг системы
            </Heading>
          </HStack>
          <HStack spacing={3}>
            <Button
              size="sm"
              leftIcon={<FiRefreshCw />}
              onClick={loadAllData}
              isLoading={loading}
              variant="outline"
            >
              Обновить
            </Button>
            <Button
              size="sm"
              leftIcon={<FiZap />}
              onClick={toggleAutoRefresh}
              colorScheme={autoRefresh ? 'green' : 'gray'}
              variant={autoRefresh ? 'solid' : 'outline'}
            >
              {autoRefresh ? 'Авто' : 'Ручное'}
            </Button>
          </HStack>
        </Flex>

        {/* === РАЗДЕЛ 1: Здоровье системы === */}
        <Box>
          <Heading size="md" color={colors.text.primary} mb={4}>
            Общий статус системы
          </Heading>

          {/* Общий статус */}
          {healthData && (
            <Card bg={colors.background.card} mb={4}>
              <CardBody>
                <HStack spacing={4}>
                  <Icon
                    as={getHealthIcon(healthData.status)}
                    boxSize={6}
                    color={`${getHealthColor(healthData.status)}.500`}
                  />
                  <VStack align="start" spacing={1}>
                    <Heading size="md" color={colors.text.primary}>
                      Статус: {healthData.status?.toUpperCase()}
                    </Heading>
                    <Badge colorScheme={getHealthColor(healthData.status)} fontSize="sm">
                      Время ответа: {healthData.response_time_ms}мс
                    </Badge>
                  </VStack>
                </HStack>
              </CardBody>
            </Card>
          )}

          {/* Состояние компонентов */}
          {healthData?.checks && (
            <Grid templateColumns="repeat(auto-fill, minmax(250px, 1fr))" gap={4} mb={4}>
              {Object.entries(healthData.checks).map(([component, check]) => (
                <HealthStatusCard
                  key={component}
                  title={component === 'database' ? 'База данных' :
                         component === 'system_resources' ? 'Системные ресурсы' :
                         component === 'rate_limiter' ? 'Rate Limiter' :
                         component === 'metrics' ? 'Метрики' : component}
                  icon={component === 'database' ? FiDatabase :
                        component === 'system_resources' ? FiServer :
                        component === 'rate_limiter' ? FiZap :
                        FiActivity}
                  status={check.status}
                  details={check.error || (typeof check.details === 'string' ? check.details : null)}
                />
              ))}
            </Grid>
          )}

          {/* Системные ресурсы */}
          {systemMetrics && (
            <Grid templateColumns="repeat(auto-fill, minmax(250px, 1fr))" gap={4}>
              {systemMetrics.memory && (
                <SystemMetricsCard
                  title="Память"
                  icon={FiServer}
                  value={formatBytes((systemMetrics.memory.total_mb - systemMetrics.memory.available_mb) * 1024 * 1024)}
                  unit={`/ ${formatBytes(systemMetrics.memory.total_mb * 1024 * 1024)}`}
                  percentage={((systemMetrics.memory.total_mb - systemMetrics.memory.available_mb) / systemMetrics.memory.total_mb) * 100}
                  threshold={85}
                />
              )}

              {systemMetrics.disk && (
                <SystemMetricsCard
                  title="Дисковое пространство"
                  icon={FiHardDrive}
                  value={formatBytes(systemMetrics.disk.used_gb * 1024 * 1024 * 1024)}
                  unit={`/ ${formatBytes(systemMetrics.disk.total_gb * 1024 * 1024 * 1024)}`}
                  percentage={(systemMetrics.disk.used_gb / systemMetrics.disk.total_gb) * 100}
                  threshold={85}
                />
              )}

              {systemMetrics.cpu && (
                <SystemMetricsCard
                  title="Процессор"
                  icon={FiCpu}
                  value={formatPercentage(systemMetrics.cpu.usage_percent || 0)}
                  unit="%"
                  percentage={systemMetrics.cpu.usage_percent || 0}
                  threshold={80}
                />
              )}
            </Grid>
          )}
        </Box>

        <Divider />

        {/* === РАЗДЕЛ 2: Redis & Кэш === */}
        <Box>
          <Heading size="md" color={colors.text.primary} mb={4}>
            Redis и кэширование
          </Heading>

          <Grid templateColumns="repeat(auto-fill, minmax(300px, 1fr))" gap={4}>
            {/* Статус Redis */}
            {cacheHealth && (
              <Card bg={colors.background.card}>
                <CardHeader>
                  <HStack spacing={3}>
                    <Icon as={FiDatabase} boxSize={5} color="blue.400" />
                    <Heading size="sm" color={colors.text.primary}>
                      Статус Redis
                    </Heading>
                  </HStack>
                </CardHeader>
                <CardBody>
                  <VStack align="stretch" spacing={3}>
                    <HStack justify="space-between">
                      <Text fontSize="sm" color={colors.text.muted}>
                        Подключение
                      </Text>
                      <Badge colorScheme={cacheHealth.redis_connected ? 'green' : 'red'}>
                        {cacheHealth.redis_connected ? 'Подключен' : 'Отключен'}
                      </Badge>
                    </HStack>
                    <HStack justify="space-between">
                      <Text fontSize="sm" color={colors.text.muted}>
                        Кэш работает
                      </Text>
                      <Badge colorScheme={cacheHealth.cache_working ? 'green' : 'red'}>
                        {cacheHealth.cache_working ? 'Да' : 'Нет'}
                      </Badge>
                    </HStack>
                    {cacheHealth.backend && (
                      <HStack justify="space-between">
                        <Text fontSize="sm" color={colors.text.muted}>
                          Backend
                        </Text>
                        <Text fontSize="sm" fontWeight="medium" color={colors.text.primary}>
                          {cacheHealth.backend}
                        </Text>
                      </HStack>
                    )}
                  </VStack>
                </CardBody>
              </Card>
            )}

            {/* Базовая статистика кэша */}
            {cacheStats && (
              <Card bg={colors.background.card}>
                <CardHeader>
                  <HStack spacing={3}>
                    <Icon as={FiActivity} boxSize={5} color="green.400" />
                    <Heading size="sm" color={colors.text.primary}>
                      Статистика кэша
                    </Heading>
                  </HStack>
                </CardHeader>
                <CardBody>
                  <VStack align="stretch" spacing={3}>
                    <HStack justify="space-between">
                      <Text fontSize="sm" color={colors.text.muted}>
                        Размер
                      </Text>
                      <Text fontSize="sm" fontWeight="medium" color={colors.text.primary}>
                        {formatBytes(cacheStats.total_size || 0)}
                      </Text>
                    </HStack>
                    <HStack justify="space-between">
                      <Text fontSize="sm" color={colors.text.muted}>
                        Ключей
                      </Text>
                      <Text fontSize="sm" fontWeight="medium" color={colors.text.primary}>
                        {formatNumber(cacheStats.total_keys || 0)}
                      </Text>
                    </HStack>
                    <HStack justify="space-between">
                      <Text fontSize="sm" color={colors.text.muted}>
                        Hit Rate
                      </Text>
                      <Text fontSize="sm" fontWeight="medium" color={colors.text.primary}>
                        {((cacheStats.hits || 0) / ((cacheStats.hits || 0) + (cacheStats.misses || 0)) * 100 || 0).toFixed(1)}%
                      </Text>
                    </HStack>
                  </VStack>
                </CardBody>
              </Card>
            )}

            {/* Hit/Miss визуализация */}
            {cacheStats && (
              <HitMissChart
                hitRate={cacheStats.hits || 0}
                missRate={cacheStats.misses || 0}
              />
            )}
          </Grid>
        </Box>

        <Divider />

        {/* === РАЗДЕЛ 3: Производительность БД === */}
        <Box>
          <Heading size="md" color={colors.text.primary} mb={4}>
            Производительность базы данных
          </Heading>

          {/* Общий балл производительности */}
          {dbPerformanceScore !== null && (
            <Card bg={colors.background.card} mb={4}>
              <CardBody>
                <Stat>
                  <StatLabel>Общий балл производительности</StatLabel>
                  <StatNumber color={getPerformanceColor(dbPerformanceScore)}>
                    {dbPerformanceScore}/100
                  </StatNumber>
                  <Progress
                    value={dbPerformanceScore}
                    colorScheme={getPerformanceColor(dbPerformanceScore)}
                    size="sm"
                    mt={2}
                  />
                </Stat>
              </CardBody>
            </Card>
          )}

          {/* Медленные запросы */}
          <Card bg={colors.background.card}>
            <CardHeader>
              <Flex justify="space-between" align="center">
                <HStack spacing={3}>
                  <Icon as={FiClock} boxSize={5} color="orange.400" />
                  <Heading size="sm" color={colors.text.primary}>
                    Медленные запросы (Top 10)
                  </Heading>
                </HStack>
                <Badge colorScheme={slowQueries.length > 0 ? 'red' : 'green'} variant="subtle">
                  {slowQueries.length} активных
                </Badge>
              </Flex>
            </CardHeader>
            <CardBody>
              {slowQueries.length === 0 ? (
                <Alert status="success">
                  <AlertIcon />
                  <Box>
                    <AlertTitle>Отлично!</AlertTitle>
                    <AlertDescription>
                      Медленных запросов не обнаружено
                    </AlertDescription>
                  </Box>
                </Alert>
              ) : (
                <TableContainer>
                  <Table variant="simple" size="sm">
                    <Thead>
                      <Tr>
                        <Th>Запрос</Th>
                        <Th>Время</Th>
                        <Th>Частота</Th>
                        <Th>Таблица</Th>
                      </Tr>
                    </Thead>
                    <Tbody>
                      {slowQueries.slice(0, 10).map((query, index) => (
                        <Tr key={index}>
                          <Td>
                            <Tooltip label={query.query_text}>
                              <Code fontSize="xs">
                                {query.query_text?.substring(0, 50)}...
                              </Code>
                            </Tooltip>
                          </Td>
                          <Td>
                            <Badge colorScheme="red">
                              {formatDuration(query.avg_duration)}
                            </Badge>
                          </Td>
                          <Td>{query.execution_count || 1} раз</Td>
                          <Td>{query.table_name || 'N/A'}</Td>
                        </Tr>
                      ))}
                    </Tbody>
                  </Table>
                </TableContainer>
              )}
            </CardBody>
          </Card>
        </Box>

        {/* Футер с информацией об обновлении */}
        {lastUpdate && (
          <Text fontSize="sm" color={colors.text.muted} textAlign="center">
            Последнее обновление: {new Date(lastUpdate).toLocaleString()}
            {autoRefresh && ' • Автообновление включено (каждые 30 секунд)'}
          </Text>
        )}
      </VStack>
    </Box>
  );
};

export default SystemMonitoring;
