import React, { useState, useEffect, useRef } from 'react';
import {
  Box,
  VStack,
  HStack,
  Grid,
  GridItem,
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
  StatArrow,
  Alert,
  AlertIcon,
  AlertTitle,
  AlertDescription,
  Spinner,
  useToast,
  Tooltip,
  Icon,
  Flex,
  Spacer,
  Button,
  useDisclosure
} from '@chakra-ui/react';
import {
  FiActivity,
  FiDatabase,
  FiHardDrive,
  FiCpu,
  FiServer,
  FiAlertTriangle,
  FiCheckCircle,
  FiXCircle,
  FiRefreshCw,
  FiZap,
  FiClock
} from 'react-icons/fi';
import { colors, sizes } from '../styles/styles';
import { createLogger } from '../utils/logger';
import api from '../utils/api';

const logger = createLogger('SystemMonitor');

// Утилиты для форматирования
const formatBytes = (bytes) => {
  if (bytes === 0) return '0 Bytes';
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
};

const formatPercentage = (value) => Math.round(value * 10) / 10;

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

// Функция для форматирования деталей различных компонентов
const formatDetails = (component, details, status) => {
  if (!details) return null;
  
  try {
    const data = typeof details === 'string' ? JSON.parse(details) : details;
    
    switch (component) {
      case 'database':
        if (data.pool_stats) {
          return [
            `Соединений: ${data.pool_stats.checked_out}/${data.pool_stats.total_connections}`,
            `Доступно: ${data.pool_stats.available_connections}`,
            `Pool Size: ${data.pool_stats.pool_size}`,
            data.connection_ok ? '✓ Подключение работает' : '✗ Ошибка подключения'
          ];
        }
        if (data.connection_ok !== undefined) {
          return [
            data.connection_ok ? '✓ Подключение работает' : '✗ Ошибка подключения',
            data.pool_message || 'Статус пула недоступен'
          ];
        }
        break;
        
      case 'system_resources':
        const resources = [];
        if (data.memory) {
          resources.push(`RAM: ${data.memory.percent}% (${data.memory.status})`);
        }
        if (data.disk) {
          resources.push(`Диск: ${data.disk.percent}% (${data.disk.status})`);
        }
        if (data.cpu) {
          resources.push(`CPU: ${data.cpu.percent}% (${data.cpu.status})`);
        }
        return resources;
        
      case 'rate_limiter':
        if (data.details) {
          return [
            `Правил: ${Object.keys(data.details.rules || {}).length}`,
            `Активных клиентов: ${Object.keys(data.details.clients || {}).length}`
          ];
        }
        break;
        
      case 'metrics':
        if (data.summary && data.summary.counters) {
          return [
            `Запросов: ${data.summary.counters.requests_total || 0}`,
            `Ошибок: ${data.summary.counters.errors_total || 0}`,
            `Error Rate: ${data.error_rate || 0}%`
          ];
        }
        break;
        
      default:
        if (typeof data === 'object') {
          return Object.entries(data)
            .slice(0, 3)
            .map(([key, value]) => `${key}: ${value}`)
            .filter(item => !item.includes('undefined'));
        }
    }
    
    return [typeof details === 'string' ? details : 'Подробности недоступны'];
  } catch (error) {
    return [typeof details === 'string' ? details : 'Подробности недоступны'];
  }
};

