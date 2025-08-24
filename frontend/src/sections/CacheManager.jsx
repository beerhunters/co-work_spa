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
  Button,
  ButtonGroup,
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
  Input,
  InputGroup,
  InputLeftElement,
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalFooter,
  ModalBody,
  ModalCloseButton,
  useDisclosure,
  Divider,
  List,
  ListItem,
  ListIcon,
  CircularProgress,
  CircularProgressLabel
} from '@chakra-ui/react';
import {
  FiDatabase,
  FiTrash2,
  FiRefreshCw,
  FiSearch,
  FiZap,
  FiCheckCircle,
  FiXCircle,
  FiAlertTriangle,
  FiClock,
  FiBarChart,
  FiActivity,
  FiSettings,
  FiLayers,
  FiHardDrive
} from 'react-icons/fi';
import { colors, sizes, styles, spacing, typography } from '../styles/styles';
import { createLogger } from '../utils/logger';
import api from '../utils/api';

const logger = createLogger('CacheManager');

// Утилиты для форматирования
const formatBytes = (bytes) => {
  if (bytes === 0) return '0 Bytes';
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
};

const formatNumber = (num) => {
  return new Intl.NumberFormat('ru-RU').format(num);
};

const formatDuration = (seconds) => {
  if (seconds < 60) return `${seconds}с`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}м ${seconds % 60}с`;
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  return `${hours}ч ${minutes}м`;
};

// Компонент статистики кэша
const CacheStatsCard = ({ title, icon: IconComponent, stats, color = 'blue' }) => {
  return (
    <Card bg={colors.background.card} borderColor={`${color}.200`} borderWidth="1px">
      <CardHeader pb={2}>
        <HStack spacing={3}>
          <Icon as={IconComponent} boxSize={5} color={`${color}.500`} />
          <Heading size="sm" color={colors.text.primary}>
            {title}
          </Heading>
        </HStack>
      </CardHeader>
      <CardBody pt={0}>
        <VStack align="stretch" spacing={3}>
          {stats.map((stat, index) => (
            <HStack key={index} justify="space-between">
              <Text fontSize="sm" color={colors.text.muted}>
                {stat.label}
              </Text>
              <Text fontSize="sm" fontWeight="medium" color={colors.text.primary}>
                {stat.value}
              </Text>
            </HStack>
          ))}
        </VStack>
      </CardBody>
    </Card>
  );
};

// Компонент для отображения hit/miss ratio
const HitMissChart = ({ hitRate, missRate, title }) => {
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
            {title}
          </Heading>
        </HStack>
      </CardHeader>
      <CardBody>
        <VStack spacing={4}>
          <CircularProgress 
            value={hitPercentage} 
            color={`${getColor()}.400`}
            size="120px"
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
            
            <Divider />
            
            <HStack justify="space-between" w="full">
              <Text fontSize="sm" fontWeight="bold" color={colors.text.primary}>
                Всего запросов
              </Text>
              <Text fontSize="sm" fontWeight="bold" color={colors.text.primary}>
                {formatNumber(hitRate + missRate)}
              </Text>
            </HStack>
          </VStack>
        </VStack>
      </CardBody>
    </Card>
  );
};

// Компонент управления очисткой кэша
const CacheControlPanel = ({ onClearCache, loading }) => {
  const { isOpen, onOpen, onClose } = useDisclosure();
  const [customPattern, setCustomPattern] = useState('');
  const [selectedPreset, setSelectedPreset] = useState('');

  const presetPatterns = [
    { label: 'Все данные пользователей', pattern: 'user:*', description: 'Очистить все кэшированные данные пользователей' },
    { label: 'Dashboard данные', pattern: 'dashboard:*', description: 'Очистить кэш дашборда и статистики' },
    { label: 'Данные бронирований', pattern: 'booking:*', description: 'Очистить кэш бронирований' },
    { label: 'Тарифы', pattern: 'tariffs:*', description: 'Очистить кэш тарифов' },
    { label: 'Сессии пользователей', pattern: 'session:*', description: 'Очистить все активные сессии' },
    { label: 'API responses', pattern: 'api:*', description: 'Очистить кэшированные API ответы' },
  ];

  const handleClear = (pattern) => {
    onClearCache(pattern);
    onClose();
    setCustomPattern('');
    setSelectedPreset('');
  };

  return (
    <>
      <Card bg={colors.background.card}>
        <CardHeader>
          <HStack spacing={3}>
            <Icon as={FiSettings} boxSize={5} color="orange.500" />
            <Heading size="sm" color={colors.text.primary}>
              Управление кэшем
            </Heading>
          </HStack>
        </CardHeader>
        <CardBody>
          <VStack spacing={3}>
            <ButtonGroup size="sm" variant="outline" w="full">
              <Button 
                leftIcon={<FiRefreshCw />}
                onClick={() => handleClear('*')}
                isLoading={loading}
                colorScheme="red"
                flex={1}
              >
                Очистить весь кэш
              </Button>
              <Button 
                leftIcon={<FiSearch />}
                onClick={onOpen}
                flex={1}
              >
                Выборочная очистка
              </Button>
            </ButtonGroup>
            
            <Text fontSize="xs" color={colors.text.muted} textAlign="center">
              Осторожно: очистка кэша может временно снизить производительность
            </Text>
          </VStack>
        </CardBody>
      </Card>

      {/* Модальное окно для выборочной очистки */}
      <Modal isOpen={isOpen} onClose={onClose} size="lg">
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>Выборочная очистка кэша</ModalHeader>
          <ModalCloseButton />
          <ModalBody>
            <VStack spacing={4} align="stretch">
              <Box>
                <Text fontSize="sm" fontWeight="medium" mb={2}>
                  Готовые шаблоны:
                </Text>
                <List spacing={2}>
                  {presetPatterns.map((preset, index) => (
                    <ListItem 
                      key={index}
                      p={3}
                      borderRadius="md"
                      border="1px"
                      borderColor={selectedPreset === preset.pattern ? 'blue.300' : 'gray.200'}
                      cursor="pointer"
                      _hover={{ bg: 'gray.50' }}
                      onClick={() => setSelectedPreset(preset.pattern)}
                    >
                      <HStack justify="space-between">
                        <VStack align="start" spacing={1}>
                          <Text fontSize="sm" fontWeight="medium">
                            {preset.label}
                          </Text>
                          <Text fontSize="xs" color={colors.text.muted}>
                            {preset.description}
                          </Text>
                        </VStack>
                        <Badge variant="outline" fontSize="xs">
                          {preset.pattern}
                        </Badge>
                      </HStack>
                    </ListItem>
                  ))}
                </List>
              </Box>
              
              <Divider />
              
              <Box>
                <Text fontSize="sm" fontWeight="medium" mb={2}>
                  Или укажите собственный паттерн:
                </Text>
                <InputGroup>
                  <InputLeftElement pointerEvents="none">
                    <Icon as={FiSearch} color="gray.300" />
                  </InputLeftElement>
                  <Input
                    placeholder="Например: user:123:* или api:dashboard*"
                    value={customPattern}
                    onChange={(e) => setCustomPattern(e.target.value)}
                  />
                </InputGroup>
                <Text fontSize="xs" color={colors.text.muted} mt={1}>
                  Используйте * для wildcard паттернов
                </Text>
              </Box>
            </VStack>
          </ModalBody>
          <ModalFooter>
            <Button variant="ghost" mr={3} onClick={onClose}>
              Отмена
            </Button>
            <Button 
              colorScheme="red"
              onClick={() => handleClear(selectedPreset || customPattern)}
              isDisabled={!selectedPreset && !customPattern}
              isLoading={loading}
              leftIcon={<FiTrash2 />}
            >
              Очистить
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>
    </>
  );
};

// Основной компонент Cache Manager
const CacheManager = () => {
  const [cacheStats, setCacheStats] = useState(null);
  const [cacheHealth, setCacheHealth] = useState(null);
  const [loading, setLoading] = useState(true);
  const [clearLoading, setClearLoading] = useState(false);
  const [lastUpdate, setLastUpdate] = useState(null);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const intervalRef = useRef(null);
  const toast = useToast();

  // Функция загрузки статистики кэша
  const loadCacheStats = async () => {
    try {
      const response = await api.get('/cache/stats');
      // API возвращает данные в cache_stats
      setCacheStats(response.data.cache_stats || response.data);
      setLastUpdate(new Date().toISOString());
      logger.debug('Cache stats loaded', { data: response.data });
    } catch (error) {
      logger.error('Failed to load cache stats', error);
      toast({
        title: 'Ошибка загрузки',
        description: 'Не удалось получить статистику кэша',
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    }
  };

  // Функция загрузки health статуса кэша
  const loadCacheHealth = async () => {
    try {
      const response = await api.get('/cache/health');
      setCacheHealth(response.data);
      logger.debug('Cache health loaded', { data: response.data });
    } catch (error) {
      logger.error('Failed to load cache health', error);
    }
  };

  // Функция очистки кэша
  const handleClearCache = async (pattern = '*') => {
    setClearLoading(true);
    try {
      const endpoint = pattern === '*' ? '/cache/clear' : `/cache/clear/${encodeURIComponent(pattern)}`;
      const response = await api.post(endpoint);
      
      toast({
        title: 'Кэш очищен',
        description: response.data.message || `Очищен кэш по паттерну: ${pattern}`,
        status: 'success',
        duration: 3000,
        isClosable: true,
      });
      
      // Обновляем статистику после очистки
      setTimeout(loadCacheStats, 1000);
      logger.info('Cache cleared', { pattern });
    } catch (error) {
      logger.error('Failed to clear cache', error);
      toast({
        title: 'Ошибка очистки',
        description: 'Не удалось очистить кэш',
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    } finally {
      setClearLoading(false);
    }
  };

  // Общая функция обновления всех данных
  const refreshAllData = async () => {
    setLoading(true);
    try {
      await Promise.all([
        loadCacheStats(),
        loadCacheHealth()
      ]);
    } catch (error) {
      logger.error('Failed to refresh cache data', error);
    } finally {
      setLoading(false);
    }
  };

  // Эффект для первоначальной загрузки и автообновления
  useEffect(() => {
    refreshAllData();

    if (autoRefresh) {
      intervalRef.current = setInterval(refreshAllData, 15000); // Обновление каждые 15 секунд
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
          <Spinner size="xl" color="blue.500" />
          <Text color={colors.text.muted}>Загрузка данных кэша...</Text>
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
            <Icon as={FiDatabase} boxSize={8} color="blue.400" />
            <Heading size="lg" color={colors.text.primary}>
              Управление кэшем
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

        {/* Health статус кэша */}
        {cacheHealth && (
          <Alert 
            status={cacheHealth.cache_working ? 'success' : 'error'} 
            borderRadius="md"
          >
            <AlertIcon />
            <Box>
              <AlertTitle>
                {cacheHealth.cache_working ? 'Кэш работает' : 'Проблемы с кэшем'}
              </AlertTitle>
              <AlertDescription>
                {cacheHealth.cache_working 
                  ? `Кэширование работает нормально (${cacheHealth.backend || 'unknown'})`
                  : `Ошибка: ${cacheHealth.error || 'неизвестная ошибка'}`
                }
                {cacheHealth.redis_connected && ' • Redis подключен'}
                {!cacheHealth.redis_connected && cacheHealth.cache_working && ' • Fallback режим'}
              </AlertDescription>
            </Box>
          </Alert>
        )}

        {/* Основная статистика */}
        {cacheStats && (
          <>
            <Grid templateColumns="repeat(auto-fill, minmax(300px, 1fr))" gap={6}>
              {/* Общая статистика */}
              <CacheStatsCard
                title="Общая статистика"
                icon={FiActivity}
                color="blue"
                stats={[
                  { label: 'Общий размер', value: formatBytes(cacheStats.total_size || 0) },
                  { label: 'Количество ключей', value: formatNumber(cacheStats.total_keys || 0) },
                  { label: 'Среднее TTL', value: formatDuration(cacheStats.average_ttl || 0) },
                  { label: 'Время работы', value: formatDuration(cacheStats.uptime || 0) },
                ]}
              />

              {/* Статистика производительности */}
              <CacheStatsCard
                title="Производительность"
                icon={FiZap}
                color="green"
                stats={[
                  { label: 'Hits', value: formatNumber(cacheStats.hits || 0) },
                  { label: 'Misses', value: formatNumber(cacheStats.misses || 0) },
                  { label: 'Hit Rate', value: `${((cacheStats.hits || 0) / ((cacheStats.hits || 0) + (cacheStats.misses || 0)) * 100 || 0).toFixed(1)}%` },
                  { label: 'Операций/сек', value: formatNumber(cacheStats.ops_per_sec || 0) },
                ]}
              />

              {/* Использование памяти */}
              {cacheStats.memory && (
                <CacheStatsCard
                  title="Использование памяти"
                  icon={FiHardDrive}
                  color="purple"
                  stats={[
                    { label: 'Используется', value: formatBytes(cacheStats.memory.used || 0) },
                    { label: 'Пик использования', value: formatBytes(cacheStats.memory.peak || 0) },
                    { label: 'RSS память', value: formatBytes(cacheStats.memory.rss || 0) },
                    { label: 'Фрагментация', value: `${(cacheStats.memory.fragmentation_ratio || 0).toFixed(2)}` },
                  ]}
                />
              )}

              {/* Hit/Miss визуализация */}
              <HitMissChart
                hitRate={cacheStats.hits || 0}
                missRate={cacheStats.misses || 0}
                title="Hit/Miss Ratio"
              />

              {/* Панель управления */}
              <CacheControlPanel
                onClearCache={handleClearCache}
                loading={clearLoading}
              />

              {/* Детальная статистика по типам */}
              {cacheStats.stats_by_type && (
                <Card bg={colors.background.card}>
                  <CardHeader>
                    <HStack spacing={3}>
                      <Icon as={FiLayers} boxSize={5} color="teal.500" />
                      <Heading size="sm" color={colors.text.primary}>
                        Статистика по типам
                      </Heading>
                    </HStack>
                  </CardHeader>
                  <CardBody>
                    <VStack spacing={3}>
                      {Object.entries(cacheStats.stats_by_type).map(([type, stats]) => (
                        <HStack key={type} justify="space-between" w="full">
                          <Text fontSize="sm" color={colors.text.muted}>
                            {type}
                          </Text>
                          <VStack spacing={0} align="end">
                            <Text fontSize="sm" fontWeight="medium" color={colors.text.primary}>
                              {stats.count} ключей
                            </Text>
                            <Text fontSize="xs" color={colors.text.muted}>
                              {formatBytes(stats.size)}
                            </Text>
                          </VStack>
                        </HStack>
                      ))}
                    </VStack>
                  </CardBody>
                </Card>
              )}
            </Grid>
          </>
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

export default CacheManager;