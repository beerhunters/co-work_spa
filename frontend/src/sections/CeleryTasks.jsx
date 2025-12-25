import React, { useState, useEffect } from 'react';
import {
  Box,
  VStack,
  HStack,
  Card,
  CardHeader,
  CardBody,
  Heading,
  Text,
  Badge,
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  Button,
  useToast,
  Spinner,
  Alert,
  AlertIcon,
  AlertTitle,
  AlertDescription,
  Tabs,
  TabList,
  TabPanels,
  Tab,
  TabPanel,
  IconButton,
  Tooltip,
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalFooter,
  ModalBody,
  ModalCloseButton,
  useDisclosure,
  Code,
  Flex,
  Spacer,
  Select,
  Stat,
  StatLabel,
  StatNumber,
  StatHelpText,
  Grid,
  GridItem,
} from '@chakra-ui/react';
import {
  FiRefreshCw,
  FiClock,
  FiCheckCircle,
  FiXCircle,
  FiAlertCircle,
  FiInfo,
  FiTrash2,
  FiActivity,
  FiServer,
} from 'react-icons/fi';
import { colors, sizes, styles } from '../styles/styles';
import { createLogger } from '../utils/logger';
import api from '../utils/api';

const logger = createLogger('CeleryTasks');

// Маппинг статусов на цвета
const getStatusColor = (status) => {
  switch (status?.toUpperCase()) {
    case 'ACTIVE':
      return 'green';
    case 'SCHEDULED':
      return 'blue';
    case 'RESERVED':
      return 'cyan';
    case 'REVOKED':
      return 'red';
    case 'PENDING':
      return 'yellow';
    case 'SUCCESS':
      return 'green';
    case 'FAILURE':
      return 'red';
    default:
      return 'gray';
  }
};

// Иконки для статусов
const getStatusIcon = (status) => {
  switch (status?.toUpperCase()) {
    case 'ACTIVE':
      return FiActivity;
    case 'SCHEDULED':
      return FiClock;
    case 'REVOKED':
      return FiXCircle;
    case 'SUCCESS':
      return FiCheckCircle;
    case 'FAILURE':
      return FiAlertCircle;
    default:
      return FiInfo;
  }
};

