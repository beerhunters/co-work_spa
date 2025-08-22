import React, { useState, useEffect } from 'react';
import {
  Box,
  VStack,
  HStack,
  Text,
  Button,
  Card,
  CardBody,
  CardHeader,
  Heading,
  Progress,
  Badge,
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  TableContainer,
  Alert,
  AlertIcon,
  AlertTitle,
  AlertDescription,
  Stat,
  StatLabel,
  StatNumber,
  StatHelpText,
  StatArrow,
  SimpleGrid,
  Icon,
  Divider,
  Tooltip,
  Spinner,
  useToast,
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalFooter,
  ModalBody,
  ModalCloseButton,
  useDisclosure,
  List,
  ListItem,
  ListIcon,
  Code,
  Flex,
  Switch,
  FormControl,
  FormLabel
} from '@chakra-ui/react';
import {
  FiDatabase,
  FiClock,
  FiTrendingUp,
  FiAlertTriangle,
  FiCheckCircle,
  FiZap,
  FiSettings,
  FiRefreshCw,
  FiBarChart,
  FiActivity,
  FiTarget,
  FiLayers,
  FiCpu,
  FiHardDrive,
  FiSearch
} from 'react-icons/fi';
import { colors, sizes } from '../styles/styles';
import api from '../utils/api';

