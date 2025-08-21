import React, { useState, useEffect, useCallback } from 'react';
import {
  Box,
  Container,
  Heading,
  VStack,
  HStack,
  Text,
  Button,
  Card,
  CardBody,
  CardHeader,
  Divider,
  Grid,
  GridItem,
  Stat,
  StatLabel,
  StatNumber,
  StatHelpText,
  Badge,
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  TableContainer,
  FormControl,
  FormLabel,
  NumberInput,
  NumberInputField,
  NumberInputStepper,
  NumberIncrementStepper,
  NumberDecrementStepper,
  Switch,
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalFooter,
  ModalBody,
  ModalCloseButton,
  useDisclosure,
  useToast,
  AlertDialog,
  AlertDialogOverlay,
  AlertDialogContent,
  AlertDialogHeader,
  AlertDialogBody,
  AlertDialogFooter,
  Spinner,
  Alert,
  AlertIcon,
  Progress,
  Tabs,
  TabList,
  TabPanels,
  Tab,
  TabPanel,
  Input,
  InputGroup,
  InputLeftElement,
  IconButton,
  Tooltip
} from '@chakra-ui/react';
import { 
  FiRefreshCw, 
  FiDownload, 
  FiUpload, 
  FiSettings, 
  FiTrash2, 
  FiPlay, 
  FiDatabase,
  FiHardDrive,
  FiClock,
  FiCheckCircle,
  FiAlertCircle,
  FiSearch
} from 'react-icons/fi';
import apiClient from '../utils/api.js';