// Компонент для отображения статуса здоровья
const HealthStatusCard = ({ title, icon: IconComponent, status, details, lastUpdate, component }) => {
  const color = getHealthColor(status);
  const HealthIcon = getHealthIcon(status);
  const formattedDetails = formatDetails(component, details, status);
  
  return (
    <Card bg={colors.card.bg} borderColor={`${color}.200`} borderWidth="2px" h="180px">
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
          {formattedDetails && formattedDetails.length > 0 && (
            <VStack align="stretch" spacing={1}>
              {formattedDetails.slice(0, 3).map((detail, index) => (
                <Text key={index} fontSize="xs" color={colors.text.muted}>
                  {detail}
                </Text>
              ))}
            </VStack>
          )}
          {lastUpdate && (
            <Text fontSize="xs" color={colors.text.light} mt="auto">
              {new Date(lastUpdate).toLocaleTimeString()}
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
    <Card bg={colors.card.bg} h="140px">
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
              {formatPercentage(percentage)}% used
            </StatHelpText>
          </Box>
        </Stat>
      </CardBody>
    </Card>
  );
};

// Компонент для отображения алертов
const SystemAlert = ({ alert }) => {
  const getSeverityColor = (severity) => {
    switch (severity?.toLowerCase()) {
      case 'critical': return 'error';
      case 'warning': return 'warning';
      case 'info': return 'info';
      default: return 'info';
    }
  };

  return (
    <Alert status={getSeverityColor(alert.severity)} borderRadius="md" mb={2}>
      <AlertIcon />
      <Box>
        <AlertTitle fontSize="sm">{alert.title}</AlertTitle>
        <AlertDescription fontSize="xs">{alert.message}</AlertDescription>
      </Box>
    </Alert>
  );
};

const SystemMonitor = () => {
  const [healthData, setHealthData] = useState(null);
  const [systemMetrics, setSystemMetrics] = useState(null);
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [lastUpdate, setLastUpdate] = useState(null);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const intervalRef = useRef(null);
  const toast = useToast();

  // Функция загрузки данных о здоровье системы
  const loadHealthData = async () => {
    try {
      const response = await api.get('/monitoring/health/detailed');
      setHealthData(response.data);
      setLastUpdate(new Date().toISOString());
      logger.debug('Health data loaded', { data: response.data });
    } catch (error) {
      logger.error('Failed to load health data', error);
      toast({
        title: 'Ошибка загрузки данных',
        description: 'Не удалось получить данные о состоянии системы',
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    }
  };

  // Функция загрузки системных метрик
  const loadSystemMetrics = async () => {
    try {
      const response = await api.get('/health/system');
      setSystemMetrics(response.data);
      logger.debug('System metrics loaded', { data: response.data });
    } catch (error) {
      logger.error('Failed to load system metrics', error);
    }
  };

  // Функция загрузки алертов
  const loadAlerts = async () => {
    try {
      const response = await api.get('/monitoring/alerts');
      setAlerts(response.data.alerts || []);
      logger.debug('Alerts loaded', { count: response.data.alerts?.length || 0 });
    } catch (error) {
      logger.error('Failed to load alerts', error);
    }
  };

  // Общая функция обновления всех данных
  const refreshAllData = async () => {
    setLoading(true);
    try {
      await Promise.all([
        loadHealthData(),
        loadSystemMetrics(),
        loadAlerts()
      ]);
    } catch (error) {
      logger.error('Failed to refresh data', error);
    } finally {
      setLoading(false);
    }
  };

  // Эффект для первоначальной загрузки и автообновления
  useEffect(() => {
    refreshAllData();

    if (autoRefresh) {
      intervalRef.current = setInterval(refreshAllData, 30000); // Обновление каждые 30 секунд
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
      refreshAllData();
    }
  };

  if (loading) {
    return (
      <Box p={6}>
        <VStack spacing={6}>
          <Spinner size="xl" color="purple.500" />
          <Text color={colors.text.muted}>Загрузка данных мониторинга...</Text>
        </VStack>
      </Box>
    );
  }

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
              onClick={refreshAllData}
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

        {/* Общий статус */}
        {healthData && (
          <Card bg={colors.card.bg}>
            <CardBody>
              <HStack spacing={4}>
                <Icon
                  as={getHealthIcon(healthData.status)}
                  boxSize={6}
                  color={`${getHealthColor(healthData.status)}.500`}
                />
                <VStack align="start" spacing={1}>
                  <Heading size="md" color={colors.text.primary}>
                    Общий статус системы
                  </Heading>
                  <Badge colorScheme={getHealthColor(healthData.status)} fontSize="sm">
                    {healthData.status?.toUpperCase()}
                  </Badge>
                </VStack>
                <Spacer />
                <Text fontSize="sm" color={colors.text.muted}>
                  Время ответа: {healthData.response_time_ms}ms
                </Text>
              </HStack>
            </CardBody>
          </Card>
        )}

        {/* Критические алерты */}
        {alerts.length > 0 && (
          <Box>
            <Heading size="md" color={colors.text.primary} mb={4}>
              Системные уведомления ({alerts.length})
            </Heading>
            <VStack align="stretch" spacing={2} maxH="200px" overflowY="auto">
              {alerts.map((alert, index) => (
                <SystemAlert key={alert.id || index} alert={alert} />
              ))}
            </VStack>
          </Box>
        )}

        {/* Health статусы компонентов */}
        {healthData?.checks && (
          <Box>
            <Heading size="md" color={colors.text.primary} mb={4}>
              Состояние компонентов
            </Heading>
            <Grid templateColumns="repeat(auto-fill, minmax(300px, 1fr))" gap={4}>
              {Object.entries(healthData.checks).map(([component, check]) => (
                <HealthStatusCard
                  key={component}
                  component={component}
                  title={component === 'database' ? 'База данных' : 
                         component === 'system_resources' ? 'Системные ресурсы' :
                         component === 'rate_limiter' ? 'Rate Limiter' :
                         component === 'metrics' ? 'Метрики' : component}
                  icon={component === 'database' ? FiDatabase :
                        component === 'system_resources' ? FiServer :
                        component === 'rate_limiter' ? FiZap :
                        FiActivity}
                  status={check.status}
                  details={check.error || check.details}
                  lastUpdate={lastUpdate}
                />
              ))}
            </Grid>
          </Box>
        )}

        {/* Системные метрики */}
        {systemMetrics && (
          <Box>
            <Heading size="md" color={colors.text.primary} mb={4}>
              Системные ресурсы
            </Heading>
            <Grid templateColumns="repeat(auto-fill, minmax(250px, 1fr))" gap={4}>
              {systemMetrics.memory && (
                <SystemMetricsCard
                  title="Память"
                  icon={FiServer}
                  value={formatBytes(systemMetrics.memory.total_mb * 1024 * 1024 - systemMetrics.memory.available_mb * 1024 * 1024)}
                  unit={`/ ${formatBytes(systemMetrics.memory.total_mb * 1024 * 1024)}`}
                  percentage={systemMetrics.memory.usage_percent}
                  threshold={85}
                />
              )}
              
              {systemMetrics.disk && (
                <SystemMetricsCard
                  title="Дисковое пространство"
                  icon={FiHardDrive}
                  value={formatBytes(systemMetrics.disk.used_gb * 1024 * 1024 * 1024)}
                  unit={`/ ${formatBytes(systemMetrics.disk.total_gb * 1024 * 1024 * 1024)}`}
                  percentage={systemMetrics.disk.usage_percent}
                  threshold={85}
                />
              )}
              
              {systemMetrics.cpu && (
                <SystemMetricsCard
                  title="Процессор"
                  icon={FiCpu}
                  value={formatPercentage(systemMetrics.cpu.usage_percent)}
                  unit="%"
                  percentage={systemMetrics.cpu.usage_percent}
                  threshold={80}
                />
              )}
            </Grid>
          </Box>
        )}

        {/* Футер с информацией об обновлении */}
        {lastUpdate && (
          <Text fontSize="sm" color={colors.text.muted} textAlign="center">
            Последнее обновление: {new Date(lastUpdate).toLocaleString()}
            {autoRefresh && ' • Автообновление включено'}
          </Text>
        )}
      </VStack>
    </Box>
  );
};

export default SystemMonitor;