const Performance = () => {
  const [loading, setLoading] = useState(true);
  const [performanceData, setPerformanceData] = useState(null);
  const [slowQueries, setSlowQueries] = useState([]);
  const [recommendations, setRecommendations] = useState([]);
  const [indexSuggestions, setIndexSuggestions] = useState([]);
  const [creatingIndex, setCreatingIndex] = useState(null);
  const [autoRefresh, setAutoRefresh] = useState(false);
  const toast = useToast();
  const { isOpen, onOpen, onClose } = useDisclosure();
  const [selectedQuery, setSelectedQuery] = useState(null);

  useEffect(() => {
    fetchPerformanceData();
  }, []);

  useEffect(() => {
    let interval;
    if (autoRefresh) {
      interval = setInterval(fetchPerformanceData, 30000); // Обновление каждые 30 секунд
    }
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [autoRefresh]);

  const fetchPerformanceData = async () => {
    try {
      const [perfResponse, queriesResponse, recsResponse] = await Promise.all([
        api.get('/optimization/performance-stats'),
        api.get('/optimization/slow-queries'),
        api.get('/optimization/recommendations')
      ]);

      setPerformanceData(perfResponse.data.performance_stats);
      setSlowQueries(queriesResponse.data.slow_queries || []);
      setRecommendations(recsResponse.data.recommendations || []);
      setIndexSuggestions(recsResponse.data.index_suggestions || []);
    } catch (error) {
      console.error('Ошибка загрузки данных производительности:', error);
      toast({
        title: 'Ошибка загрузки',
        description: 'Не удалось загрузить данные производительности',
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    } finally {
      setLoading(false);
    }
  };

  const createIndex = async (suggestion) => {
    setCreatingIndex(suggestion.id);
    try {
      await api.post('/optimization/create-index', {
        table: suggestion.table,
        columns: suggestion.columns,
        index_type: suggestion.type || 'btree'
      });
      
      toast({
        title: 'Индекс создан',
        description: `Индекс на ${suggestion.table}(${suggestion.columns.join(', ')}) успешно создан`,
        status: 'success',
        duration: 5000,
        isClosable: true,
      });
      
      fetchPerformanceData(); // Перезагружаем данные
    } catch (error) {
      console.error('Ошибка создания индекса:', error);
      toast({
        title: 'Ошибка создания индекса',
        description: error.response?.data?.detail || 'Не удалось создать индекс',
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    } finally {
      setCreatingIndex(null);
    }
  };

  const optimizeQuery = async (queryId) => {
    try {
      await api.post(`/optimization/optimize-query/${queryId}`);
      toast({
        title: 'Запрос оптимизирован',
        description: 'Запрос был успешно оптимизирован',
        status: 'success',
        duration: 3000,
        isClosable: true,
      });
      fetchPerformanceData();
    } catch (error) {
      console.error('Ошибка оптимизации запроса:', error);
      toast({
        title: 'Ошибка оптимизации',
        description: 'Не удалось оптимизировать запрос',
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    }
  };

  const formatDuration = (ms) => {
    if (ms < 1000) return `${ms}мс`;
    if (ms < 60000) return `${(ms / 1000).toFixed(1)}с`;
    return `${(ms / 60000).toFixed(1)}мин`;
  };

  const formatBytes = (bytes) => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const getPerformanceColor = (score) => {
    if (score >= 80) return 'green';
    if (score >= 60) return 'yellow';
    return 'red';
  };

  const openQueryDetails = (query) => {
    setSelectedQuery(query);
    onOpen();
  };

  if (loading) {
    return (
      <Box p={6} textAlign="center">
        <Spinner size="xl" color={colors.primary} />
        <Text mt={4} color={colors.text.muted}>Загрузка данных производительности...</Text>
      </Box>
    );
  }

  return (
    <Box p={6} maxW="full">
      <Flex justify="space-between" align="center" mb={6}>
        <Heading size="lg" color={colors.text.primary}>
          <Icon as={FiActivity} mr={3} />
          Анализ производительности
        </Heading>
        <HStack>
          <FormControl display="flex" alignItems="center">
            <FormLabel htmlFor="auto-refresh" mb="0" fontSize="sm">
              Автообновление
            </FormLabel>
            <Switch 
              id="auto-refresh" 
              isChecked={autoRefresh}
              onChange={(e) => setAutoRefresh(e.target.checked)}
              colorScheme="blue"
            />
          </FormControl>
          <Button
            leftIcon={<FiRefreshCw />}
            onClick={fetchPerformanceData}
            colorScheme="blue"
            size="sm"
          >
            Обновить
          </Button>
        </HStack>
      </Flex>

      <VStack spacing={6} align="stretch">
        {/* Общие метрики производительности */}
        <Card>
          <CardHeader>
            <Heading size="md">
              <Icon as={FiBarChart} mr={2} />
              Общая производительность
            </Heading>
          </CardHeader>
          <CardBody>
            <SimpleGrid columns={{ base: 2, md: 4 }} spacing={4}>
              <Stat>
                <StatLabel>Общий балл</StatLabel>
                <StatNumber color={getPerformanceColor(performanceData?.overall_score || 0)}>
                  {performanceData?.overall_score || 0}/100
                </StatNumber>
                <Progress 
                  value={performanceData?.overall_score || 0} 
                  colorScheme={getPerformanceColor(performanceData?.overall_score || 0)}
                  size="sm"
                  mt={2}
                />
              </Stat>
              
              <Stat>
                <StatLabel>Среднее время запроса</StatLabel>
                <StatNumber>{formatDuration(performanceData?.avg_query_time || 0)}</StatNumber>
                <StatHelpText>
                  <StatArrow type={performanceData?.query_time_trend > 0 ? 'increase' : 'decrease'} />
                  {Math.abs(performanceData?.query_time_trend || 0).toFixed(1)}%
                </StatHelpText>
              </Stat>
              
              <Stat>
                <StatLabel>Использование CPU</StatLabel>
                <StatNumber>{performanceData?.cpu_usage || 0}%</StatNumber>
                <Progress 
                  value={performanceData?.cpu_usage || 0} 
                  colorScheme={performanceData?.cpu_usage > 80 ? 'red' : 'green'}
                  size="sm"
                  mt={2}
                />
              </Stat>
              
              <Stat>
                <StatLabel>Использование памяти</StatLabel>
                <StatNumber>{formatBytes(performanceData?.memory_usage || 0)}</StatNumber>
                <StatHelpText>{performanceData?.memory_percentage || 0}%</StatHelpText>
              </Stat>
            </SimpleGrid>
          </CardBody>
        </Card>

        {/* Медленные запросы */}
        <Card>
          <CardHeader>
            <Flex justify="space-between" align="center">
              <Heading size="md">
                <Icon as={FiClock} mr={2} />
                Медленные запросы
              </Heading>
              <Badge colorScheme="red" variant="subtle">
                {slowQueries.length} активных
              </Badge>
            </Flex>
          </CardHeader>
          <CardBody>
            {slowQueries.length === 0 ? (
              <Alert status="success">
                <AlertIcon />
                <AlertTitle>Отлично!</AlertTitle>
                <AlertDescription>
                  Медленных запросов не обнаружено
                </AlertDescription>
              </Alert>
            ) : (
              <TableContainer>
                <Table variant="simple" size="sm">
                  <Thead>
                    <Tr>
                      <Th>Запрос</Th>
                      <Th>Время выполнения</Th>
                      <Th>Частота</Th>
                      <Th>Таблица</Th>
                      <Th>Действия</Th>
                    </Tr>
                  </Thead>
                  <Tbody>
                    {slowQueries.map((query, index) => (
                      <Tr key={index}>
                        <Td>
                          <Tooltip label="Нажмите для подробностей">
                            <Code 
                              fontSize="xs" 
                              cursor="pointer"
                              onClick={() => openQueryDetails(query)}
                              _hover={{ bg: colors.card.border }}
                            >
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
                        <Td>
                          <Button
                            size="xs"
                            colorScheme="green"
                            onClick={() => optimizeQuery(query.id)}
                            leftIcon={<FiZap />}
                          >
                            Оптимизировать
                          </Button>
                        </Td>
                      </Tr>
                    ))}
                  </Tbody>
                </Table>
              </TableContainer>
            )}
          </CardBody>
        </Card>

        {/* Рекомендации по индексам */}
        <Card>
          <CardHeader>
            <Flex justify="space-between" align="center">
              <Heading size="md">
                <Icon as={FiDatabase} mr={2} />
                Рекомендации по индексам
              </Heading>
              <Badge colorScheme="blue" variant="subtle">
                {indexSuggestions.length} предложений
              </Badge>
            </Flex>
          </CardHeader>
          <CardBody>
            {indexSuggestions.length === 0 ? (
              <Alert status="info">
                <AlertIcon />
                <AlertTitle>Хорошая работа!</AlertTitle>
                <AlertDescription>
                  Дополнительные индексы не требуются
                </AlertDescription>
              </Alert>
            ) : (
              <VStack spacing={3} align="stretch">
                {indexSuggestions.map((suggestion, index) => (
                  <Card key={index} variant="outline" size="sm">
                    <CardBody>
                      <Flex justify="space-between" align="center">
                        <Box flex="1">
                          <HStack spacing={3} mb={2}>
                            <Badge colorScheme="blue">
                              {suggestion.table}
                            </Badge>
                            <Text fontSize="sm" color={colors.text.muted}>
                              Колонки: {suggestion.columns.join(', ')}
                            </Text>
                          </HStack>
                          <Text fontSize="xs" color={colors.text.muted}>
                            {suggestion.reason}
                          </Text>
                          <HStack spacing={2} mt={2}>
                            <Badge size="sm" colorScheme="green">
                              Ускорение: {suggestion.estimated_improvement}
                            </Badge>
                            <Badge size="sm" colorScheme="purple">
                              Тип: {suggestion.type || 'btree'}
                            </Badge>
                          </HStack>
                        </Box>
                        <Button
                          size="sm"
                          colorScheme="blue"
                          onClick={() => createIndex(suggestion)}
                          isLoading={creatingIndex === suggestion.id}
                          loadingText="Создание..."
                          leftIcon={<FiCheckCircle />}
                        >
                          Создать индекс
                        </Button>
                      </Flex>
                    </CardBody>
                  </Card>
                ))}
              </VStack>
            )}
          </CardBody>
        </Card>

        {/* Общие рекомендации */}
        <Card>
          <CardHeader>
            <Heading size="md">
              <Icon as={FiTarget} mr={2} />
              Рекомендации по оптимизации
            </Heading>
          </CardHeader>
          <CardBody>
            {recommendations.length === 0 ? (
              <Alert status="success">
                <AlertIcon />
                <AlertTitle>Система оптимизирована!</AlertTitle>
                <AlertDescription>
                  Дополнительных рекомендаций нет
                </AlertDescription>
              </Alert>
            ) : (
              <List spacing={3}>
                {recommendations.map((rec, index) => (
                  <ListItem key={index}>
                    <ListIcon 
                      as={rec.priority === 'high' ? FiAlertTriangle : FiSettings} 
                      color={rec.priority === 'high' ? 'red.500' : 'blue.500'} 
                    />
                    <Box display="inline-block">
                      <Text fontWeight="medium">{rec.title}</Text>
                      <Text fontSize="sm" color={colors.text.muted}>
                        {rec.description}
                      </Text>
                      <HStack spacing={2} mt={1}>
                        <Badge 
                          size="sm" 
                          colorScheme={rec.priority === 'high' ? 'red' : rec.priority === 'medium' ? 'yellow' : 'green'}
                        >
                          {rec.priority}
                        </Badge>
                        {rec.impact && (
                          <Badge size="sm" colorScheme="purple">
                            Влияние: {rec.impact}
                          </Badge>
                        )}
                      </HStack>
                    </Box>
                  </ListItem>
                ))}
              </List>
            )}
          </CardBody>
        </Card>
      </VStack>

      {/* Модальное окно с деталями запроса */}
      <Modal isOpen={isOpen} onClose={onClose} size="xl">
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>
            <Icon as={FiSearch} mr={2} />
            Детали запроса
          </ModalHeader>
          <ModalCloseButton />
          <ModalBody>
            {selectedQuery && (
              <VStack spacing={4} align="stretch">
                <Box>
                  <Text fontWeight="medium" mb={2}>SQL запрос:</Text>
                  <Code p={3} display="block" whiteSpace="pre-wrap" fontSize="sm">
                    {selectedQuery.query_text}
                  </Code>
                </Box>
                
                <Divider />
                
                <SimpleGrid columns={2} spacing={4}>
                  <Stat>
                    <StatLabel>Среднее время</StatLabel>
                    <StatNumber>{formatDuration(selectedQuery.avg_duration)}</StatNumber>
                  </Stat>
                  <Stat>
                    <StatLabel>Количество выполнений</StatLabel>
                    <StatNumber>{selectedQuery.execution_count}</StatNumber>
                  </Stat>
                  <Stat>
                    <StatLabel>Максимальное время</StatLabel>
                    <StatNumber>{formatDuration(selectedQuery.max_duration)}</StatNumber>
                  </Stat>
                  <Stat>
                    <StatLabel>Таблица</StatLabel>
                    <StatNumber fontSize="md">{selectedQuery.table_name || 'N/A'}</StatNumber>
                  </Stat>
                </SimpleGrid>

                {selectedQuery.execution_plan && (
                  <>
                    <Divider />
                    <Box>
                      <Text fontWeight="medium" mb={2}>План выполнения:</Text>
                      <Code p={3} display="block" whiteSpace="pre-wrap" fontSize="xs">
                        {selectedQuery.execution_plan}
                      </Code>
                    </Box>
                  </>
                )}
              </VStack>
            )}
          </ModalBody>
          <ModalFooter>
            <Button onClick={onClose}>Закрыть</Button>
          </ModalFooter>
        </ModalContent>
      </Modal>
    </Box>
  );
};

export default Performance;