const Backups = ({ currentAdmin }) => {
  // Состояния
  const [backupStats, setBackupStats] = useState(null);
  const [backupsList, setBackupsList] = useState([]);
  const [settings, setSettings] = useState({
    backup_enabled: true,
    backup_interval_hours: 6,
    compress_backups: true,
    keep_hourly_backups: 48,
    keep_daily_backups: 30,
    keep_weekly_backups: 12,
    keep_monthly_backups: 6,
    max_backup_size_mb: 1000
  });
  const [loading, setLoading] = useState(false);
  const [statsLoading, setStatsLoading] = useState(false);
  const [operationProgress, setOperationProgress] = useState(0);
  const [searchFilter, setSearchFilter] = useState('');

  // Модальные окна
  const { isOpen: isSettingsOpen, onOpen: onSettingsOpen, onClose: onSettingsClose } = useDisclosure();
  const { isOpen: isDeleteOpen, onOpen: onDeleteOpen, onClose: onDeleteClose } = useDisclosure();
  const [selectedBackup, setSelectedBackup] = useState(null);

  const toast = useToast();
  const cancelRef = React.useRef();

  // Загрузка статистики
  const fetchStats = useCallback(async () => {
    setStatsLoading(true);
    try {
      const response = await apiClient.get('/backups/dashboard-stats');
      setBackupStats(response.data);
    } catch (error) {
      console.error('Ошибка загрузки статистики:', error);
      toast({
        title: 'Ошибка загрузки статистики',
        description: error.response?.data?.detail || 'Не удалось загрузить данные',
        status: 'error',
        duration: 5000,
        isClosable: true
      });
    } finally {
      setStatsLoading(false);
    }
  }, [toast]);

  // Загрузка списка бэкапов
  const fetchBackups = useCallback(async () => {
    try {
      const response = await apiClient.get('/backups/list');
      setBackupsList(response.data || []);
    } catch (error) {
      console.error('Ошибка загрузки бэкапов:', error);
      toast({
        title: 'Ошибка загрузки',
        description: 'Не удалось загрузить список бэкапов',
        status: 'error',
        duration: 5000,
        isClosable: true
      });
    }
  }, [toast]);

  // Загрузка настроек
  const fetchSettings = useCallback(async () => {
    try {
      const response = await apiClient.get('/backups/settings');
      setSettings(response.data);
    } catch (error) {
      console.error('Ошибка загрузки настроек:', error);
    }
  }, []);

  // Обновление всех данных
  const refreshAllData = useCallback(async () => {
    await Promise.all([fetchStats(), fetchBackups(), fetchSettings()]);
  }, [fetchStats, fetchBackups, fetchSettings]);

  // Создание бэкапа
  const createBackup = async () => {
    setLoading(true);
    setOperationProgress(10);
    try {
      const response = await apiClient.post('/backups/create', {
        backup_type: 'manual',
        description: 'Manual backup from admin panel'
      });
      setOperationProgress(50);
      
      toast({
        title: 'Бэкап создан',
        description: `Бэкап успешно создан: ${response.data.filename}`,
        status: 'success',
        duration: 5000,
        isClosable: true
      });
      
      setOperationProgress(100);
      setTimeout(() => setOperationProgress(0), 1000);
      await refreshAllData();
    } catch (error) {
      console.error('Ошибка создания бэкапа:', error);
      toast({
        title: 'Ошибка создания бэкапа',
        description: error.response?.data?.detail || 'Не удалось создать бэкап',
        status: 'error',
        duration: 5000,
        isClosable: true
      });
      setOperationProgress(0);
    } finally {
      setLoading(false);
    }
  };

  // Восстановление бэкапа
  const restoreBackup = async (filename) => {
    setLoading(true);
    setOperationProgress(10);
    try {
      await apiClient.post(`/backups/restore`, {
        backup_filename: filename,
        confirm_restore: true
      });
      setOperationProgress(100);
      
      toast({
        title: 'Бэкап восстановлен',
        description: 'База данных успешно восстановлена из бэкапа',
        status: 'success',
        duration: 5000,
        isClosable: true
      });
      
      setTimeout(() => setOperationProgress(0), 1000);
      await refreshAllData();
    } catch (error) {
      console.error('Ошибка восстановления:', error);
      toast({
        title: 'Ошибка восстановления',
        description: error.response?.data?.detail || 'Не удалось восстановить бэкап',
        status: 'error',
        duration: 5000,
        isClosable: true
      });
      setOperationProgress(0);
    } finally {
      setLoading(false);
    }
  };

  // Удаление бэкапа
  const deleteBackup = async () => {
    if (!selectedBackup) return;
    
    setLoading(true);
    try {
      await apiClient.delete(`/backups/${selectedBackup.filename}`);
      
      toast({
        title: 'Бэкап удален',
        description: `Бэкап ${selectedBackup.filename} успешно удален`,
        status: 'success',
        duration: 3000,
        isClosable: true
      });
      
      await refreshAllData();
    } catch (error) {
      console.error('Ошибка удаления:', error);
      toast({
        title: 'Ошибка удаления',
        description: error.response?.data?.detail || 'Не удалось удалить бэкап',
        status: 'error',
        duration: 5000,
        isClosable: true
      });
    } finally {
      setLoading(false);
      onDeleteClose();
      setSelectedBackup(null);
    }
  };

  // Очистка старых бэкапов
  const cleanupBackups = async () => {
    setLoading(true);
    setOperationProgress(20);
    try {
      const response = await apiClient.post('/backups/cleanup');
      setOperationProgress(100);
      
      toast({
        title: 'Очистка завершена',
        description: `Удалено ${response.data.deleted_count || 0} старых бэкапов`,
        status: 'success',
        duration: 5000,
        isClosable: true
      });
      
      setTimeout(() => setOperationProgress(0), 1000);
      await refreshAllData();
    } catch (error) {
      console.error('Ошибка очистки:', error);
      toast({
        title: 'Ошибка очистки',
        description: error.response?.data?.detail || 'Не удалось выполнить очистку',
        status: 'error',
        duration: 5000,
        isClosable: true
      });
      setOperationProgress(0);
    } finally {
      setLoading(false);
    }
  };

  // Тестирование бэкапа
  const testRestore = async (filename) => {
    setLoading(true);
    setOperationProgress(25);
    try {
      await apiClient.post('/backups/test-restore', { 
        backup_filename: filename,
        confirm_restore: false
      });
      setOperationProgress(100);
      
      toast({
        title: 'Тест пройден',
        description: `Бэкап ${filename} прошел проверку целостности`,
        status: 'success',
        duration: 5000,
        isClosable: true
      });
      
      setTimeout(() => setOperationProgress(0), 1000);
    } catch (error) {
      console.error('Ошибка тестирования:', error);
      toast({
        title: 'Тест не пройден',
        description: error.response?.data?.detail || 'Бэкап поврежден или недоступен',
        status: 'error',
        duration: 5000,
        isClosable: true
      });
      setOperationProgress(0);
    } finally {
      setLoading(false);
    }
  };

  // Сохранение настроек
  const saveSettings = async () => {
    setLoading(true);
    try {
      await apiClient.put('/backups/settings', settings);
      
      toast({
        title: 'Настройки сохранены',
        description: 'Конфигурация бэкапов обновлена',
        status: 'success',
        duration: 3000,
        isClosable: true
      });
      
      onSettingsClose();
      await refreshAllData();
    } catch (error) {
      console.error('Ошибка сохранения настроек:', error);
      toast({
        title: 'Ошибка сохранения',
        description: error.response?.data?.detail || 'Не удалось сохранить настройки',
        status: 'error',
        duration: 5000,
        isClosable: true
      });
    } finally {
      setLoading(false);
    }
  };

  // Форматирование размера файла
  const formatFileSize = (bytes) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  // Форматирование даты с учетом московского времени (+3 часа)
  const formatDate = (dateString) => {
    const date = new Date(dateString);
    // Добавляем 3 часа для московского времени
    date.setHours(date.getHours() + 3);
    return date.toLocaleString('ru-RU', {
      year: 'numeric',
      month: '2-digit', 
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    });
  };

  // Фильтрация бэкапов
  const filteredBackups = (Array.isArray(backupsList) ? backupsList : []).filter(backup =>
    backup.filename.toLowerCase().includes(searchFilter.toLowerCase())
  );

  // Инициализация
  useEffect(() => {
    refreshAllData();
    
    // Автообновление каждые 30 секунд
    const interval = setInterval(fetchStats, 30000);
    return () => clearInterval(interval);
  }, [refreshAllData, fetchStats]);

  // Проверка прав доступа
  if (currentAdmin?.role !== 'super_admin') {
    return (
      <Container maxW="container.xl" py={8}>
        <Alert status="error">
          <AlertIcon />
          Доступ запрещен. Только главный администратор может управлять бэкапами.
        </Alert>
      </Container>
    );
  }

  return (
    <Container maxW="container.xl" py={8}>
      <VStack spacing={6} align="stretch">
        {/* Заголовок и действия */}
        <Box>
          <HStack justify="space-between" align="center" mb={4}>
            <Heading size="lg">Управление бэкапами</Heading>
            <HStack>
              <Button
                leftIcon={<FiRefreshCw />}
                onClick={refreshAllData}
                isLoading={statsLoading}
                variant="ghost"
              >
                Обновить
              </Button>
              <Button
                leftIcon={<FiSettings />}
                onClick={onSettingsOpen}
                variant="outline"
              >
                Настройки
              </Button>
              <Button
                leftIcon={<FiDatabase />}
                onClick={createBackup}
                colorScheme="blue"
                isLoading={loading}
              >
                Создать бэкап
              </Button>
            </HStack>
          </HStack>

          {/* Прогресс операции */}
          {operationProgress > 0 && (
            <Box mb={4}>
              <Text fontSize="sm" mb={2}>Выполнение операции...</Text>
              <Progress value={operationProgress} colorScheme="blue" hasStripe isAnimated />
            </Box>
          )}
        </Box>

        {/* Статистика */}
        {backupStats && (
          <Grid templateColumns="repeat(auto-fit, minmax(250px, 1fr))" gap={6}>
            <Card>
              <CardBody>
                <Stat>
                  <StatLabel>Всего бэкапов</StatLabel>
                  <StatNumber>{backupStats.total_backups}</StatNumber>
                  <StatHelpText>
                    <HStack>
                      <FiHardDrive />
                      <Text>{formatFileSize((backupStats.total_size_mb || 0) * 1024 * 1024)}</Text>
                    </HStack>
                  </StatHelpText>
                </Stat>
              </CardBody>
            </Card>

            <Card>
              <CardBody>
                <Stat>
                  <StatLabel>Последний бэкап</StatLabel>
                  <StatNumber fontSize="lg">
                    {backupStats.last_backup?.created_at ? 
                      formatDate(backupStats.last_backup.created_at) : 'Нет данных'
                    }
                  </StatNumber>
                  <StatHelpText>
                    <HStack>
                      <FiClock />
                      <Text>
                        {backupStats.enabled ? 
                          'Автобэкапы включены' : 'Отключено'
                        }
                      </Text>
                    </HStack>
                  </StatHelpText>
                </Stat>
              </CardBody>
            </Card>

            <Card>
              <CardBody>
                <Stat>
                  <StatLabel>Статус системы</StatLabel>
                  <StatNumber>
                    <Badge 
                      colorScheme={backupStats.enabled ? 'green' : 'red'}
                      fontSize="sm"
                    >
                      {backupStats.enabled ? 'Активна' : 'Отключена'}
                    </Badge>
                  </StatNumber>
                  <StatHelpText>
                    <HStack>
                      {backupStats.enabled ? <FiCheckCircle /> : <FiAlertCircle />}
                      <Text>
                        {backupStats.scheduler_running ? 'Планировщик работает' : 'Планировщик остановлен'}
                      </Text>
                    </HStack>
                  </StatHelpText>
                </Stat>
              </CardBody>
            </Card>
          </Grid>
        )}

        {/* Управление бэкапами */}
        <Tabs>
          <TabList>
            <Tab>Список бэкапов</Tab>
            <Tab>Действия</Tab>
          </TabList>

          <TabPanels>
            {/* Список бэкапов */}
            <TabPanel>
              <VStack align="stretch" spacing={4}>
                {/* Поиск */}
                <HStack>
                  <InputGroup maxW="400px">
                    <InputLeftElement>
                      <FiSearch />
                    </InputLeftElement>
                    <Input
                      placeholder="Поиск по названию бэкапа..."
                      value={searchFilter}
                      onChange={(e) => setSearchFilter(e.target.value)}
                    />
                  </InputGroup>
                </HStack>

                {/* Таблица бэкапов */}
                <Card>
                  <CardBody p={0}>
                    <TableContainer>
                      <Table variant="simple">
                        <Thead>
                          <Tr>
                            <Th>Название файла</Th>
                            <Th>Дата создания</Th>
                            <Th>Размер</Th>
                            <Th>Тип</Th>
                            <Th>Действия</Th>
                          </Tr>
                        </Thead>
                        <Tbody>
                          {filteredBackups.map((backup) => (
                            <Tr key={backup.filename}>
                              <Td>{backup.filename}</Td>
                              <Td>{formatDate(backup.created_at)}</Td>
                              <Td>{formatFileSize(backup.size_bytes || 0)}</Td>
                              <Td>
                                <Badge colorScheme="blue">
                                  {backup.compressed ? 'Сжатый' : 'Обычный'}
                                </Badge>
                              </Td>
                              <Td>
                                <HStack spacing={2}>
                                  <Tooltip label="Скачать">
                                    <IconButton
                                      icon={<FiDownload />}
                                      size="sm"
                                      variant="ghost"
                                      as="a"
                                      href={`/api/backups/download/${backup.filename}`}
                                      download
                                    />
                                  </Tooltip>
                                  
                                  <Tooltip label="Восстановить">
                                    <IconButton
                                      icon={<FiUpload />}
                                      size="sm"
                                      variant="ghost"
                                      onClick={() => restoreBackup(backup.filename)}
                                      isLoading={loading}
                                      colorScheme="green"
                                    />
                                  </Tooltip>
                                  
                                  <Tooltip label="Тестировать">
                                    <IconButton
                                      icon={<FiPlay />}
                                      size="sm"
                                      variant="ghost"
                                      onClick={() => testRestore(backup.filename)}
                                      isLoading={loading}
                                      colorScheme="orange"
                                    />
                                  </Tooltip>
                                  
                                  <Tooltip label="Удалить">
                                    <IconButton
                                      icon={<FiTrash2 />}
                                      size="sm"
                                      variant="ghost"
                                      onClick={() => {
                                        setSelectedBackup(backup);
                                        onDeleteOpen();
                                      }}
                                      colorScheme="red"
                                    />
                                  </Tooltip>
                                </HStack>
                              </Td>
                            </Tr>
                          ))}
                        </Tbody>
                      </Table>
                    </TableContainer>
                    
                    {filteredBackups.length === 0 && (
                      <Box p={8} textAlign="center">
                        <Text color="gray.500">
                          {searchFilter ? 'Бэкапы не найдены' : 'Нет доступных бэкапов'}
                        </Text>
                      </Box>
                    )}
                  </CardBody>
                </Card>
              </VStack>
            </TabPanel>

            {/* Действия */}
            <TabPanel>
              <Grid templateColumns="repeat(auto-fit, minmax(300px, 1fr))" gap={6}>
                <Card>
                  <CardHeader>
                    <Heading size="md">Управление</Heading>
                  </CardHeader>
                  <CardBody>
                    <VStack spacing={4} align="stretch">
                      <Button
                        leftIcon={<FiDatabase />}
                        onClick={createBackup}
                        isLoading={loading}
                        colorScheme="blue"
                        size="lg"
                      >
                        Создать бэкап сейчас
                      </Button>
                      
                      <Button
                        leftIcon={<FiTrash2 />}
                        onClick={cleanupBackups}
                        isLoading={loading}
                        colorScheme="orange"
                        variant="outline"
                      >
                        Очистить старые бэкапы
                      </Button>
                      
                      <Button
                        leftIcon={<FiSettings />}
                        onClick={onSettingsOpen}
                        variant="outline"
                      >
                        Настроить автобэкапы
                      </Button>
                    </VStack>
                  </CardBody>
                </Card>

                <Card>
                  <CardHeader>
                    <Heading size="md">Информация</Heading>
                  </CardHeader>
                  <CardBody>
                    <VStack spacing={3} align="stretch">
                      <Text fontSize="sm">
                        <strong>Автоматические бэкапы:</strong> {' '}
                        {backupStats?.enabled ? 'Включены' : 'Выключены'}
                      </Text>
                      
                      <Text fontSize="sm">
                        <strong>Планировщик:</strong> {' '}
                        {backupStats?.scheduler_running ? 'Работает' : 'Остановлен'}
                      </Text>
                      
                      <Text fontSize="sm">
                        <strong>Статус:</strong> {' '}
                        <Badge 
                          colorScheme={backupStats?.health_status === 'healthy' ? 'green' : 'red'}
                          fontSize="xs"
                        >
                          {backupStats?.health_status || 'unknown'}
                        </Badge>
                      </Text>
                      
                      <Divider />
                      
                      <Text fontSize="sm">
                        <strong>Политика хранения:</strong>
                      </Text>
                      <VStack spacing={1} align="stretch" pl={4} fontSize="xs">
                        <Text>• Почасовые: {backupStats?.retention_policy?.hourly || 48}</Text>
                        <Text>• Дневные: {backupStats?.retention_policy?.daily || 30}</Text>
                        <Text>• Недельные: {backupStats?.retention_policy?.weekly || 12}</Text>
                        <Text>• Месячные: {backupStats?.retention_policy?.monthly || 6}</Text>
                      </VStack>
                    </VStack>
                  </CardBody>
                </Card>
              </Grid>
            </TabPanel>
          </TabPanels>
        </Tabs>

        {/* Модальное окно настроек */}
        <Modal isOpen={isSettingsOpen} onClose={onSettingsClose} size="lg">
          <ModalOverlay />
          <ModalContent>
            <ModalHeader>Настройки бэкапов</ModalHeader>
            <ModalCloseButton />
            <ModalBody>
              <VStack spacing={6} align="stretch">
                {/* Основные настройки */}
                <Box>
                  <Heading size="sm" mb={4}>Основные настройки</Heading>
                  <VStack spacing={4} align="stretch">
                    <FormControl display="flex" alignItems="center">
                      <FormLabel htmlFor="backup-enabled" mb="0">
                        Автоматические бэкапы
                      </FormLabel>
                      <Switch
                        id="backup-enabled"
                        isChecked={settings.backup_enabled}
                        onChange={(e) => setSettings({...settings, backup_enabled: e.target.checked})}
                      />
                    </FormControl>

                    <FormControl>
                      <FormLabel>Интервал бэкапов (часы)</FormLabel>
                      <NumberInput
                        value={settings.backup_interval_hours}
                        onChange={(val) => setSettings({...settings, backup_interval_hours: parseInt(val)})}
                        min={1}
                        max={168}
                      >
                        <NumberInputField />
                        <NumberInputStepper>
                          <NumberIncrementStepper />
                          <NumberDecrementStepper />
                        </NumberInputStepper>
                      </NumberInput>
                    </FormControl>

                    <FormControl display="flex" alignItems="center">
                      <FormLabel htmlFor="compress-backups" mb="0">
                        Сжимать бэкапы
                      </FormLabel>
                      <Switch
                        id="compress-backups"
                        isChecked={settings.compress_backups}
                        onChange={(e) => setSettings({...settings, compress_backups: e.target.checked})}
                      />
                    </FormControl>

                    <FormControl>
                      <FormLabel>Максимальный размер бэкапа (МБ)</FormLabel>
                      <NumberInput
                        value={settings.max_backup_size_mb}
                        onChange={(val) => setSettings({...settings, max_backup_size_mb: parseInt(val)})}
                        min={100}
                        max={10000}
                      >
                        <NumberInputField />
                        <NumberInputStepper>
                          <NumberIncrementStepper />
                          <NumberDecrementStepper />
                        </NumberInputStepper>
                      </NumberInput>
                    </FormControl>
                  </VStack>
                </Box>

                <Divider />

                {/* Политика хранения */}
                <Box>
                  <Heading size="sm" mb={4}>Политика хранения</Heading>
                  <Grid templateColumns="repeat(2, 1fr)" gap={4}>
                    <FormControl>
                      <FormLabel>Почасовые бэкапы</FormLabel>
                      <NumberInput
                        value={settings.keep_hourly_backups}
                        onChange={(val) => setSettings({...settings, keep_hourly_backups: parseInt(val)})}
                        min={0}
                        max={168}
                      >
                        <NumberInputField />
                        <NumberInputStepper>
                          <NumberIncrementStepper />
                          <NumberDecrementStepper />
                        </NumberInputStepper>
                      </NumberInput>
                    </FormControl>

                    <FormControl>
                      <FormLabel>Дневные бэкапы</FormLabel>
                      <NumberInput
                        value={settings.keep_daily_backups}
                        onChange={(val) => setSettings({...settings, keep_daily_backups: parseInt(val)})}
                        min={0}
                        max={365}
                      >
                        <NumberInputField />
                        <NumberInputStepper>
                          <NumberIncrementStepper />
                          <NumberDecrementStepper />
                        </NumberInputStepper>
                      </NumberInput>
                    </FormControl>

                    <FormControl>
                      <FormLabel>Недельные бэкапы</FormLabel>
                      <NumberInput
                        value={settings.keep_weekly_backups}
                        onChange={(val) => setSettings({...settings, keep_weekly_backups: parseInt(val)})}
                        min={0}
                        max={52}
                      >
                        <NumberInputField />
                        <NumberInputStepper>
                          <NumberIncrementStepper />
                          <NumberDecrementStepper />
                        </NumberInputStepper>
                      </NumberInput>
                    </FormControl>

                    <FormControl>
                      <FormLabel>Месячные бэкапы</FormLabel>
                      <NumberInput
                        value={settings.keep_monthly_backups}
                        onChange={(val) => setSettings({...settings, keep_monthly_backups: parseInt(val)})}
                        min={0}
                        max={120}
                      >
                        <NumberInputField />
                        <NumberInputStepper>
                          <NumberIncrementStepper />
                          <NumberDecrementStepper />
                        </NumberInputStepper>
                      </NumberInput>
                    </FormControl>
                  </Grid>
                </Box>
              </VStack>
            </ModalBody>
            <ModalFooter>
              <Button variant="ghost" mr={3} onClick={onSettingsClose}>
                Отмена
              </Button>
              <Button colorScheme="blue" onClick={saveSettings} isLoading={loading}>
                Сохранить
              </Button>
            </ModalFooter>
          </ModalContent>
        </Modal>

        {/* Диалог подтверждения удаления */}
        <AlertDialog
          isOpen={isDeleteOpen}
          leastDestructiveRef={cancelRef}
          onClose={onDeleteClose}
        >
          <AlertDialogOverlay>
            <AlertDialogContent>
              <AlertDialogHeader fontSize="lg" fontWeight="bold">
                Удалить бэкап
              </AlertDialogHeader>

              <AlertDialogBody>
                Вы действительно хотите удалить бэкап{' '}
                <strong>{selectedBackup?.filename}</strong>?{' '}
                Это действие нельзя будет отменить.
              </AlertDialogBody>

              <AlertDialogFooter>
                <Button ref={cancelRef} onClick={onDeleteClose}>
                  Отмена
                </Button>
                <Button colorScheme="red" onClick={deleteBackup} ml={3} isLoading={loading}>
                  Удалить
                </Button>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialogOverlay>
        </AlertDialog>
      </VStack>
    </Container>
  );
};

export default Backups;