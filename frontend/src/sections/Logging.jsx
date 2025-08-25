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
  Spinner,
  useToast,
  FormControl,
  FormLabel,
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
  FiRefreshCw,
  FiSearch,
  FiEye,
  FiSend
} from 'react-icons/fi';
import { createLogger } from '../utils/logger.js';
import { getAuthToken } from '../utils/auth.js';

const logger = createLogger('Logging');

const Logging = ({ currentAdmin }) => {
  // Состояния
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [clearing, setClearing] = useState(false);
  const [logFiles, setLogFiles] = useState([]);
  const [selectedFile, setSelectedFile] = useState(null);
  const [logContent, setLogContent] = useState([]);
  const [statistics, setStatistics] = useState(null);
  const [config, setConfig] = useState(null);

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

  // Загрузка конфигурации при монтировании
  useEffect(() => {
    loadConfig();
    loadLogFiles();
    loadStatistics();
  }, []);

  const refreshData = async () => {
    setLoading(true);
    try {
      await Promise.all([
        loadConfig(),
        loadLogFiles(),
        loadStatistics()
      ]);
      
      toast({
        title: 'Обновлено',
        description: 'Данные успешно обновлены',
        status: 'success',
        duration: 2000
      });
    } catch (error) {
      logger.error('Ошибка обновления данных:', error);
      toast({
        title: 'Ошибка',
        description: 'Не удалось обновить данные',
        status: 'error',
        duration: 3000
      });
    } finally {
      setLoading(false);
    }
  };


  const loadConfig = async () => {
    try {
      const response = await fetch('/api/logging/config', {
        headers: {
          'Authorization': `Bearer ${getAuthToken()}`
        }
      });

      if (!response.ok) {
        throw new Error('Ошибка загрузки конфигурации');
      }

      const data = await response.json();
      setConfig(data);
      
      // Правильно устанавливаем форму с нужной структурой
      setFormData({
        log_level: data.log_level,
        log_format: data.log_format,
        log_to_file: data.log_to_file,
        log_retention_days: data.log_retention_days,
        max_log_file_size_mb: data.max_log_file_size_mb,
        telegram_notifications: {
          enabled: data.telegram_notifications.enabled,
          chat_id: data.telegram_notifications.chat_id || '',
          min_level: data.telegram_notifications.min_level,
          rate_limit_minutes: data.telegram_notifications.rate_limit_minutes
        }
      });
      
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
          'Authorization': `Bearer ${getAuthToken()}`
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
          'Authorization': `Bearer ${getAuthToken()}`
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
      // Подготавливаем данные для отправки
      const updateData = {
        log_level: formData.log_level,
        log_format: formData.log_format,
        log_to_file: formData.log_to_file,
        log_retention_days: formData.log_retention_days,
        max_log_file_size_mb: formData.max_log_file_size_mb,
        telegram_notifications: {
          enabled: formData.telegram_notifications.enabled,
          chat_id: formData.telegram_notifications.chat_id,
          min_level: formData.telegram_notifications.min_level,
          rate_limit_minutes: formData.telegram_notifications.rate_limit_minutes
        }
      };

      const response = await fetch('/api/logging/config', {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${getAuthToken()}`
        },
        body: JSON.stringify(updateData)
      });

      if (!response.ok) {
        const errorData = await response.text();
        logger.error('Server response:', errorData);
        throw new Error('Ошибка сохранения конфигурации');
      }

      const data = await response.json();
      setConfig(data);
      
      // Правильно устанавливаем форму с нужной структурой
      setFormData({
        log_level: data.log_level,
        log_format: data.log_format,
        log_to_file: data.log_to_file,
        log_retention_days: data.log_retention_days,
        max_log_file_size_mb: data.max_log_file_size_mb,
        telegram_notifications: {
          enabled: data.telegram_notifications.enabled,
          chat_id: data.telegram_notifications.chat_id || '',
          min_level: data.telegram_notifications.min_level,
          rate_limit_minutes: data.telegram_notifications.rate_limit_minutes
        }
      });

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
          'Authorization': `Bearer ${getAuthToken()}`
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
          'Authorization': `Bearer ${getAuthToken()}`
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


  const testTelegramNotification = async () => {
    // Проверяем, есть ли несохраненные изменения
    if (config && hasUnsavedChanges()) {
      toast({
        title: 'Сохраните изменения',
        description: 'Сначала сохраните текущие настройки, затем отправьте тестовое уведомление',
        status: 'warning',
        duration: 5000
      });
      return;
    }

    try {
      const response = await fetch('/api/logging/test-notification', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${getAuthToken()}`
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

  const hasUnsavedChanges = () => {
    if (!config) return false;
    
    return (
      formData.log_level !== config.log_level ||
      formData.log_format !== config.log_format ||
      formData.log_to_file !== config.log_to_file ||
      formData.log_retention_days !== config.log_retention_days ||
      formData.max_log_file_size_mb !== config.max_log_file_size_mb ||
      formData.telegram_notifications.enabled !== config.telegram_notifications.enabled ||
      formData.telegram_notifications.chat_id !== config.telegram_notifications.chat_id ||
      formData.telegram_notifications.min_level !== config.telegram_notifications.min_level ||
      formData.telegram_notifications.rate_limit_minutes !== config.telegram_notifications.rate_limit_minutes
    );
  };

  const clearLogs = async () => {
    setClearing(true);
    try {
      const response = await fetch('/api/logging/clear-logs', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${getAuthToken()}`
        }
      });

      if (!response.ok) {
        throw new Error('Ошибка очистки логов');
      }

      const data = await response.json();

      if (data.success) {
        toast({
          title: 'Успешно',
          description: `Очищено файлов: ${data.files_processed}`,
          status: 'success',
          duration: 3000
        });
        
        // Обновляем список файлов
        await loadLogFiles();
        setLogContent([]);
        setSelectedFile(null);
      } else {
        throw new Error('Не удалось очистить логи');
      }

      logger.info('Логи очищены');
    } catch (error) {
      logger.error('Ошибка очистки логов:', error);
      toast({
        title: 'Ошибка',
        description: 'Не удалось очистить логи',
        status: 'error',
        duration: 5000
      });
    } finally {
      setClearing(false);
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
    <Box p={6} bg="gray.50" minHeight="100vh">
      <VStack spacing={6} align="stretch">
        <HStack justify="space-between" align="center">
          <Heading size="lg" color="gray.800">
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
              onClick={refreshData}
              isLoading={loading}
            >
              Обновить
            </Button>
            
            <Button
              colorScheme="red"
              size="sm"
              onClick={clearLogs}
              isLoading={clearing}
              loadingText="Очистка..."
            >
              Очистить логи
            </Button>
          </HStack>
        </HStack>

        {/* Статистика логов */}
        {statistics && (
          <Card bg="white" borderColor="gray.200" boxShadow="lg">
            <CardHeader>
              <Heading size="md" color="gray.800">Статистика за 24 часа</Heading>
            </CardHeader>
            <CardBody>
              <StatGroup>
                <Stat>
                  <StatLabel color="gray.600">Всего записей</StatLabel>
                  <StatNumber color="gray.800">{statistics.total_entries}</StatNumber>
                </Stat>
                <Stat>
                  <StatLabel color="gray.600">Ошибки</StatLabel>
                  <StatNumber color="red.500">{statistics.errors_count}</StatNumber>
                  <StatHelpText color="gray.500">{statistics.error_rate}%</StatHelpText>
                </Stat>
                <Stat>
                  <StatLabel color="gray.600">Предупреждения</StatLabel>
                  <StatNumber color="orange.500">{statistics.warnings_count}</StatNumber>
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
          </TabList>

          <TabPanels>
            {/* Вкладка настроек */}
            <TabPanel>
              <VStack spacing={6} align="stretch">
                <Card bg="white" borderColor="gray.200" boxShadow="lg">
                  <CardHeader>
                    <Heading size="md" color="gray.800">Основные настройки</Heading>
                  </CardHeader>
                  <CardBody>
                    <VStack spacing={4} align="stretch">
                      <HStack spacing={4}>
                        <FormControl>
                          <FormLabel color="gray.700">Уровень логирования</FormLabel>
                          <Select
                            value={formData.log_level}
                            onChange={(e) => setFormData(prev => ({...prev, log_level: e.target.value}))}
                            bg="white"
                            borderColor="gray.300"
                            color="gray.800"
                          >
                            <option value="DEBUG">DEBUG</option>
                            <option value="INFO">INFO</option>
                            <option value="WARNING">WARNING</option>
                            <option value="ERROR">ERROR</option>
                            <option value="CRITICAL">CRITICAL</option>
                          </Select>
                        </FormControl>

                        <FormControl>
                          <FormLabel color="gray.700">Формат логов</FormLabel>
                          <Select
                            value={formData.log_format}
                            onChange={(e) => setFormData(prev => ({...prev, log_format: e.target.value}))}
                            bg="white"
                            borderColor="gray.300"
                            color="gray.800"
                          >
                            <option value="text">Текстовый</option>
                            <option value="json">JSON</option>
                          </Select>
                        </FormControl>
                      </HStack>

                      <HStack spacing={4} align="flex-end">
                        <FormControl display="flex" alignItems="center">
                          <FormLabel color="gray.700" mb="0">Запись в файл</FormLabel>
                          <Switch
                            isChecked={formData.log_to_file}
                            onChange={(e) => setFormData(prev => ({...prev, log_to_file: e.target.checked}))}
                            colorScheme="purple"
                          />
                        </FormControl>

                        <FormControl>
                          <FormLabel color="gray.700">Срок хранения (дни)</FormLabel>
                          <Input
                            type="number"
                            value={formData.log_retention_days}
                            onChange={(e) => setFormData(prev => ({...prev, log_retention_days: parseInt(e.target.value)}))}
                            bg="white"
                            borderColor="gray.300"
                            color="gray.800"
                            min="1"
                            max="365"
                          />
                        </FormControl>

                        <FormControl>
                          <FormLabel color="gray.700">Размер файла (MB)</FormLabel>
                          <Input
                            type="number"
                            value={formData.max_log_file_size_mb}
                            onChange={(e) => setFormData(prev => ({...prev, max_log_file_size_mb: parseInt(e.target.value)}))}
                            bg="white"
                            borderColor="gray.300"
                            color="gray.800"
                            min="1"
                            max="100"
                          />
                        </FormControl>
                      </HStack>
                    </VStack>
                  </CardBody>
                </Card>

                {/* Настройки Telegram уведомлений */}
                <Card bg="white" borderColor="gray.200" boxShadow="lg">
                  <CardHeader>
                    <Heading size="md" color="gray.800">Telegram уведомления</Heading>
                  </CardHeader>
                  <CardBody>
                    <VStack spacing={4} align="stretch">
                      <HStack justify="space-between">
                        <FormControl display="flex" alignItems="center">
                          <FormLabel color="gray.700" mb="0">Включить уведомления</FormLabel>
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
                            <FormLabel color="gray.700">ID чата</FormLabel>
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
                              bg="white"
                              borderColor="gray.300"
                              color="gray.800"
                            />
                          </FormControl>

                          <FormControl>
                            <FormLabel color="gray.700">Мин. уровень</FormLabel>
                            <Select
                              value={formData.telegram_notifications.min_level}
                              onChange={(e) => setFormData(prev => ({
                                ...prev,
                                telegram_notifications: {
                                  ...prev.telegram_notifications,
                                  min_level: e.target.value
                                }
                              }))}
                              bg="white"
                              borderColor="gray.300"
                              color="gray.800"
                            >
                              <option value="WARNING">WARNING</option>
                              <option value="ERROR">ERROR</option>
                              <option value="CRITICAL">CRITICAL</option>
                            </Select>
                          </FormControl>

                          <FormControl>
                            <FormLabel color="gray.700">Интервал (мин)</FormLabel>
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
                              bg="white"
                              borderColor="gray.300"
                              color="gray.800"
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
                <Card bg="white" borderColor="gray.200" boxShadow="lg">
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
                          bg="white"
                          borderColor="gray.300"
                          color="gray.800"
                        />
                      </InputGroup>

                      <Select
                        placeholder="Уровень"
                        value={levelFilter}
                        onChange={(e) => setLevelFilter(e.target.value)}
                        bg="white"
                        borderColor="gray.300"
                        color="gray.800"
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
                        bg="white"
                        borderColor="gray.300"
                        color="gray.800"
                        width="100px"
                        min="10"
                        max="10000"
                      />
                    </HStack>
                  </CardBody>
                </Card>

                {/* Список файлов логов */}
                <Card bg="white" borderColor="gray.200" boxShadow="lg">
                  <CardHeader>
                    <Heading size="md" color="gray.800">Файлы логов</Heading>
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
                            <Td color="gray.800">
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
                  <Card bg="white" borderColor="gray.200" boxShadow="lg">
                    <CardHeader>
                      <Heading size="md" color="gray.800">
                        Содержимое: {selectedFile}
                      </Heading>
                    </CardHeader>
                    <CardBody>
                      <Box
                        bg="gray.50"
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
                                  color="gray.800"
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

          </TabPanels>
        </Tabs>
      </VStack>
    </Box>
  );
};

export default Logging;