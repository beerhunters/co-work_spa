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
  AlertDialog,
  AlertDialogBody,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogContent,
  AlertDialogOverlay,
} from '@chakra-ui/react';
import {
  FiRefreshCw,
  FiClock,
  FiCheckCircle,
  FiXCircle,
  FiAlertCircle,
  FiInfo,
  FiTrash2,
  FiCalendar,
  FiAlertTriangle,
} from 'react-icons/fi';
import { colors, sizes, styles } from '../styles/styles';
import { createLogger } from '../utils/logger';
import api from '../utils/api';

const logger = createLogger('ScheduledTasks');

// Маппинг статусов на цвета
const getStatusColor = (status) => {
  switch (status?.toLowerCase()) {
    case 'pending':
      return 'blue';
    case 'running':
      return 'cyan';
    case 'completed':
      return 'green';
    case 'failed':
      return 'red';
    case 'cancelled':
      return 'gray';
    default:
      return 'gray';
  }
};

// Маппинг типов задач на читаемые названия
const getTaskTypeName = (taskType) => {
  switch (taskType) {
    case 'office_reminder_admin':
      return 'Напоминание администратору';
    case 'office_reminder_tenant':
      return 'Напоминание постояльцу';
    case 'booking_expiration':
      return 'Истечение бронирования';
    case 'booking_rental_reminder':
      return 'Напоминание об аренде';
    default:
      return taskType;
  }
};

// Маппинг полей параметров на русские названия
const getParamLabel = (key) => {
  const labels = {
    office_number: 'Номер офиса',
    floor: 'Этаж',
    reminder_type: 'Тип напоминания',
    booking_id: 'ID бронирования',
    user_id: 'ID пользователя',
    office_id: 'ID офиса',
    days_before: 'Дней до',
    message: 'Сообщение',
    telegram_id: 'Telegram ID',
    admin_id: 'ID администратора',
  };
  return labels[key] || key;
};

// Форматирование значения параметра
const formatParamValue = (key, value) => {
  if (value === null || value === undefined) return '—';
  if (typeof value === 'boolean') return value ? 'Да' : 'Нет';
  if (key === 'reminder_type') {
    return value === 'admin' ? 'Администратору' : value === 'tenant' ? 'Постояльцу' : value;
  }
  return String(value);
};

// Иконки для статусов
const getStatusIcon = (status) => {
  switch (status?.toLowerCase()) {
    case 'pending':
      return FiClock;
    case 'running':
      return FiRefreshCw;
    case 'completed':
      return FiCheckCircle;
    case 'failed':
      return FiXCircle;
    case 'cancelled':
      return FiAlertCircle;
    default:
      return FiInfo;
  }
};

