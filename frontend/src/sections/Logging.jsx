import React, { useState, useEffect, useRef } from 'react';
import {
  Box,
  VStack,
  HStack,
  Heading,
  Text,
  Card,
  CardHeader,
  CardBody,
  Button,
  Switch,
  Select,
  Input,
  InputGroup,
  InputLeftElement,
  Badge,
  Divider,
  Tabs,
  TabList,
  TabPanels,
  Tab,
  TabPanel,
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  Code,
  Alert,
  AlertIcon,
  AlertDescription,
  Spinner,
  useToast,
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalBody,
  ModalCloseButton,
  useDisclosure,
  FormControl,
  FormLabel,
  Textarea,
  Progress,
  Stat,
  StatLabel,
  StatNumber,
  StatHelpText,
  StatGroup,
  Tooltip
} from '@chakra-ui/react';
import {
  FiSettings,
  FiFileText,
  FiDownload,
  FiPlay,
  FiPause,
  FiRefreshCw,
  FiSearch,
  FiFilter,
  FiEye,
  FiSend,
  FiActivity,
  FiAlertCircle,
  FiInfo,
  FiAlertTriangle
} from 'react-icons/fi';
import { createLogger } from '../utils/logger.js';

const logger = createLogger('Logging');

const Logging = ({ currentAdmin }) => {
  // Состояния
  const [config, setConfig] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [logFiles, setLogFiles] = useState([]);
  const [selectedFile, setSelectedFile] = useState(null);
  const [logContent, setLogContent] = useState([]);
  const [liveLogsEnabled, setLiveLogsEnabled] = useState(false);
  const [statistics, setStatistics] = useState(null);
  
  // Фильтры
  const [searchTerm, setSearchTerm] = useState('');
  const [levelFilter, setLevelFilter] = useState('');
  const [linesCount, setLinesCount] = useState(100);
  
  // Настройки формы
  const [formData, setFormData] = useState({
    log_level: 'INFO',
    log_format: 'text',
    log_to_file: true,
    log_retention_days: 30,
    max_log_file_size_mb: 10,
    telegram_notifications: {
      enabled: false,
      chat_id: '',
      min_level: 'ERROR',
      rate_limit_minutes: 5
    }
  });
  
  const toast = useToast();
  const { isOpen, onOpen, onClose } = useDisclosure();
  const liveLogsRef = useRef(null);
  const eventSourceRef = useRef(null);

  // Загрузка конфигурации при монтировании
  useEffect(() => {
    loadConfig();
    loadLogFiles();
    loadStatistics();
  }, []);

  // Cleanup при размонтировании
  useEffect(() => {
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
    };
  }, []);

  const loadConfig = async () => {
    try {
      const response = await fetch('/api/logging/config', {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        }
      });
      
      if (!response.ok) {
        throw new Error('Ошибка загрузки конфигурации');
      }
      
      const data = await response.json();
      setConfig(data);
      setFormData(data);
      logger.debug('Конфигурация логирования загружена', data);
    } catch (error) {
      logger.error('Ошибка загрузки конфигурации логирования:', error);
      toast({
        title: 'Ошибка',
        description: 'Не удалось загрузить конфигурацию логирования',
        status: 'error',
        duration: 5000
      });
    } finally {
      setLoading(false);
    }
  };

  const loadLogFiles = async () => {
    try {
      const response = await fetch('/api/logging/files', {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        }
      });
      
      if (!response.ok) {
        throw new Error('Ошибка загрузки файлов логов');
      }
      
      const data = await response.json();
      setLogFiles(data);
      logger.debug('Файлы логов загружены', { count: data.length });
    } catch (error) {
      logger.error('Ошибка загрузки файлов логов:', error);
      toast({
        title: 'Ошибка',
        description: 'Не удалось загрузить список файлов логов',
        status: 'error',
        duration: 5000
      });
    }
  };

  const loadStatistics = async () => {
    try {
      const response = await fetch('/api/logging/statistics?hours=24', {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        }
      });
      
      if (!response.ok) {
        throw new Error('Ошибка загрузки статистики');
      }
      
      const data = await response.json();
      setStatistics(data);
      logger.debug('Статистика логов загружена', data);
    } catch (error) {
      logger.error('Ошибка загрузки статистики:', error);
    }
  };

  const saveConfig = async () => {
    setSaving(true);
    try {
      const response = await fetch('/api/logging/config', {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        },
        body: JSON.stringify(formData)
      });
      
      if (!response.ok) {
        throw new Error('Ошибка сохранения конфигурации');
      }
      
      const data = await response.json();
      setConfig(data);
      setFormData(data);
      
      toast({
        title: 'Успешно',
        description: 'Конфигурация логирования обновлена',
        status: 'success',
        duration: 3000
      });
      
      logger.info('Конфигурация логирования обновлена');
    } catch (error) {
      logger.error('Ошибка сохранения конфигурации:', error);
      toast({
        title: 'Ошибка',
        description: 'Не удалось сохранить конфигурацию',
        status: 'error',
        duration: 5000
      });
    } finally {
      setSaving(false);
    }
  };

  const loadLogContent = async (filename) => {
    try {
      const params = new URLSearchParams({
        lines: linesCount.toString()
      });
      
      if (searchTerm) params.append('search', searchTerm);
      if (levelFilter) params.append('level', levelFilter);
      
      const response = await fetch(`/api/logging/files/${filename}/content?${params}`, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        }
      });
      
      if (!response.ok) {
        throw new Error('Ошибка загрузки содержимого лога');
      }
      
      const data = await response.json();
      setLogContent(data.content);
      setSelectedFile(filename);
      logger.debug('Содержимое лога загружено', { filename, lines: data.lines_count });
    } catch (error) {
      logger.error('Ошибка загрузки содержимого лога:', error);
      toast({
        title: 'Ошибка',
        description: 'Не удалось загрузить содержимое лога',
        status: 'error',
        duration: 5000
      });
    }
  };

  const downloadLogFile = async (filename) => {
    try {
      const response = await fetch(`/api/logging/files/${filename}/download`, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        }
      });
      
      if (!response.ok) {
        throw new Error('Ошибка скачивания файла');
      }
      
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
      
      logger.info('Файл лога скачан', { filename });
    } catch (error) {
      logger.error('Ошибка скачивания файла:', error);
      toast({
        title: 'Ошибка',
        description: 'Не удалось скачать файл',
        status: 'error',
        duration: 5000
      });
    }
  };

  const toggleLiveLogs = () => {
    if (liveLogsEnabled) {
      // Останавливаем live логи
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
      setLiveLogsEnabled(false);
      logger.debug('Live логи остановлены');
    } else {
      // Запускаем live логи
      const params = new URLSearchParams();
      if (levelFilter) params.append('level', levelFilter);
      if (searchTerm) params.append('search', searchTerm);
      
      const eventSource = new EventSource(`/api/logging/live?${params}`);
      
      eventSource.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.error) {
            logger.error('Ошибка в live логах:', data.error);
            return;
          }
          
          if (data.line) {
            setLogContent(prev => [data.line, ...prev.slice(0, 999)]);
            
            // Автоскролл
            if (liveLogsRef.current) {
              liveLogsRef.current.scrollTop = 0;
            }
          }
        } catch (error) {
          logger.error('Ошибка парсинга live лога:', error);
        }
      };
      
      eventSource.onerror = (error) => {
        logger.error('Ошибка EventSource:', error);
        eventSource.close();
        setLiveLogsEnabled(false);
      };
      
      eventSourceRef.current = eventSource;
      setLiveLogsEnabled(true);
      setLogContent([]);
      logger.debug('Live логи запущены');
    }
  };

  const testTelegramNotification = async () => {
    try {
      const response = await fetch('/api/logging/test-notification', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        }
      });
      
      if (!response.ok) {
        throw new Error('Ошибка тестирования уведомлений');
      }
      
      const data = await response.json();
      
      if (data.success) {
        toast({
          title: 'Успешно',
          description: 'Тестовое уведомление отправлено',
          status: 'success',
          duration: 3000
        });
      } else {
        throw new Error(data.message);
      }
      
      logger.info('Тестовое уведомление отправлено');
    } catch (error) {
      logger.error('Ошибка тестирования уведомлений:', error);
      toast({
        title: 'Ошибка',
        description: 'Не удалось отправить тестовое уведомление',
        status: 'error',
        duration: 5000
      });
    }
  };

  const formatFileSize = (bytes) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const getLevelColor = (level) => {
    const colors = {
      'DEBUG': 'gray',
      'INFO': 'blue',
      'WARNING': 'yellow',
      'ERROR': 'red',
      'CRITICAL': 'purple'
    };
    return colors[level] || 'gray';
  };

  const getLevelIcon = (level) => {
    const icons = {
      'DEBUG': FiInfo,
      'INFO': FiInfo,
      'WARNING': FiAlertTriangle,
      'ERROR': FiAlertCircle,
      'CRITICAL': FiAlertCircle
    };
    return icons[level] || FiInfo;
  };

  if (loading) {
    return (
      <Box p={6}>
        <VStack spacing={4}>
          <Spinner size="xl" />
          <Text>Загрузка конфигурации логирования...</Text>
        </VStack>
      </Box>
    );
  }

  return (
    <Box p={6}>
      <VStack spacing={6} align="stretch">
        <HStack justify="space-between" align="center">
          <Heading size="lg" color="white">
            <HStack>
              <FiFileText />
              <Text>Управление логированием</Text>
            </HStack>
          </Heading>
          
          <HStack>
            <Button
              leftIcon={<FiRefreshCw />}
              variant="outline"
              size="sm"
              onClick={loadConfig}
            >
              Обновить
            </Button>
          </HStack>
        </HStack>

        {/* Статистика логов */}
        {statistics && (
          <Card bg="gray.800" borderColor="gray.700">
            <CardHeader>
              <Heading size="md" color="white">Статистика за 24 часа</Heading>
            </CardHeader>
            <CardBody>
              <StatGroup>
                <Stat>
                  <StatLabel color="gray.400">Всего записей</StatLabel>
                  <StatNumber color="white">{statistics.total_entries}</StatNumber>
                </Stat>
                <Stat>
                  <StatLabel color="gray.400">Ошибки</StatLabel>
                  <StatNumber color="red.400">{statistics.errors_count}</StatNumber>
                  <StatHelpText color="gray.500">{statistics.error_rate}%</StatHelpText>
                </Stat>
                <Stat>
                  <StatLabel color="gray.400">Предупреждения</StatLabel>
                  <StatNumber color="yellow.400">{statistics.warnings_count}</StatNumber>
                  <StatHelpText color="gray.500">{statistics.warning_rate}%</StatHelpText>
                </Stat>
              </StatGroup>
            </CardBody>
          </Card>
        )}

        <Tabs variant="enclosed" colorScheme="purple">
          <TabList>
            <Tab _selected={{ bg: 'purple.600', color: 'white' }}>
              <HStack>
                <FiSettings />
                <Text>Настройки</Text>
              </HStack>
            </Tab>
            <Tab _selected={{ bg: 'purple.600', color: 'white' }}>
              <HStack>
                <FiFileText />
                <Text>Просмотр логов</Text>
              </HStack>
            </Tab>
            <Tab _selected={{ bg: 'purple.600', color: 'white' }}>
              <HStack>
                <FiActivity />
                <Text>Live логи</Text>
              </HStack>
            </Tab>
          </TabList>

          <TabPanels>
            {/* Вкладка настроек */}
            <TabPanel>
              <VStack spacing={6} align="stretch">
                <Card bg="gray.800" borderColor="gray.700">
                  <CardHeader>
                    <Heading size="md" color="white">Основные настройки</Heading>
                  </CardHeader>
                  <CardBody>
                    <VStack spacing={4} align="stretch">
                      <HStack spacing={4}>
                        <FormControl>
                          <FormLabel color="gray.300">Уровень логирования</FormLabel>
                          <Select
                            value={formData.log_level}
                            onChange={(e) => setFormData(prev => ({...prev, log_level: e.target.value}))}
                            bg="gray.700"
                            borderColor="gray.600"
                            color="white"
                          >
                            <option value="DEBUG">DEBUG</option>
                            <option value="INFO">INFO</option>
                            <option value="WARNING">WARNING</option>
                            <option value="ERROR">ERROR</option>
                            <option value="CRITICAL">CRITICAL</option>
                          </Select>
                        </FormControl>

                        <FormControl>
                          <FormLabel color="gray.300">Формат логов</FormLabel>
                          <Select
                            value={formData.log_format}
                            onChange={(e) => setFormData(prev => ({...prev, log_format: e.target.value}))}
                            bg="gray.700"
                            borderColor="gray.600"
                            color="white"
                          >
                            <option value="text">Текстовый</option>
                            <option value="json">JSON</option>
                          </Select>
                        </FormControl>
                      </HStack>

                      <HStack spacing={4} align="flex-end">
                        <FormControl display="flex" alignItems="center">
                          <FormLabel color="gray.300" mb="0">Запись в файл</FormLabel>
                          <Switch
                            isChecked={formData.log_to_file}
                            onChange={(e) => setFormData(prev => ({...prev, log_to_file: e.target.checked}))}
                            colorScheme="purple"
                          />
                        </FormControl>

                        <FormControl>
                          <FormLabel color="gray.300">Срок хранения (дни)</FormLabel>
                          <Input
                            type="number"
                            value={formData.log_retention_days}
                            onChange={(e) => setFormData(prev => ({...prev, log_retention_days: parseInt(e.target.value)}))}
                            bg="gray.700"
                            borderColor="gray.600"
                            color="white"
                            min="1"
                            max="365"
                          />
                        </FormControl>

                        <FormControl>
                          <FormLabel color="gray.300">Размер файла (MB)</FormLabel>
                          <Input
                            type="number"
                            value={formData.max_log_file_size_mb}
                            onChange={(e) => setFormData(prev => ({...prev, max_log_file_size_mb: parseInt(e.target.value)}))}
                            bg="gray.700"
                            borderColor="gray.600"
                            color="white"
                            min="1"
                            max="100"
                          />
                        </FormControl>
                      </HStack>
                    </VStack>
                  </CardBody>
                </Card>

                {/* Настройки Telegram уведомлений */}
                <Card bg="gray.800" borderColor="gray.700">
                  <CardHeader>
                    <Heading size="md" color="white">Telegram уведомления</Heading>
                  </CardHeader>
                  <CardBody>
                    <VStack spacing={4} align="stretch">
                      <HStack justify="space-between">
                        <FormControl display="flex" alignItems="center">
                          <FormLabel color="gray.300" mb="0">Включить уведомления</FormLabel>
                          <Switch
                            isChecked={formData.telegram_notifications.enabled}
                            onChange={(e) => setFormData(prev => ({
                              ...prev,
                              telegram_notifications: {
                                ...prev.telegram_notifications,
                                enabled: e.target.checked
                              }
                            }))}
                            colorScheme="purple"
                          />
                        </FormControl>

                        <Button
                          size="sm"
                          colorScheme="blue"
                          leftIcon={<FiSend />}
                          onClick={testTelegramNotification}
                          isDisabled={!formData.telegram_notifications.enabled}
                        >
                          Тест
                        </Button>
                      </HStack>

                      {formData.telegram_notifications.enabled && (
                        <HStack spacing={4}>
                          <FormControl>
                            <FormLabel color="gray.300">ID чата</FormLabel>
                            <Input
                              value={formData.telegram_notifications.chat_id}
                              onChange={(e) => setFormData(prev => ({
                                ...prev,
                                telegram_notifications: {
                                  ...prev.telegram_notifications,
                                  chat_id: e.target.value
                                }
                              }))}
                              placeholder="-100123456789"
                              bg="gray.700"
                              borderColor="gray.600"
                              color="white"
                            />
                          </FormControl>

                          <FormControl>
                            <FormLabel color="gray.300">Мин. уровень</FormLabel>
                            <Select
                              value={formData.telegram_notifications.min_level}
                              onChange={(e) => setFormData(prev => ({
                                ...prev,
                                telegram_notifications: {
                                  ...prev.telegram_notifications,
                                  min_level: e.target.value
                                }
                              }))}
                              bg="gray.700"
                              borderColor="gray.600"
                              color="white"
                            >
                              <option value="WARNING">WARNING</option>
                              <option value="ERROR">ERROR</option>
                              <option value="CRITICAL">CRITICAL</option>
                            </Select>
                          </FormControl>

                          <FormControl>
                            <FormLabel color="gray.300">Интервал (мин)</FormLabel>
                            <Input
                              type="number"
                              value={formData.telegram_notifications.rate_limit_minutes}
                              onChange={(e) => setFormData(prev => ({
                                ...prev,
                                telegram_notifications: {
                                  ...prev.telegram_notifications,
                                  rate_limit_minutes: parseInt(e.target.value)
                                }
                              }))}
                              bg="gray.700"
                              borderColor="gray.600"
                              color="white"
                              min="1"
                              max="60"
                            />
                          </FormControl>
                        </HStack>
                      )}
                    </VStack>
                  </CardBody>
                </Card>

                <HStack justify="flex-end">
                  <Button
                    colorScheme="purple"
                    onClick={saveConfig}
                    isLoading={saving}
                    loadingText="Сохранение..."
                    leftIcon={<FiSettings />}
                  >
                    Сохранить настройки
                  </Button>
                </HStack>
              </VStack>
            </TabPanel>

            {/* Вкладка просмотра логов */}
            <TabPanel>
              <VStack spacing={4} align="stretch">
                {/* Фильтры */}
                <Card bg="gray.800" borderColor="gray.700">
                  <CardBody>
                    <HStack spacing={4}>
                      <InputGroup>
                        <InputLeftElement pointerEvents="none">
                          <FiSearch color="gray.300" />
                        </InputLeftElement>
                        <Input
                          placeholder="Поиск в логах..."
                          value={searchTerm}
                          onChange={(e) => setSearchTerm(e.target.value)}
                          bg="gray.700"
                          borderColor="gray.600"
                          color="white"
                        />
                      </InputGroup>

                      <Select
                        placeholder="Уровень"
                        value={levelFilter}
                        onChange={(e) => setLevelFilter(e.target.value)}
                        bg="gray.700"
                        borderColor="gray.600"
                        color="white"
                        width="150px"
                      >
                        <option value="DEBUG">DEBUG</option>
                        <option value="INFO">INFO</option>
                        <option value="WARNING">WARNING</option>
                        <option value="ERROR">ERROR</option>
                        <option value="CRITICAL">CRITICAL</option>
                      </Select>

                      <Input
                        type="number"
                        placeholder="Строки"
                        value={linesCount}
                        onChange={(e) => setLinesCount(parseInt(e.target.value) || 100)}
                        bg="gray.700"
                        borderColor="gray.600"
                        color="white"
                        width="100px"
                        min="10"
                        max="10000"
                      />
                    </HStack>
                  </CardBody>
                </Card>

                {/* Список файлов логов */}
                <Card bg="gray.800" borderColor="gray.700">
                  <CardHeader>
                    <Heading size="md" color="white">Файлы логов</Heading>
                  </CardHeader>
                  <CardBody>
                    <Table variant="simple">
                      <Thead>
                        <Tr>
                          <Th color="gray.400">Файл</Th>
                          <Th color="gray.400">Размер</Th>
                          <Th color="gray.400">Изменен</Th>
                          <Th color="gray.400">Действия</Th>
                        </Tr>
                      </Thead>
                      <Tbody>
                        {logFiles.map((file) => (
                          <Tr key={file.name}>
                            <Td color="white">
                              <HStack>
                                <Text>{file.name}</Text>
                                {file.is_current && (
                                  <Badge colorScheme="green" size="sm">
                                    Текущий
                                  </Badge>
                                )}
                              </HStack>
                            </Td>
                            <Td color="gray.300">{formatFileSize(file.size)}</Td>
                            <Td color="gray.300">
                              {new Date(file.modified).toLocaleString('ru-RU')}
                            </Td>
                            <Td>
                              <HStack>
                                <Tooltip label="Просмотреть">
                                  <Button
                                    size="sm"
                                    variant="outline"
                                    colorScheme="blue"
                                    onClick={() => loadLogContent(file.name)}
                                  >
                                    <FiEye />
                                  </Button>
                                </Tooltip>
                                <Tooltip label="Скачать">
                                  <Button
                                    size="sm"
                                    variant="outline"
                                    colorScheme="green"
                                    onClick={() => downloadLogFile(file.name)}
                                  >
                                    <FiDownload />
                                  </Button>
                                </Tooltip>
                              </HStack>
                            </Td>
                          </Tr>
                        ))}
                      </Tbody>
                    </Table>
                  </CardBody>
                </Card>

                {/* Содержимое лога */}
                {selectedFile && logContent.length > 0 && (
                  <Card bg="gray.800" borderColor="gray.700">
                    <CardHeader>
                      <Heading size="md" color="white">
                        Содержимое: {selectedFile}
                      </Heading>
                    </CardHeader>
                    <CardBody>
                      <Box
                        bg="gray.900"
                        p={4}
                        borderRadius="md"
                        maxHeight="400px"
                        overflowY="auto"
                      >
                        <VStack align="stretch" spacing={1}>
                          {logContent.map((line, index) => {
                            const levelMatch = line.match(/\[(DEBUG|INFO|WARNING|ERROR|CRITICAL)\]/);
                            const level = levelMatch ? levelMatch[1] : '';
                            
                            return (
                              <HStack key={index} align="flex-start" spacing={2}>
                                {level && (
                                  <Badge 
                                    colorScheme={getLevelColor(level)} 
                                    size="sm"
                                    minWidth="60px"
                                  >
                                    {level}
                                  </Badge>
                                )}
                                <Code
                                  display="block"
                                  whiteSpace="pre-wrap"
                                  bg="transparent"
                                  color="gray.100"
                                  fontSize="sm"
                                  p={0}
                                  flex="1"
                                >
                                  {line}
                                </Code>
                              </HStack>
                            );
                          })}
                        </VStack>
                      </Box>
                    </CardBody>
                  </Card>
                )}
              </VStack>
            </TabPanel>

            {/* Вкладка Live логов */}
            <TabPanel>
              <VStack spacing={4} align="stretch">
                <Card bg="gray.800" borderColor="gray.700">
                  <CardHeader>
                    <HStack justify="space-between">
                      <Heading size="md" color="white">Live мониторинг логов</Heading>
                      <HStack>
                        <Button
                          size="sm"
                          colorScheme={liveLogsEnabled ? 'red' : 'green'}
                          leftIcon={liveLogsEnabled ? <FiPause /> : <FiPlay />}
                          onClick={toggleLiveLogs}
                        >
                          {liveLogsEnabled ? 'Остановить' : 'Запустить'}
                        </Button>
                        {liveLogsEnabled && (
                          <Badge colorScheme="green">Запущено</Badge>
                        )}
                      </HStack>
                    </HStack>
                  </CardHeader>
                  <CardBody>
                    {liveLogsEnabled && (
                      <Alert status="info" mb={4}>
                        <AlertIcon />
                        <AlertDescription color="gray.800">
                          Live мониторинг активен. Новые записи отображаются в реальном времени.
                        </AlertDescription>
                      </Alert>
                    )}

                    <Box
                      ref={liveLogsRef}
                      bg="gray.900"
                      p={4}
                      borderRadius="md"
                      height="500px"
                      overflowY="auto"
                      border="1px solid"
                      borderColor="gray.600"
                    >
                      {logContent.length === 0 ? (
                        <Text color="gray.500" textAlign="center" mt={8}>
                          {liveLogsEnabled ? 'Ожидание новых логов...' : 'Запустите мониторинг для просмотра логов в реальном времени'}
                        </Text>
                      ) : (
                        <VStack align="stretch" spacing={1}>
                          {logContent.map((line, index) => {
                            const levelMatch = line.match(/\[(DEBUG|INFO|WARNING|ERROR|CRITICAL)\]/);
                            const level = levelMatch ? levelMatch[1] : '';
                            const LevelIcon = getLevelIcon(level);
                            
                            return (
                              <HStack key={index} align="flex-start" spacing={2}>
                                {level && (
                                  <HStack spacing={1}>
                                    <LevelIcon size={12} color={getLevelColor(level)} />
                                    <Badge 
                                      colorScheme={getLevelColor(level)} 
                                      size="sm"
                                      minWidth="60px"
                                    >
                                      {level}
                                    </Badge>
                                  </HStack>
                                )}
                                <Code
                                  display="block"
                                  whiteSpace="pre-wrap"
                                  bg="transparent"
                                  color="gray.100"
                                  fontSize="sm"
                                  p={0}
                                  flex="1"
                                >
                                  {line}
                                </Code>
                              </HStack>
                            );
                          })}
                        </VStack>
                      )}
                    </Box>
                  </CardBody>
                </Card>
              </VStack>
            </TabPanel>
          </TabPanels>
        </Tabs>
      </VStack>
    </Box>
  );
};

export default Logging;