// Форматирование даты
const formatDateTime = (isoString) => {
  if (!isoString) return 'N/A';
  try {
    const date = new Date(isoString);
    return date.toLocaleString('ru-RU', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  } catch (e) {
    return isoString;
  }
};

// Форматирование имени задачи с описанием на русском
const formatTaskName = (name, taskType) => {
  // Если есть информация о типе задачи бронирования - используем её
  if (taskType) {
    const typeNames = {
      'expiration_notification': 'Уведомление о завершении бронирования',
      'rental_reminder': 'Напоминание об окончании аренды',
    };
    return typeNames[taskType] || taskType;
  }

  // Иначе форматируем имя задачи
  if (!name || name === 'Unknown') return 'Системная задача';

  // Убираем prefixes типа "tasks.booking_tasks."
  const parts = name.split('.');
  const shortName = parts[parts.length - 1];

  // Переводим распространенные названия на русский
  const nameTranslations = {
    'send_booking_expiration_notification': 'Уведомление о завершении',
    'send_rental_reminder': 'Напоминание об аренде',
    'send_booking_reminder': 'Напоминание о бронировании',
    'cleanup_expired_bookings': 'Очистка истекших бронирований',
  };

  return nameTranslations[shortName] || shortName;
};

const CeleryTasks = () => {
  const [tasks, setTasks] = useState({
    active: [],
    scheduled: [],
    reserved: [],
    revoked: [],
    total: 0,
  });
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(false);
  const [selectedTask, setSelectedTask] = useState(null);
  const { isOpen, onOpen, onClose } = useDisclosure();
  const toast = useToast();

  // Загрузка задач
  const fetchTasks = async () => {
    try {
      setLoading(true);
      const response = await api.get('/celery-tasks/list');
      setTasks(response.data);
      logger.debug('Загружено задач:', response.data.total);
    } catch (error) {
      logger.error('Ошибка загрузки задач:', error);
      toast({
        title: 'Ошибка загрузки задач',
        description: error.response?.data?.detail || error.message,
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    } finally {
      setLoading(false);
    }
  };

  // Загрузка статистики workers
  const fetchStats = async () => {
    try {
      const response = await api.get('/celery-tasks/stats');
      setStats(response.data);
      logger.debug('Загружена статистика workers:', response.data.total_workers);
    } catch (error) {
      logger.error('Ошибка загрузки статистики:', error);
    }
  };

  // Получение детальной информации о задаче
  const fetchTaskDetails = async (taskId) => {
    try {
      const response = await api.get(`/celery-tasks/task/${taskId}`);
      setSelectedTask(response.data);
      onOpen();
    } catch (error) {
      logger.error('Ошибка загрузки деталей задачи:', error);
      toast({
        title: 'Ошибка',
        description: 'Не удалось загрузить детали задачи',
        status: 'error',
        duration: 3000,
      });
    }
  };

  // Отмена задачи
  const revokeTask = async (taskId, terminate = false) => {
    try {
      const response = await api.post(`/celery-tasks/revoke/${taskId}`, null, {
        params: { terminate },
      });

      if (response.data.success) {
        toast({
          title: 'Задача отменена',
          description: `Задача ${taskId} успешно отменена`,
          status: 'success',
          duration: 3000,
        });
        fetchTasks(); // Перезагружаем список
        onClose(); // Закрываем модальное окно
      } else {
        toast({
          title: 'Не удалось отменить',
          description: response.data.message,
          status: 'warning',
          duration: 3000,
        });
      }
    } catch (error) {
      logger.error('Ошибка отмены задачи:', error);
      toast({
        title: 'Ошибка отмены задачи',
        description: error.response?.data?.detail || error.message,
        status: 'error',
        duration: 5000,
      });
    }
  };

  // Массовая отмена всех задач
  const handleRevokeAll = async () => {
    // Подтверждение от пользователя
    const confirmed = window.confirm(
      '⚠️ Вы уверены, что хотите ПОЛНОСТЬЮ УДАЛИТЬ ВСЕ задачи?\n\n' +
      'Это действие:\n' +
      '• ПОЛНОСТЬЮ удалит все задачи из очередей Celery (НАВСЕГДА)\n' +
      '• Отменит активные задачи\n' +
      '• Очистит task_id в таблице бронирований\n' +
      '• Отправит уведомление администратору\n\n' +
      'ВНИМАНИЕ: Это необратимая операция!\n\n' +
      'Продолжить?'
    );

    if (!confirmed) return;

    try {
      const response = await api.post('/celery-tasks/revoke-all');

      if (response.data.success) {
        const totalRemoved = response.data.total_removed || 0;
        const bookingsCleared = response.data.bookings_cleared || 0;

        toast({
          title: 'Все задачи удалены',
          description: `Полностью удалено: ${totalRemoved} задач, очищено бронирований: ${bookingsCleared}`,
          status: 'success',
          duration: 5000,
        });
        fetchTasks(); // Перезагружаем список
        fetchStats(); // Обновляем статистику
      }
    } catch (error) {
      logger.error('Ошибка массовой отмены задач:', error);
      toast({
        title: 'Ошибка массовой отмены',
        description: error.response?.data?.detail || error.message,
        status: 'error',
        duration: 5000,
      });
    }
  };

  // Загрузка данных при монтировании компонента
  useEffect(() => {
    fetchTasks();
    fetchStats();
  }, []);

  // Компонент таблицы задач
  const TasksTable = ({ tasksList, status }) => (
    <Table variant="simple" size="sm">
      <Thead>
        <Tr>
          <Th>Task ID</Th>
          <Th>Название</Th>
          <Th>Статус</Th>
          <Th>Бронирование</Th>
          <Th>ETA</Th>
          <Th>Действия</Th>
        </Tr>
      </Thead>
      <Tbody>
        {tasksList.length === 0 ? (
          <Tr>
            <Td colSpan={6} textAlign="center">
              <Text color="gray.500">Нет задач</Text>
            </Td>
          </Tr>
        ) : (
          tasksList.map((task, index) => (
            <Tr key={task.task_id || index}>
              <Td>
                <Tooltip label={task.task_id}>
                  <Code fontSize="xs">{task.task_id?.slice(0, 8)}...</Code>
                </Tooltip>
              </Td>
              <Td>
                <VStack align="start" spacing={0}>
                  <Text fontSize="sm" fontWeight="medium">
                    {formatTaskName(task.name, task.booking_task_type)}
                  </Text>
                  {task.name && task.name !== 'Unknown' && (
                    <Text fontSize="xs" color="gray.500">
                      {task.name.split('.').pop()}
                    </Text>
                  )}
                </VStack>
              </Td>
              <Td>
                <Badge colorScheme={getStatusColor(status)} fontSize="xs">
                  {status === 'ACTIVE' ? 'Активна' :
                   status === 'SCHEDULED' ? 'Запланирована' :
                   status === 'RESERVED' ? 'Зарезервирована' :
                   status === 'REVOKED' ? 'Отменена' : status}
                </Badge>
              </Td>
              <Td>
                {task.booking_id ? (
                  <VStack align="start" spacing={0}>
                    <Text fontSize="xs" fontWeight="medium">Бронирование #{task.booking_id}</Text>
                    {task.booking_visit_date && (
                      <Text fontSize="xs" color="gray.600">
                        📅 {task.booking_visit_date}
                      </Text>
                    )}
                    {task.booking_user_id && (
                      <Text fontSize="xs" color="gray.500">
                        Пользователь ID: {task.booking_user_id}
                      </Text>
                    )}
                  </VStack>
                ) : (
                  <Text color="gray.400" fontSize="xs">Нет привязки</Text>
                )}
              </Td>
              <Td>
                <Text fontSize="xs">
                  {task.eta ? formatDateTime(task.eta) : '-'}
                </Text>
              </Td>
              <Td>
                <HStack spacing={2}>
                  <Tooltip label="Детали">
                    <IconButton
                      size="xs"
                      icon={<FiInfo />}
                      onClick={() => fetchTaskDetails(task.task_id)}
                    />
                  </Tooltip>
                  <Tooltip label="Отменить задачу">
                    <IconButton
                      size="xs"
                      colorScheme="red"
                      icon={<FiTrash2 />}
                      onClick={() => revokeTask(task.task_id)}
                    />
                  </Tooltip>
                </HStack>
              </Td>
            </Tr>
          ))
        )}
      </Tbody>
    </Table>
  );

  return (
    <Box p={6}>
      <VStack spacing={6} align="stretch">
        {/* Заголовок и управление */}
        <Card>
          <CardHeader>
            <Flex align="center">
              <Heading size="lg">Мониторинг Celery задач</Heading>
              <Spacer />
              <HStack spacing={3}>
                <Button
                  leftIcon={<FiRefreshCw />}
                  onClick={() => {
                    fetchTasks();
                    fetchStats();
                  }}
                  isLoading={loading}
                  colorScheme="blue"
                  size="sm"
                >
                  Обновить
                </Button>
                <Button
                  leftIcon={<FiTrash2 />}
                  onClick={handleRevokeAll}
                  colorScheme="red"
                  size="sm"
                  isDisabled={loading}
                >
                  Удалить все задачи
                </Button>
              </HStack>
            </Flex>
          </CardHeader>
        </Card>

        {/* Статистика */}
        {stats && (
          <Grid templateColumns="repeat(auto-fit, minmax(200px, 1fr))" gap={4}>
            <Card>
              <CardBody>
                <Stat>
                  <StatLabel>Всего задач</StatLabel>
                  <StatNumber>
                    {(tasks.active?.length || 0) + (tasks.scheduled?.length || 0) + (tasks.reserved?.length || 0)}
                  </StatNumber>
                  <StatHelpText>Активные + Запланированные + Зарезервированные</StatHelpText>
                </Stat>
              </CardBody>
            </Card>
            <Card>
              <CardBody>
                <Stat>
                  <StatLabel>Workers</StatLabel>
                  <StatNumber>{stats.total_workers}</StatNumber>
                  <StatHelpText>
                    <Badge colorScheme="green">Online</Badge>
                  </StatHelpText>
                </Stat>
              </CardBody>
            </Card>
            <Card>
              <CardBody>
                <Stat>
                  <StatLabel>Активные</StatLabel>
                  <StatNumber>{tasks.active?.length || 0}</StatNumber>
                  <StatHelpText>Выполняются сейчас</StatHelpText>
                </Stat>
              </CardBody>
            </Card>
            <Card>
              <CardBody>
                <Stat>
                  <StatLabel>Запланированные</StatLabel>
                  <StatNumber>{tasks.scheduled?.length || 0}</StatNumber>
                  <StatHelpText>Будут выполнены позже</StatHelpText>
                </Stat>
              </CardBody>
            </Card>
          </Grid>
        )}

        {/* Табы с задачами */}
        <Card>
          <CardBody>
            <Tabs colorScheme="blue">
              <TabList>
                <Tab>
                  Запланированные{' '}
                  <Badge ml={2} colorScheme="blue">
                    {tasks.scheduled?.length || 0}
                  </Badge>
                </Tab>
                <Tab>
                  Активные{' '}
                  <Badge ml={2} colorScheme="green">
                    {tasks.active?.length || 0}
                  </Badge>
                </Tab>
                <Tab>
                  Зарезервированные{' '}
                  <Badge ml={2} colorScheme="cyan">
                    {tasks.reserved?.length || 0}
                  </Badge>
                </Tab>
                <Tab>
                  Отмененные{' '}
                  <Badge ml={2} colorScheme="red">
                    {tasks.revoked?.length || 0}
                  </Badge>
                </Tab>
              </TabList>

              <TabPanels>
                <TabPanel>
                  {loading ? (
                    <Flex justify="center" py={8}>
                      <Spinner />
                    </Flex>
                  ) : (
                    <TasksTable tasksList={tasks.scheduled || []} status="SCHEDULED" />
                  )}
                </TabPanel>
                <TabPanel>
                  {loading ? (
                    <Flex justify="center" py={8}>
                      <Spinner />
                    </Flex>
                  ) : (
                    <TasksTable tasksList={tasks.active || []} status="ACTIVE" />
                  )}
                </TabPanel>
                <TabPanel>
                  {loading ? (
                    <Flex justify="center" py={8}>
                      <Spinner />
                    </Flex>
                  ) : (
                    <TasksTable tasksList={tasks.reserved || []} status="RESERVED" />
                  )}
                </TabPanel>
                <TabPanel>
                  {loading ? (
                    <Flex justify="center" py={8}>
                      <Spinner />
                    </Flex>
                  ) : (
                    <TasksTable tasksList={tasks.revoked || []} status="REVOKED" />
                  )}
                </TabPanel>
              </TabPanels>
            </Tabs>
          </CardBody>
        </Card>
      </VStack>

      {/* Модальное окно с деталями задачи */}
      <Modal isOpen={isOpen} onClose={onClose} size="xl">
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>Детали задачи Celery</ModalHeader>
          <ModalCloseButton />
          <ModalBody>
            {selectedTask && (
              <VStack align="stretch" spacing={4}>
                {/* Название задачи */}
                {selectedTask.booking && (
                  <Box borderWidth="1px" borderRadius="md" p={3} bg="purple.50">
                    <Text fontSize="lg" fontWeight="bold" color="purple.700">
                      {formatTaskName(null, selectedTask.booking.task_type)}
                    </Text>
                    <Text fontSize="xs" color="gray.600" mt={1}>
                      {selectedTask.booking.task_type}
                    </Text>
                  </Box>
                )}

                {/* Task ID */}
                <Box>
                  <Text fontWeight="bold" fontSize="sm" color="gray.600" mb={1}>
                    Идентификатор задачи:
                  </Text>
                  <Code fontSize="xs" display="block" p={2}>
                    {selectedTask.task_id}
                  </Code>
                </Box>

                {/* Статус */}
                <Box>
                  <Text fontWeight="bold" fontSize="sm" color="gray.600" mb={1}>
                    Статус:
                  </Text>
                  <Badge
                    colorScheme={getStatusColor(selectedTask.state)}
                    fontSize="sm"
                    px={3}
                    py={1}
                  >
                    {selectedTask.state === 'SUCCESS' ? 'Выполнена' :
                     selectedTask.state === 'PENDING' ? 'Ожидает' :
                     selectedTask.state === 'ACTIVE' ? 'Активна' :
                     selectedTask.state === 'SCHEDULED' ? 'Запланирована' :
                     selectedTask.state === 'RESERVED' ? 'Зарезервирована' :
                     selectedTask.state === 'REVOKED' ? 'Отменена' :
                     selectedTask.state === 'FAILURE' ? 'Ошибка' :
                     selectedTask.state}
                  </Badge>
                </Box>

                {/* Информация о бронировании */}
                {selectedTask.booking && (
                  <Box borderWidth="1px" borderRadius="md" p={3} bg="gray.50">
                    <Text fontWeight="bold" fontSize="sm" color="gray.600" mb={2}>
                      📋 Информация о бронировании:
                    </Text>
                    <VStack align="stretch" spacing={2}>
                      <HStack>
                        <Text fontSize="sm" fontWeight="medium" minW="140px">
                          Номер бронирования:
                        </Text>
                        <Badge colorScheme="blue">#{selectedTask.booking.booking_id}</Badge>
                      </HStack>

                      {/* Тип бронирования (тариф) */}
                      {selectedTask.booking.tariff_name && (
                        <HStack>
                          <Text fontSize="sm" fontWeight="medium" minW="140px">
                            Тип бронирования:
                          </Text>
                          <VStack align="start" spacing={0}>
                            <Text fontSize="sm" fontWeight="semibold">
                              {selectedTask.booking.tariff_purpose === 'meeting_room' ? '🏢 Переговорная' :
                               selectedTask.booking.tariff_purpose === 'open_space' ? '💼 Опенспейс' :
                               selectedTask.booking.tariff_purpose === 'fixed_workplace' ? '🪑 Фиксированное место' :
                               selectedTask.booking.tariff_purpose}
                            </Text>
                            <Text fontSize="xs" color="gray.600">
                              {selectedTask.booking.tariff_name}
                            </Text>
                          </VStack>
                        </HStack>
                      )}

                      {/* Пользователь */}
                      <HStack>
                        <Text fontSize="sm" fontWeight="medium" minW="140px">
                          Пользователь:
                        </Text>
                        <VStack align="start" spacing={0}>
                          <Text fontSize="sm" fontWeight="semibold">
                            👤 {selectedTask.booking.user_name || 'Не указано'}
                          </Text>
                          {selectedTask.booking.user_telegram_username && (
                            <Text fontSize="xs" color="blue.600">
                              @{selectedTask.booking.user_telegram_username}
                            </Text>
                          )}
                          <Text fontSize="xs" color="gray.500">
                            ID: {selectedTask.booking.user_id}
                          </Text>
                        </VStack>
                      </HStack>

                      {selectedTask.booking.visit_date && (
                        <HStack>
                          <Text fontSize="sm" fontWeight="medium" minW="140px">
                            Дата визита:
                          </Text>
                          <Text fontSize="sm">📅 {selectedTask.booking.visit_date}</Text>
                        </HStack>
                      )}

                      {selectedTask.booking.visit_time && (
                        <HStack>
                          <Text fontSize="sm" fontWeight="medium" minW="140px">
                            Время визита:
                          </Text>
                          <Text fontSize="sm">🕒 {selectedTask.booking.visit_time}</Text>
                        </HStack>
                      )}

                      {selectedTask.booking.duration && (
                        <HStack>
                          <Text fontSize="sm" fontWeight="medium" minW="140px">
                            Длительность:
                          </Text>
                          <Text fontSize="sm">⏱️ {selectedTask.booking.duration} {selectedTask.booking.duration === 1 ? 'час' : selectedTask.booking.duration < 5 ? 'часа' : 'часов'}</Text>
                        </HStack>
                      )}

                      <HStack spacing={2} mt={2}>
                        <Badge colorScheme={selectedTask.booking.confirmed ? 'green' : 'gray'} fontSize="xs">
                          {selectedTask.booking.confirmed ? '✓ Подтверждено' : '○ Не подтверждено'}
                        </Badge>
                        <Badge colorScheme={selectedTask.booking.paid ? 'green' : 'gray'} fontSize="xs">
                          {selectedTask.booking.paid ? '✓ Оплачено' : '○ Не оплачено'}
                        </Badge>
                      </HStack>
                    </VStack>
                  </Box>
                )}

                {/* Техническая информация */}
                {selectedTask.info && Object.keys(selectedTask.info).length > 0 && (
                  <Box>
                    <Text fontWeight="bold" fontSize="sm" color="gray.600" mb={1}>
                      Техническая информация:
                    </Text>
                    <Code display="block" whiteSpace="pre" p={3} fontSize="xs" borderRadius="md">
                      {JSON.stringify(selectedTask.info, null, 2)}
                    </Code>
                  </Box>
                )}
              </VStack>
            )}
          </ModalBody>
          <ModalFooter>
            {selectedTask?.state !== 'REVOKED' && selectedTask?.state !== 'SUCCESS' && (
              <Button
                colorScheme="red"
                mr={3}
                onClick={() => revokeTask(selectedTask?.task_id, false)}
                size="sm"
              >
                🚫 Отменить задачу
              </Button>
            )}
            <Button variant="ghost" onClick={onClose} size="sm">
              Закрыть
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>
    </Box>
  );
};

export default CeleryTasks;