// Форматирование даты/времени
const formatDateTime = (dateStr) => {
  if (!dateStr) return 'Не указано';
  try {
    const date = new Date(dateStr);
    return date.toLocaleString('ru-RU', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch (e) {
    return dateStr;
  }
};

// Форматирование времени до выполнения
const formatTimeUntil = (seconds) => {
  if (seconds === null || seconds === undefined) return '';

  const absSeconds = Math.abs(seconds);
  const isOverdue = seconds < 0;

  const days = Math.floor(absSeconds / 86400);
  const hours = Math.floor((absSeconds % 86400) / 3600);
  const minutes = Math.floor((absSeconds % 3600) / 60);

  let result = '';
  if (days > 0) result += `${days}д `;
  if (hours > 0) result += `${hours}ч `;
  if (minutes > 0 || result === '') result += `${minutes}м`;

  return isOverdue ? `Просрочено на ${result.trim()}` : `Через ${result.trim()}`;
};

const ScheduledTasks = () => {
  const [tasks, setTasks] = useState([]);
  const [stats, setStats] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [selectedTask, setSelectedTask] = useState(null);
  const [filterStatus, setFilterStatus] = useState('all');
  const [filterType, setFilterType] = useState('all');

  const toast = useToast();
  const { isOpen: isDetailOpen, onOpen: onDetailOpen, onClose: onDetailClose } = useDisclosure();
  const { isOpen: isDeleteOpen, onOpen: onDeleteOpen, onClose: onDeleteClose } = useDisclosure();
  const cancelRef = React.useRef();

  // Загрузка задач
  const fetchTasks = async () => {
    try {
      setIsLoading(true);

      // Формируем параметры запроса (временно без фильтров для отладки)
      const params = {};
      // if (filterStatus !== 'all') params.status = filterStatus;
      // if (filterType !== 'all') params.task_type = filterType;

      const response = await api.get('/scheduled-tasks/', { params });

      // Проверяем структуру ответа
      console.log('API response:', response.data);
      console.log('Response type:', typeof response.data);
      console.log('Is array:', Array.isArray(response.data));

      // Устанавливаем задачи, убедившись что это массив
      const tasksData = Array.isArray(response.data) ? response.data : [];
      setTasks(tasksData);

      logger.info(`Загружено ${tasksData.length} задач`);
    } catch (error) {
      logger.error('Ошибка загрузки задач:', error);
      setTasks([]); // Сбрасываем на пустой массив при ошибке
      toast({
        title: 'Ошибка',
        description: 'Не удалось загрузить список задач',
        status: 'error',
        duration: 3000,
      });
    } finally {
      setIsLoading(false);
    }
  };

  // Загрузка статистики
  const fetchStats = async () => {
    try {
      const response = await api.get('/scheduled-tasks/stats');
      setStats(response.data);
      logger.info('Статистика загружена');
    } catch (error) {
      logger.error('Ошибка загрузки статистики:', error);
    }
  };

  // Первоначальная загрузка
  useEffect(() => {
    fetchTasks();
    fetchStats();
  }, [filterStatus, filterType]);

  // Автообновление каждые 30 секунд
  useEffect(() => {
    const interval = setInterval(() => {
      fetchTasks();
      fetchStats();
    }, 30000);

    return () => clearInterval(interval);
  }, [filterStatus, filterType]);

  // Просмотр деталей задачи
  const handleViewDetails = async (task) => {
    try {
      const response = await api.get(`/scheduled-tasks/${task.id}`);
      setSelectedTask(response.data);
      onDetailOpen();
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
  const handleCancelTask = async (taskId) => {
    try {
      await api.post(`/scheduled-tasks/${taskId}/cancel`);
      toast({
        title: 'Задача отменена',
        description: 'Задача успешно отменена',
        status: 'success',
        duration: 3000,
      });
      fetchTasks();
      fetchStats();
      onDetailClose();
    } catch (error) {
      logger.error('Ошибка отмены задачи:', error);
      toast({
        title: 'Ошибка',
        description: error.response?.data?.detail || 'Не удалось отменить задачу',
        status: 'error',
        duration: 3000,
      });
    }
  };

  // Удаление задачи
  const handleDeleteTask = async () => {
    if (!selectedTask) return;

    try {
      await api.delete(`/scheduled-tasks/${selectedTask.id}`);
      toast({
        title: 'Задача удалена',
        description: 'Задача успешно удалена',
        status: 'success',
        duration: 3000,
      });
      fetchTasks();
      fetchStats();
      onDeleteClose();
      onDetailClose();
    } catch (error) {
      logger.error('Ошибка удаления задачи:', error);
      toast({
        title: 'Ошибка',
        description: error.response?.data?.detail || 'Не удалось удалить задачу',
        status: 'error',
        duration: 3000,
      });
    }
  };

  // Очистка старых задач
  const handleCleanup = async () => {
    try {
      const response = await api.post('/scheduled-tasks/cleanup', {
        older_than_days: 30
      });

      toast({
        title: 'Очистка выполнена',
        description: `Удалено задач: ${response.data.deleted_count}`,
        status: 'success',
        duration: 3000,
      });

      fetchTasks();
      fetchStats();
    } catch (error) {
      logger.error('Ошибка очистки задач:', error);
      toast({
        title: 'Ошибка',
        description: 'Не удалось выполнить очистку',
        status: 'error',
        duration: 3000,
      });
    }
  };

  return (
    <Box p={6}>
      <VStack spacing={6} align="stretch">
        {/* Заголовок и кнопки управления */}
        <Flex align="center">
          <Heading size="lg">Запланированные задачи</Heading>
          <Spacer />
          <HStack spacing={3}>
            <Button
              leftIcon={<FiTrash2 />}
              colorScheme="orange"
              size="sm"
              onClick={handleCleanup}
            >
              Очистить старые
            </Button>
            <Button
              leftIcon={<FiRefreshCw />}
              colorScheme="blue"
              size="sm"
              onClick={() => {
                fetchTasks();
                fetchStats();
              }}
              isLoading={isLoading}
            >
              Обновить
            </Button>
          </HStack>
        </Flex>

        {/* Статистика */}
        {stats && (
          <Grid templateColumns="repeat(auto-fit, minmax(150px, 1fr))" gap={4}>
            <Card>
              <CardBody>
                <Stat>
                  <StatLabel>Всего задач</StatLabel>
                  <StatNumber>{stats.total}</StatNumber>
                </Stat>
              </CardBody>
            </Card>

            <Card>
              <CardBody>
                <Stat>
                  <StatLabel>Ожидают</StatLabel>
                  <StatNumber color="blue.500">{stats.pending}</StatNumber>
                </Stat>
              </CardBody>
            </Card>

            <Card>
              <CardBody>
                <Stat>
                  <StatLabel>Выполняются</StatLabel>
                  <StatNumber color="cyan.500">{stats.running}</StatNumber>
                </Stat>
              </CardBody>
            </Card>

            <Card>
              <CardBody>
                <Stat>
                  <StatLabel>Завершены</StatLabel>
                  <StatNumber color="green.500">{stats.completed}</StatNumber>
                </Stat>
              </CardBody>
            </Card>

            <Card>
              <CardBody>
                <Stat>
                  <StatLabel>Ошибки</StatLabel>
                  <StatNumber color="red.500">{stats.failed}</StatNumber>
                </Stat>
              </CardBody>
            </Card>

            <Card>
              <CardBody>
                <Stat>
                  <StatLabel>Просрочено</StatLabel>
                  <StatNumber color="orange.500">{stats.overdue}</StatNumber>
                </Stat>
              </CardBody>
            </Card>
          </Grid>
        )}

        {/* Фильтры */}
        <Card>
          <CardBody>
            <HStack spacing={4}>
              <Box flex="1">
                <Text fontSize="sm" mb={2}>Статус:</Text>
                <Select
                  value={filterStatus}
                  onChange={(e) => setFilterStatus(e.target.value)}
                  size="sm"
                >
                  <option value="all">Все</option>
                  <option value="pending">Ожидают</option>
                  <option value="running">Выполняются</option>
                  <option value="completed">Завершены</option>
                  <option value="failed">Ошибки</option>
                  <option value="cancelled">Отменены</option>
                </Select>
              </Box>

              <Box flex="1">
                <Text fontSize="sm" mb={2}>Тип задачи:</Text>
                <Select
                  value={filterType}
                  onChange={(e) => setFilterType(e.target.value)}
                  size="sm"
                >
                  <option value="all">Все</option>
                  <option value="office_reminder_admin">Напоминания администратору</option>
                  <option value="office_reminder_tenant">Напоминания постояльцам</option>
                  <option value="booking_expiration">Истечение бронирования</option>
                  <option value="booking_rental_reminder">Напоминания об аренде</option>
                </Select>
              </Box>
            </HStack>
          </CardBody>
        </Card>

        {/* Таблица задач */}
        <Card>
          <CardHeader>
            <Heading size="md">
              Список задач ({tasks.length})
            </Heading>
          </CardHeader>
          <CardBody>
            {isLoading ? (
              <Flex justify="center" py={10}>
                <Spinner size="xl" />
              </Flex>
            ) : tasks.length === 0 ? (
              <Alert status="info">
                <AlertIcon />
                <AlertTitle>Нет задач</AlertTitle>
                <AlertDescription>
                  Запланированные задачи отсутствуют
                </AlertDescription>
              </Alert>
            ) : (
              <Box overflowX="auto">
                <Table variant="simple" size="sm">
                  <Thead>
                    <Tr>
                      <Th>ID</Th>
                      <Th>Тип</Th>
                      <Th>Статус</Th>
                      <Th>Запланировано</Th>
                      <Th>До выполнения</Th>
                      <Th>Офис/Бронь</Th>
                      <Th>Создано</Th>
                      <Th>Действия</Th>
                    </Tr>
                  </Thead>
                  <Tbody>
                    {tasks.map((task) => {
                      const StatusIcon = getStatusIcon(task.status);

                      return (
                        <Tr key={task.id}>
                          <Td>{task.id}</Td>
                          <Td>
                            <Text fontSize="xs">
                              {getTaskTypeName(task.task_type)}
                            </Text>
                          </Td>
                          <Td>
                            <Badge
                              colorScheme={getStatusColor(task.status)}
                              display="flex"
                              alignItems="center"
                              gap={1}
                              w="fit-content"
                            >
                              <StatusIcon size={12} />
                              {task.status}
                            </Badge>
                          </Td>
                          <Td>
                            <Text fontSize="xs">
                              {formatDateTime(task.scheduled_datetime)}
                            </Text>
                          </Td>
                          <Td>
                            {task.is_overdue ? (
                              <Badge colorScheme="orange" display="flex" alignItems="center" gap={1}>
                                <FiAlertTriangle size={12} />
                                Просрочено
                              </Badge>
                            ) : (
                              <Text fontSize="xs" color="gray.600">
                                {formatTimeUntil(task.time_until_execution_seconds)}
                              </Text>
                            )}
                          </Td>
                          <Td>
                            {task.office_id && (
                              <Badge colorScheme="purple">Офис #{task.office_id}</Badge>
                            )}
                            {task.booking_id && (
                              <Badge colorScheme="blue">Бронь #{task.booking_id}</Badge>
                            )}
                          </Td>
                          <Td>
                            <Text fontSize="xs" color="gray.600">
                              {formatDateTime(task.created_at)}
                            </Text>
                          </Td>
                          <Td>
                            <HStack spacing={1}>
                              <Tooltip label="Детали">
                                <IconButton
                                  icon={<FiInfo />}
                                  size="sm"
                                  variant="ghost"
                                  onClick={() => handleViewDetails(task)}
                                />
                              </Tooltip>

                              {task.status === 'pending' && (
                                <Tooltip label="Отменить">
                                  <IconButton
                                    icon={<FiXCircle />}
                                    size="sm"
                                    variant="ghost"
                                    colorScheme="orange"
                                    onClick={() => handleCancelTask(task.id)}
                                  />
                                </Tooltip>
                              )}

                              <Tooltip label="Удалить">
                                <IconButton
                                  icon={<FiTrash2 />}
                                  size="sm"
                                  variant="ghost"
                                  colorScheme="red"
                                  onClick={() => {
                                    setSelectedTask(task);
                                    onDeleteOpen();
                                  }}
                                />
                              </Tooltip>
                            </HStack>
                          </Td>
                        </Tr>
                      );
                    })}
                  </Tbody>
                </Table>
              </Box>
            )}
          </CardBody>
        </Card>
      </VStack>

      {/* Модальное окно с деталями задачи */}
      <Modal isOpen={isDetailOpen} onClose={onDetailClose} size="xl">
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>Детали задачи #{selectedTask?.id}</ModalHeader>
          <ModalCloseButton />
          <ModalBody>
            {selectedTask && (
              <VStack align="stretch" spacing={4}>
                <Box>
                  <Text fontWeight="bold" mb={2}>Общая информация</Text>
                  <VStack align="stretch" spacing={2}>
                    <HStack>
                      <Text fontWeight="semibold" minW="150px">Тип:</Text>
                      <Text>{getTaskTypeName(selectedTask.task_type)}</Text>
                    </HStack>
                    <HStack>
                      <Text fontWeight="semibold" minW="150px">Статус:</Text>
                      <Badge colorScheme={getStatusColor(selectedTask.status)}>
                        {selectedTask.status}
                      </Badge>
                    </HStack>
                    <HStack>
                      <Text fontWeight="semibold" minW="150px">Celery Task ID:</Text>
                      <Code fontSize="xs">{selectedTask.celery_task_id || 'Нет'}</Code>
                    </HStack>
                    <HStack>
                      <Text fontWeight="semibold" minW="150px">Запланировано:</Text>
                      <Text>{formatDateTime(selectedTask.scheduled_datetime)}</Text>
                    </HStack>
                    <HStack>
                      <Text fontWeight="semibold" minW="150px">Создано:</Text>
                      <Text>{formatDateTime(selectedTask.created_at)}</Text>
                    </HStack>
                    <HStack>
                      <Text fontWeight="semibold" minW="150px">Создал:</Text>
                      <Text>{selectedTask.created_by}</Text>
                    </HStack>
                    {selectedTask.executed_at && (
                      <HStack>
                        <Text fontWeight="semibold" minW="150px">Выполнено:</Text>
                        <Text>{formatDateTime(selectedTask.executed_at)}</Text>
                      </HStack>
                    )}
                    <HStack>
                      <Text fontWeight="semibold" minW="150px">Попыток:</Text>
                      <Text>{selectedTask.retry_count}</Text>
                    </HStack>
                  </VStack>
                </Box>

                {selectedTask.params && Object.keys(selectedTask.params).length > 0 && (
                  <Box>
                    <Text fontWeight="bold" mb={2}>Параметры</Text>
                    <VStack align="stretch" spacing={2} bg="gray.50" p={3} borderRadius="md">
                      {Object.entries(selectedTask.params).map(([key, value]) => (
                        <HStack key={key}>
                          <Text fontWeight="semibold" minW="150px" color="gray.600">
                            {getParamLabel(key)}:
                          </Text>
                          <Text>{formatParamValue(key, value)}</Text>
                        </HStack>
                      ))}
                    </VStack>
                  </Box>
                )}

                {selectedTask.result && (
                  <Box>
                    <Text fontWeight="bold" mb={2}>Результат</Text>
                    <Code p={3} borderRadius="md" w="full" fontSize="xs" colorScheme="green">
                      <pre>{JSON.stringify(selectedTask.result, null, 2)}</pre>
                    </Code>
                  </Box>
                )}

                {selectedTask.error_message && (
                  <Box>
                    <Text fontWeight="bold" mb={2} color="red.500">Ошибка</Text>
                    <Alert status="error">
                      <AlertIcon />
                      <Text fontSize="sm">{selectedTask.error_message}</Text>
                    </Alert>
                  </Box>
                )}
              </VStack>
            )}
          </ModalBody>
          <ModalFooter>
            {selectedTask?.status === 'pending' && (
              <Button
                colorScheme="orange"
                mr={3}
                onClick={() => handleCancelTask(selectedTask.id)}
              >
                Отменить задачу
              </Button>
            )}
            <Button variant="ghost" onClick={onDetailClose}>
              Закрыть
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
              Удалить задачу
            </AlertDialogHeader>

            <AlertDialogBody>
              Вы уверены, что хотите удалить задачу #{selectedTask?.id}?
              {selectedTask?.status === 'pending' && (
                <Text mt={2} color="orange.500">
                  Внимание: задача будет также отменена в Celery.
                </Text>
              )}
            </AlertDialogBody>

            <AlertDialogFooter>
              <Button ref={cancelRef} onClick={onDeleteClose}>
                Отмена
              </Button>
              <Button colorScheme="red" onClick={handleDeleteTask} ml={3}>
                Удалить
              </Button>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialogOverlay>
      </AlertDialog>
    </Box>
  );
};

export default ScheduledTasks;
