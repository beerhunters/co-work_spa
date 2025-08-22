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
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  TableContainer,
  Badge,
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
  FormControl,
  FormLabel,
  Input,
  Textarea,
  Select,
  Checkbox,
  CheckboxGroup,
  Stack,
  Divider,
  Code,
  Flex,
  IconButton,
  Menu,
  MenuButton,
  MenuList,
  MenuItem,
  Progress,
  Switch,
  Tab,
  Tabs,
  TabList,
  TabPanel,
  TabPanels,
  Accordion,
  AccordionItem,
  AccordionButton,
  AccordionPanel,
  AccordionIcon
} from '@chakra-ui/react';
import {
  FiKey,
  FiPlus,
  FiEdit3,
  FiTrash2,
  FiEye,
  FiEyeOff,
  FiCopy,
  FiActivity,
  FiShield,
  FiAlertTriangle,
  FiCheck,
  FiX,
  FiMoreVertical,
  FiBarChart,
  FiClock,
  FiUser,
  FiSettings,
  FiRefreshCw,
  FiDownload,
  FiFilter,
  FiSearch
} from 'react-icons/fi';
import { colors, sizes } from '../styles/styles';
import api from '../utils/api';

const ApiKeys = ({ currentAdmin }) => {
  const [loading, setLoading] = useState(true);
  const [apiKeys, setApiKeys] = useState([]);
  const [usageStats, setUsageStats] = useState({});
  const [auditLogs, setAuditLogs] = useState([]);
  const [selectedKey, setSelectedKey] = useState(null);
  const [activeTab, setActiveTab] = useState(0);
  const [visibleKeys, setVisibleKeys] = useState(new Set());
  const toast = useToast();
  const { isOpen, onOpen, onClose } = useDisclosure();
  const { isOpen: isDeleteOpen, onOpen: onDeleteOpen, onClose: onDeleteClose } = useDisclosure();
  const { isOpen: isUsageOpen, onOpen: onUsageOpen, onClose: onUsageClose } = useDisclosure();

  // Форма создания/редактирования API ключа
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    scopes: [],
    expiresAt: '',
    ipWhitelist: '',
    rateLimit: 1000
  });

  // Доступные области (scopes) для API ключей
  const availableScopes = [
    { id: 'users:read', name: 'Чтение пользователей', description: 'Доступ к информации о пользователях' },
    { id: 'users:write', name: 'Управление пользователями', description: 'Создание и изменение пользователей' },
    { id: 'bookings:read', name: 'Чтение бронирований', description: 'Просмотр бронирований' },
    { id: 'bookings:write', name: 'Управление бронированиями', description: 'Создание и изменение бронирований' },
    { id: 'tickets:read', name: 'Чтение заявок', description: 'Просмотр заявок поддержки' },
    { id: 'tickets:write', name: 'Управление заявками', description: 'Обработка заявок поддержки' },
    { id: 'analytics:read', name: 'Аналитика', description: 'Доступ к отчетам и статистике' },
    { id: 'admin:read', name: 'Административное чтение', description: 'Чтение административных данных' },
    { id: 'admin:write', name: 'Административное управление', description: 'Полный административный доступ' }
  ];

  useEffect(() => {
    fetchApiKeys();
    fetchUsageStats();
    fetchAuditLogs();
  }, []);

  const fetchApiKeys = async () => {
    try {
      const response = await api.get('/api-keys');
      setApiKeys(response.data.api_keys || []);
    } catch (error) {
      console.error('Ошибка загрузки API ключей:', error);
      toast({
        title: 'Ошибка загрузки',
        description: 'Не удалось загрузить API ключи',
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    } finally {
      setLoading(false);
    }
  };

  const fetchUsageStats = async () => {
    try {
      const response = await api.get('/api-keys/usage-stats');
      setUsageStats(response.data.usage_stats || {});
    } catch (error) {
      console.error('Ошибка загрузки статистики:', error);
    }
  };

  const fetchAuditLogs = async () => {
    try {
      const response = await api.get('/api-keys/audit-logs');
      setAuditLogs(response.data.audit_logs || []);
    } catch (error) {
      console.error('Ошибка загрузки логов аудита:', error);
    }
  };

  const handleCreate = async () => {
    try {
      const payload = {
        ...formData,
        expires_at: formData.expiresAt || null,
        ip_whitelist: formData.ipWhitelist ? formData.ipWhitelist.split(',').map(ip => ip.trim()) : [],
        rate_limit: parseInt(formData.rateLimit) || 1000
      };

      const response = await api.post('/api-keys', payload);
      
      toast({
        title: 'API ключ создан',
        description: 'API ключ успешно создан. Сохраните его в безопасном месте!',
        status: 'success',
        duration: 7000,
        isClosable: true,
      });

      setSelectedKey(response.data.api_key);
      fetchApiKeys();
      fetchAuditLogs();
      onClose();
      resetForm();
    } catch (error) {
      console.error('Ошибка создания API ключа:', error);
      toast({
        title: 'Ошибка создания',
        description: error.response?.data?.detail || 'Не удалось создать API ключ',
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    }
  };

  const handleUpdate = async () => {
    try {
      const payload = {
        name: formData.name,
        description: formData.description,
        scopes: formData.scopes,
        expires_at: formData.expiresAt || null,
        ip_whitelist: formData.ipWhitelist ? formData.ipWhitelist.split(',').map(ip => ip.trim()) : [],
        rate_limit: parseInt(formData.rateLimit) || 1000
      };

      await api.put(`/api-keys/${selectedKey.id}`, payload);
      
      toast({
        title: 'API ключ обновлен',
        description: 'API ключ успешно обновлен',
        status: 'success',
        duration: 3000,
        isClosable: true,
      });

      fetchApiKeys();
      fetchAuditLogs();
      onClose();
      resetForm();
    } catch (error) {
      console.error('Ошибка обновления API ключа:', error);
      toast({
        title: 'Ошибка обновления',
        description: error.response?.data?.detail || 'Не удалось обновить API ключ',
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    }
  };

  const handleDelete = async () => {
    try {
      await api.delete(`/api-keys/${selectedKey.id}`);
      
      toast({
        title: 'API ключ удален',
        description: 'API ключ успешно удален',
        status: 'success',
        duration: 3000,
        isClosable: true,
      });

      fetchApiKeys();
      fetchAuditLogs();
      onDeleteClose();
      setSelectedKey(null);
    } catch (error) {
      console.error('Ошибка удаления API ключа:', error);
      toast({
        title: 'Ошибка удаления',
        description: error.response?.data?.detail || 'Не удалось удалить API ключ',
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    }
  };

  const handleToggleStatus = async (keyId, currentStatus) => {
    try {
      await api.patch(`/api-keys/${keyId}/toggle`);
      
      toast({
        title: currentStatus ? 'API ключ деактивирован' : 'API ключ активирован',
        description: `API ключ ${currentStatus ? 'отключен' : 'включен'}`,
        status: 'success',
        duration: 3000,
        isClosable: true,
      });

      fetchApiKeys();
      fetchAuditLogs();
    } catch (error) {
      console.error('Ошибка изменения статуса:', error);
      toast({
        title: 'Ошибка',
        description: 'Не удалось изменить статус API ключа',
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    }
  };

  const resetForm = () => {
    setFormData({
      name: '',
      description: '',
      scopes: [],
      expiresAt: '',
      ipWhitelist: '',
      rateLimit: 1000
    });
  };

  const openCreateModal = () => {
    setSelectedKey(null);
    resetForm();
    onOpen();
  };

  const openEditModal = (apiKey) => {
    setSelectedKey(apiKey);
    setFormData({
      name: apiKey.name,
      description: apiKey.description || '',
      scopes: apiKey.scopes || [],
      expiresAt: apiKey.expires_at ? apiKey.expires_at.split('T')[0] : '',
      ipWhitelist: (apiKey.ip_whitelist || []).join(', '),
      rateLimit: apiKey.rate_limit || 1000
    });
    onOpen();
  };

  const openDeleteModal = (apiKey) => {
    setSelectedKey(apiKey);
    onDeleteOpen();
  };

  const openUsageModal = (apiKey) => {
    setSelectedKey(apiKey);
    onUsageOpen();
  };

  const toggleKeyVisibility = (keyId) => {
    const newVisible = new Set(visibleKeys);
    if (newVisible.has(keyId)) {
      newVisible.delete(keyId);
    } else {
      newVisible.add(keyId);
    }
    setVisibleKeys(newVisible);
  };

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
    toast({
      title: 'Скопировано',
      description: 'API ключ скопирован в буфер обмена',
      status: 'success',
      duration: 2000,
    });
  };

  const getStatusColor = (status, expiresAt) => {
    if (!status) return 'red';
    if (expiresAt && new Date(expiresAt) < new Date()) return 'orange';
    return 'green';
  };

  const getStatusText = (status, expiresAt) => {
    if (!status) return 'Неактивен';
    if (expiresAt && new Date(expiresAt) < new Date()) return 'Истек';
    return 'Активен';
  };

  const formatDate = (dateString) => {
    if (!dateString) return 'Никогда';
    return new Date(dateString).toLocaleDateString('ru-RU');
  };

  const getScopeDisplayName = (scopeId) => {
    const scope = availableScopes.find(s => s.id === scopeId);
    return scope ? scope.name : scopeId;
  };

  if (loading) {
    return (
      <Box p={6} textAlign="center">
        <Spinner size="xl" color={colors.primary} />
        <Text mt={4} color={colors.text.muted}>Загрузка API ключей...</Text>
      </Box>
    );
  }

  return (
    <Box p={6} maxW="full">
      <Flex justify="space-between" align="center" mb={6}>
        <Heading size="lg" color={colors.text.primary}>
          <Icon as={FiKey} mr={3} />
          Управление API ключами
        </Heading>
        <Button
          leftIcon={<FiPlus />}
          colorScheme="blue"
          onClick={openCreateModal}
        >
          Создать API ключ
        </Button>
      </Flex>

      <Tabs index={activeTab} onChange={setActiveTab}>
        <TabList>
          <Tab>
            <Icon as={FiKey} mr={2} />
            API ключи ({apiKeys.length})
          </Tab>
          <Tab>
            <Icon as={FiBarChart} mr={2} />
            Аналитика использования
          </Tab>
          <Tab>
            <Icon as={FiShield} mr={2} />
            Аудит безопасности
          </Tab>
        </TabList>

        <TabPanels>
          {/* Вкладка API ключей */}
          <TabPanel px={0}>
            <VStack spacing={6} align="stretch">
              {/* Статистика */}
              <SimpleGrid columns={{ base: 2, md: 4 }} spacing={4}>
                <Stat>
                  <StatLabel>Всего ключей</StatLabel>
                  <StatNumber>{apiKeys.length}</StatNumber>
                </Stat>
                
                <Stat>
                  <StatLabel>Активных</StatLabel>
                  <StatNumber color="green.500">
                    {apiKeys.filter(k => k.is_active && (!k.expires_at || new Date(k.expires_at) > new Date())).length}
                  </StatNumber>
                </Stat>
                
                <Stat>
                  <StatLabel>Истекших</StatLabel>
                  <StatNumber color="orange.500">
                    {apiKeys.filter(k => k.expires_at && new Date(k.expires_at) < new Date()).length}
                  </StatNumber>
                </Stat>
                
                <Stat>
                  <StatLabel>Запросов сегодня</StatLabel>
                  <StatNumber>{usageStats.total_requests_today || 0}</StatNumber>
                  <StatHelpText>
                    <StatArrow type={usageStats.requests_trend > 0 ? 'increase' : 'decrease'} />
                    {Math.abs(usageStats.requests_trend || 0).toFixed(1)}%
                  </StatHelpText>
                </Stat>
              </SimpleGrid>

              {/* Таблица API ключей */}
              <Card>
                <CardHeader>
                  <Flex justify="space-between" align="center">
                    <Heading size="md">API ключи</Heading>
                    <HStack>
                      <Button size="sm" leftIcon={<FiRefreshCw />} onClick={fetchApiKeys}>
                        Обновить
                      </Button>
                      <Button size="sm" leftIcon={<FiDownload />}>
                        Экспорт
                      </Button>
                    </HStack>
                  </Flex>
                </CardHeader>
                <CardBody>
                  {apiKeys.length === 0 ? (
                    <Alert status="info">
                      <AlertIcon />
                      <Box>
                        <AlertTitle>API ключи не найдены</AlertTitle>
                        <AlertDescription>
                          Создайте первый API ключ для начала работы с API
                        </AlertDescription>
                      </Box>
                    </Alert>
                  ) : (
                    <TableContainer>
                      <Table variant="simple" size="sm">
                        <Thead>
                          <Tr>
                            <Th>Название</Th>
                            <Th>Ключ</Th>
                            <Th>Статус</Th>
                            <Th>Области доступа</Th>
                            <Th>Истекает</Th>
                            <Th>Использование</Th>
                            <Th>Действия</Th>
                          </Tr>
                        </Thead>
                        <Tbody>
                          {apiKeys.map((apiKey) => (
                            <Tr key={apiKey.id}>
                              <Td>
                                <VStack align="start" spacing={1}>
                                  <Text fontWeight="medium">{apiKey.name}</Text>
                                  {apiKey.description && (
                                    <Text fontSize="xs" color={colors.text.muted}>
                                      {apiKey.description}
                                    </Text>
                                  )}
                                </VStack>
                              </Td>
                              <Td>
                                <HStack spacing={2}>
                                  <Code fontSize="xs" maxW="150px" isTruncated>
                                    {visibleKeys.has(apiKey.id) 
                                      ? apiKey.key 
                                      : apiKey.key?.replace(/./g, '*').substring(0, 20) + '...'
                                    }
                                  </Code>
                                  <IconButton
                                    size="xs"
                                    icon={visibleKeys.has(apiKey.id) ? <FiEyeOff /> : <FiEye />}
                                    onClick={() => toggleKeyVisibility(apiKey.id)}
                                  />
                                  <IconButton
                                    size="xs"
                                    icon={<FiCopy />}
                                    onClick={() => copyToClipboard(apiKey.key)}
                                  />
                                </HStack>
                              </Td>
                              <Td>
                                <Badge colorScheme={getStatusColor(apiKey.is_active, apiKey.expires_at)}>
                                  {getStatusText(apiKey.is_active, apiKey.expires_at)}
                                </Badge>
                              </Td>
                              <Td>
                                <VStack align="start" spacing={1} maxW="200px">
                                  {(apiKey.scopes || []).slice(0, 2).map(scope => (
                                    <Badge key={scope} size="sm" variant="outline">
                                      {getScopeDisplayName(scope)}
                                    </Badge>
                                  ))}
                                  {(apiKey.scopes?.length || 0) > 2 && (
                                    <Text fontSize="xs" color={colors.text.muted}>
                                      +{apiKey.scopes.length - 2} еще
                                    </Text>
                                  )}
                                </VStack>
                              </Td>
                              <Td>{formatDate(apiKey.expires_at)}</Td>
                              <Td>
                                <Tooltip label="Посмотреть детальную статистику">
                                  <Button
                                    size="xs"
                                    variant="ghost"
                                    onClick={() => openUsageModal(apiKey)}
                                  >
                                    {apiKey.request_count || 0} запросов
                                  </Button>
                                </Tooltip>
                              </Td>
                              <Td>
                                <Menu>
                                  <MenuButton as={IconButton} size="sm" icon={<FiMoreVertical />} />
                                  <MenuList>
                                    <MenuItem icon={<FiEdit3 />} onClick={() => openEditModal(apiKey)}>
                                      Редактировать
                                    </MenuItem>
                                    <MenuItem 
                                      icon={apiKey.is_active ? <FiX /> : <FiCheck />}
                                      onClick={() => handleToggleStatus(apiKey.id, apiKey.is_active)}
                                    >
                                      {apiKey.is_active ? 'Деактивировать' : 'Активировать'}
                                    </MenuItem>
                                    <MenuItem icon={<FiActivity />} onClick={() => openUsageModal(apiKey)}>
                                      Статистика
                                    </MenuItem>
                                    <Divider />
                                    <MenuItem 
                                      icon={<FiTrash2 />} 
                                      color="red.500"
                                      onClick={() => openDeleteModal(apiKey)}
                                    >
                                      Удалить
                                    </MenuItem>
                                  </MenuList>
                                </Menu>
                              </Td>
                            </Tr>
                          ))}
                        </Tbody>
                      </Table>
                    </TableContainer>
                  )}
                </CardBody>
              </Card>
            </VStack>
          </TabPanel>

          {/* Вкладка аналитики */}
          <TabPanel px={0}>
            <VStack spacing={6} align="stretch">
              <SimpleGrid columns={{ base: 1, md: 2 }} spacing={6}>
                <Card>
                  <CardHeader>
                    <Heading size="md">Использование по дням</Heading>
                  </CardHeader>
                  <CardBody>
                    <VStack spacing={4}>
                      {(usageStats.daily_usage || []).map((day, index) => (
                        <Box key={index} w="full">
                          <HStack justify="space-between" mb={1}>
                            <Text fontSize="sm">{day.date}</Text>
                            <Text fontSize="sm" fontWeight="medium">{day.requests}</Text>
                          </HStack>
                          <Progress 
                            value={day.requests} 
                            max={Math.max(...(usageStats.daily_usage || []).map(d => d.requests))}
                            colorScheme="blue"
                            size="sm"
                          />
                        </Box>
                      ))}
                    </VStack>
                  </CardBody>
                </Card>

                <Card>
                  <CardHeader>
                    <Heading size="md">Топ API ключей</Heading>
                  </CardHeader>
                  <CardBody>
                    <VStack spacing={3} align="stretch">
                      {(usageStats.top_keys || []).map((keyStats, index) => (
                        <HStack key={index} justify="space-between">
                          <VStack align="start" spacing={0}>
                            <Text fontWeight="medium">{keyStats.name}</Text>
                            <Text fontSize="xs" color={colors.text.muted}>
                              {keyStats.success_rate}% успешных запросов
                            </Text>
                          </VStack>
                          <Badge colorScheme="blue">
                            {keyStats.requests} запросов
                          </Badge>
                        </HStack>
                      ))}
                    </VStack>
                  </CardBody>
                </Card>
              </SimpleGrid>

              <Card>
                <CardHeader>
                  <Heading size="md">Статистика ошибок</Heading>
                </CardHeader>
                <CardBody>
                  <SimpleGrid columns={{ base: 2, md: 4 }} spacing={4}>
                    <Stat>
                      <StatLabel>Всего запросов</StatLabel>
                      <StatNumber>{usageStats.total_requests || 0}</StatNumber>
                    </Stat>
                    <Stat>
                      <StatLabel>Успешных</StatLabel>
                      <StatNumber color="green.500">{usageStats.successful_requests || 0}</StatNumber>
                    </Stat>
                    <Stat>
                      <StatLabel>Ошибок 4xx</StatLabel>
                      <StatNumber color="orange.500">{usageStats.client_errors || 0}</StatNumber>
                    </Stat>
                    <Stat>
                      <StatLabel>Ошибок 5xx</StatLabel>
                      <StatNumber color="red.500">{usageStats.server_errors || 0}</StatNumber>
                    </Stat>
                  </SimpleGrid>
                </CardBody>
              </Card>
            </VStack>
          </TabPanel>

          {/* Вкладка аудита */}
          <TabPanel px={0}>
            <Card>
              <CardHeader>
                <Heading size="md">Журнал аудита безопасности</Heading>
              </CardHeader>
              <CardBody>
                {auditLogs.length === 0 ? (
                  <Alert status="info">
                    <AlertIcon />
                    <AlertTitle>Нет записей аудита</AlertTitle>
                  </Alert>
                ) : (
                  <TableContainer>
                    <Table variant="simple" size="sm">
                      <Thead>
                        <Tr>
                          <Th>Время</Th>
                          <Th>Пользователь</Th>
                          <Th>Действие</Th>
                          <Th>API ключ</Th>
                          <Th>IP адрес</Th>
                          <Th>Статус</Th>
                        </Tr>
                      </Thead>
                      <Tbody>
                        {auditLogs.map((log, index) => (
                          <Tr key={index}>
                            <Td>{formatDate(log.timestamp)}</Td>
                            <Td>{log.user || 'Система'}</Td>
                            <Td>
                              <Badge
                                colorScheme={
                                  log.action.includes('create') ? 'green' :
                                  log.action.includes('delete') ? 'red' :
                                  log.action.includes('update') ? 'blue' : 'gray'
                                }
                              >
                                {log.action}
                              </Badge>
                            </Td>
                            <Td>{log.api_key_name}</Td>
                            <Td>{log.ip_address}</Td>
                            <Td>
                              <Badge colorScheme={log.success ? 'green' : 'red'}>
                                {log.success ? 'Успешно' : 'Ошибка'}
                              </Badge>
                            </Td>
                          </Tr>
                        ))}
                      </Tbody>
                    </Table>
                  </TableContainer>
                )}
              </CardBody>
            </Card>
          </TabPanel>
        </TabPanels>
      </Tabs>

      {/* Модальное окно создания/редактирования */}
      <Modal isOpen={isOpen} onClose={onClose} size="xl">
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>
            {selectedKey ? 'Редактировать API ключ' : 'Создать новый API ключ'}
          </ModalHeader>
          <ModalCloseButton />
          <ModalBody>
            <VStack spacing={4} align="stretch">
              <FormControl isRequired>
                <FormLabel>Название</FormLabel>
                <Input
                  value={formData.name}
                  onChange={(e) => setFormData(prev => ({ ...prev, name: e.target.value }))}
                  placeholder="Например: Mobile App API"
                />
              </FormControl>

              <FormControl>
                <FormLabel>Описание</FormLabel>
                <Textarea
                  value={formData.description}
                  onChange={(e) => setFormData(prev => ({ ...prev, description: e.target.value }))}
                  placeholder="Краткое описание назначения API ключа"
                  rows={3}
                />
              </FormControl>

              <FormControl isRequired>
                <FormLabel>Области доступа (Scopes)</FormLabel>
                <CheckboxGroup 
                  value={formData.scopes}
                  onChange={(values) => setFormData(prev => ({ ...prev, scopes: values }))}
                >
                  <Accordion allowMultiple>
                    <AccordionItem>
                      <AccordionButton>
                        <Box flex="1" textAlign="left">
                          Пользователи
                        </Box>
                        <AccordionIcon />
                      </AccordionButton>
                      <AccordionPanel>
                        <Stack spacing={2}>
                          {availableScopes.filter(s => s.id.startsWith('users')).map(scope => (
                            <Checkbox key={scope.id} value={scope.id}>
                              <VStack align="start" spacing={0}>
                                <Text>{scope.name}</Text>
                                <Text fontSize="xs" color={colors.text.muted}>{scope.description}</Text>
                              </VStack>
                            </Checkbox>
                          ))}
                        </Stack>
                      </AccordionPanel>
                    </AccordionItem>

                    <AccordionItem>
                      <AccordionButton>
                        <Box flex="1" textAlign="left">
                          Бронирования
                        </Box>
                        <AccordionIcon />
                      </AccordionButton>
                      <AccordionPanel>
                        <Stack spacing={2}>
                          {availableScopes.filter(s => s.id.startsWith('bookings')).map(scope => (
                            <Checkbox key={scope.id} value={scope.id}>
                              <VStack align="start" spacing={0}>
                                <Text>{scope.name}</Text>
                                <Text fontSize="xs" color={colors.text.muted}>{scope.description}</Text>
                              </VStack>
                            </Checkbox>
                          ))}
                        </Stack>
                      </AccordionPanel>
                    </AccordionItem>

                    <AccordionItem>
                      <AccordionButton>
                        <Box flex="1" textAlign="left">
                          Заявки
                        </Box>
                        <AccordionIcon />
                      </AccordionButton>
                      <AccordionPanel>
                        <Stack spacing={2}>
                          {availableScopes.filter(s => s.id.startsWith('tickets')).map(scope => (
                            <Checkbox key={scope.id} value={scope.id}>
                              <VStack align="start" spacing={0}>
                                <Text>{scope.name}</Text>
                                <Text fontSize="xs" color={colors.text.muted}>{scope.description}</Text>
                              </VStack>
                            </Checkbox>
                          ))}
                        </Stack>
                      </AccordionPanel>
                    </AccordionItem>

                    <AccordionItem>
                      <AccordionButton>
                        <Box flex="1" textAlign="left">
                          Административные
                        </Box>
                        <AccordionIcon />
                      </AccordionButton>
                      <AccordionPanel>
                        <Stack spacing={2}>
                          {availableScopes.filter(s => s.id.startsWith('admin') || s.id.startsWith('analytics')).map(scope => (
                            <Checkbox key={scope.id} value={scope.id}>
                              <VStack align="start" spacing={0}>
                                <Text>{scope.name}</Text>
                                <Text fontSize="xs" color={colors.text.muted}>{scope.description}</Text>
                              </VStack>
                            </Checkbox>
                          ))}
                        </Stack>
                      </AccordionPanel>
                    </AccordionItem>
                  </Accordion>
                </CheckboxGroup>
              </FormControl>

              <FormControl>
                <FormLabel>Дата истечения</FormLabel>
                <Input
                  type="date"
                  value={formData.expiresAt}
                  onChange={(e) => setFormData(prev => ({ ...prev, expiresAt: e.target.value }))}
                  min={new Date().toISOString().split('T')[0]}
                />
              </FormControl>

              <FormControl>
                <FormLabel>Лимит запросов в час</FormLabel>
                <Input
                  type="number"
                  value={formData.rateLimit}
                  onChange={(e) => setFormData(prev => ({ ...prev, rateLimit: e.target.value }))}
                  placeholder="1000"
                  min="1"
                  max="10000"
                />
              </FormControl>

              <FormControl>
                <FormLabel>IP whitelist (через запятую)</FormLabel>
                <Input
                  value={formData.ipWhitelist}
                  onChange={(e) => setFormData(prev => ({ ...prev, ipWhitelist: e.target.value }))}
                  placeholder="192.168.1.1, 10.0.0.1"
                />
              </FormControl>
            </VStack>
          </ModalBody>
          <ModalFooter>
            <Button variant="ghost" mr={3} onClick={onClose}>
              Отмена
            </Button>
            <Button 
              colorScheme="blue" 
              onClick={selectedKey ? handleUpdate : handleCreate}
              isDisabled={!formData.name || formData.scopes.length === 0}
            >
              {selectedKey ? 'Обновить' : 'Создать'}
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>

      {/* Модальное окно удаления */}
      <Modal isOpen={isDeleteOpen} onClose={onDeleteClose}>
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>Подтверждение удаления</ModalHeader>
          <ModalCloseButton />
          <ModalBody>
            <Alert status="warning">
              <AlertIcon />
              <Box>
                <AlertTitle>Внимание!</AlertTitle>
                <AlertDescription>
                  Вы уверены, что хотите удалить API ключ "{selectedKey?.name}"?
                  Это действие нельзя отменить. Все приложения, использующие этот ключ, перестанут работать.
                </AlertDescription>
              </Box>
            </Alert>
          </ModalBody>
          <ModalFooter>
            <Button variant="ghost" mr={3} onClick={onDeleteClose}>
              Отмена
            </Button>
            <Button colorScheme="red" onClick={handleDelete}>
              Удалить
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>

      {/* Модальное окно статистики использования */}
      <Modal isOpen={isUsageOpen} onClose={onUsageClose} size="lg">
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>Статистика использования: {selectedKey?.name}</ModalHeader>
          <ModalCloseButton />
          <ModalBody>
            <VStack spacing={4} align="stretch">
              <SimpleGrid columns={2} spacing={4}>
                <Stat>
                  <StatLabel>Всего запросов</StatLabel>
                  <StatNumber>{selectedKey?.request_count || 0}</StatNumber>
                </Stat>
                <Stat>
                  <StatLabel>Последний запрос</StatLabel>
                  <StatNumber fontSize="sm">
                    {formatDate(selectedKey?.last_used_at) || 'Никогда'}
                  </StatNumber>
                </Stat>
              </SimpleGrid>
              
              <Divider />
              
              <Box>
                <Text fontWeight="medium" mb={2}>Активность за последние 7 дней</Text>
                <VStack spacing={2}>
                  {Array.from({length: 7}, (_, i) => {
                    const date = new Date();
                    date.setDate(date.getDate() - i);
                    const requests = Math.floor(Math.random() * 100);
                    
                    return (
                      <HStack key={i} justify="space-between" w="full">
                        <Text fontSize="sm">{date.toLocaleDateString('ru-RU')}</Text>
                        <HStack>
                          <Progress value={requests} max={100} w="100px" size="sm" colorScheme="blue" />
                          <Text fontSize="sm" minW="40px">{requests}</Text>
                        </HStack>
                      </HStack>
                    );
                  })}
                </VStack>
              </Box>
            </VStack>
          </ModalBody>
          <ModalFooter>
            <Button onClick={onUsageClose}>Закрыть</Button>
          </ModalFooter>
        </ModalContent>
      </Modal>
    </Box>
  );
};

export default ApiKeys;