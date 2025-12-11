import React, { useState, useEffect } from 'react';
import {
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalBody,
  ModalCloseButton,
  VStack,
  HStack,
  Text,
  Badge,
  ModalFooter,
  Button,
  Box,
  Icon,
  Card,
  CardBody,
  useColorModeValue,
  Skeleton,
  Tooltip,
  Link,
  useToast,
  Alert,
  AlertIcon,
  AlertTitle,
  AlertDescription,
  Input,
  FormControl,
  FormLabel,
  NumberInput,
  NumberInputField,
  NumberInputStepper,
  NumberIncrementStepper,
  NumberDecrementStepper,
  Divider,
  IconButton
} from '@chakra-ui/react';
import {
  FiUser,
  FiCalendar,
  FiClock,
  FiDollarSign,
  FiTag,
  FiPercent,
  FiPhone,
  FiMail,
  FiMessageCircle,
  FiCheck,
  FiX,
  FiExternalLink,
  FiCopy,
  FiRefreshCw,
  FiAlertTriangle,
  FiInfo,
  FiEdit2,
  FiSave,
  FiSend
} from 'react-icons/fi';
import { getStatusColor } from '../../styles/styles';
import { bookingApi } from '../../utils/api';

const BookingDetailModal = ({ isOpen, onClose, booking, onUpdate, currentAdmin }) => {
  const [detailedBooking, setDetailedBooking] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [retryCount, setRetryCount] = useState(0);
  const [actionLoading, setActionLoading] = useState({ confirm: false, markPaid: false, markFree: false, save: false, sendLink: false, cancel: false });
  const toast = useToast();

  // Состояния для редактирования
  const [isEditing, setIsEditing] = useState(false);
  const [editData, setEditData] = useState({
    visit_date: null,
    visit_time: null,
    duration: null
  });
  const [recalculatedAmount, setRecalculatedAmount] = useState(null);

  const bgColor = useColorModeValue('white', 'gray.800');

  // Загрузка детальной информации о бронировании
  const fetchBookingDetails = async (showToast = true) => {
    if (!booking || !isOpen) return;

    setLoading(true);
    setError(null);

    try {
      console.log('Загрузка деталей бронирования:', booking.id);

      // Сначала валидируем ID
      const validation = await bookingApi.validateId(booking.id);
      if (!validation.exists) {
        throw new Error('Бронирование не найдено или было удалено');
      }

      // Загружаем детальную информацию
      const detailed = await bookingApi.getByIdDetailed(booking.id);
      console.log('Получены детали бронирования:', detailed);

      setDetailedBooking(detailed);
      setRetryCount(0); // Сбрасываем счетчик попыток при успехе

    } catch (error) {
      console.error('Ошибка загрузки деталей бронирования:', error);
      setError(error.message || 'Не удалось загрузить детали бронирования');

      if (showToast) {
        toast({
          title: 'Ошибка загрузки',
          description: error.message || 'Не удалось загрузить детали бронирования',
          status: 'error',
          duration: 5000,
          isClosable: true,
        });
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchBookingDetails();
  }, [booking, isOpen]);

  // Сброс состояния при закрытии
  useEffect(() => {
    if (!isOpen) {
      setDetailedBooking(null);
      setLoading(true);
      setError(null);
      setRetryCount(0);
    }
  }, [isOpen]);

  const handleRetry = async () => {
    setRetryCount(prev => prev + 1);
    await fetchBookingDetails(false);
  };

  const formatDate = (dateString) => {
    try {
      return new Date(dateString).toLocaleDateString('ru-RU');
    } catch {
      return 'Неизвестно';
    }
  };

  const formatDateTime = (dateString) => {
    try {
      return new Date(dateString).toLocaleString('ru-RU');
    } catch {
      return 'Неизвестно';
    }
  };

  const formatTime = (timeString) => {
    if (!timeString) return 'Весь день';
    try {
      return timeString.slice(0, 5); // HH:MM
    } catch {
      return 'Неизвестно';
    }
  };

  const copyToClipboard = (text, label) => {
    navigator.clipboard.writeText(text).then(() => {
      toast({
        title: `${label} скопирован`,
        status: 'success',
        duration: 2000,
        isClosable: true,
      });
    });
  };

  const getTelegramUrl = (username) => {
    if (!username) return null;
    const cleanUsername = username.startsWith('@') ? username.slice(1) : username;
    return `https://t.me/${cleanUsername}`;
  };

  const getMailtoUrl = (email) => {
    if (!email) return null;
    return `mailto:${email}`;
  };

  const debugBooking = async () => {
    console.log('Запуск отладки бронирования...');
    const debugInfo = await bookingApi.debug(booking.id);
    console.log('Результат отладки:', debugInfo);

    toast({
      title: 'Отладка завершена',
      description: 'Проверьте консоль для детальной информации',
      status: 'info',
      duration: 3000,
    });
  };

  // Подтверждение бронирования
  const handleConfirmBooking = async () => {
    setActionLoading(prev => ({ ...prev, confirm: true }));

    try {
      await bookingApi.updateBooking(booking.id, { confirmed: true });

      toast({
        title: 'Бронирование подтверждено',
        description: 'Пользователь получит уведомление',
        status: 'success',
        duration: 3000,
        isClosable: true,
      });

      // Перезагружаем данные из API для актуального отображения
      await fetchBookingDetails(false);

      // Вызываем callback для обновления родительского компонента
      if (onUpdate) {
        onUpdate();
      }

    } catch (error) {
      console.error('Ошибка подтверждения бронирования:', error);
      toast({
        title: 'Ошибка подтверждения',
        description: error.message || 'Не удалось подтвердить бронирование',
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    } finally {
      setActionLoading(prev => ({ ...prev, confirm: false }));
    }
  };

  // Отметить как оплачено
  const handleMarkAsPaid = async () => {
    setActionLoading(prev => ({ ...prev, markPaid: true }));

    try {
      await bookingApi.updateBooking(booking.id, { paid: true });

      toast({
        title: 'Отмечено как оплачено',
        description: 'Пользователь получит уведомление о зачислении оплаты',
        status: 'success',
        duration: 3000,
        isClosable: true,
      });

      // Перезагружаем данные из API для актуального отображения
      await fetchBookingDetails(false);

      // Вызываем callback для обновления родительского компонента
      if (onUpdate) {
        onUpdate();
      }

    } catch (error) {
      console.error('Ошибка отметки оплаты:', error);
      toast({
        title: 'Ошибка обновления',
        description: error.message || 'Не удалось отметить как оплачено',
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    } finally {
      setActionLoading(prev => ({ ...prev, markPaid: false }));
    }
  };

  // Отметить как бесплатное (без оплаты)
  const handleMarkAsFree = async () => {
    setActionLoading(prev => ({ ...prev, markFree: true }));

    try {
      await bookingApi.updateBooking(booking.id, {
        amount: 0,
        paid: true,
        confirmed: true
      });

      toast({
        title: 'Отмечено как бесплатное',
        description: 'Бронирование подтверждено без оплаты',
        status: 'success',
        duration: 3000,
        isClosable: true,
      });

      // Перезагружаем данные из API для актуального отображения
      await fetchBookingDetails(false);

      // Вызываем callback для обновления родительского компонента
      if (onUpdate) {
        onUpdate();
      }

    } catch (error) {
      console.error('Ошибка отметки как бесплатное:', error);
      toast({
        title: 'Ошибка обновления',
        description: error.message || 'Не удалось отметить как бесплатное',
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    } finally {
      setActionLoading(prev => ({ ...prev, markFree: false }));
    }
  };

  // Отменить бронирование
  const handleCancelBooking = async () => {
    setActionLoading(prev => ({ ...prev, cancel: true }));

    try {
      // Рассчитываем сумму на основе тарифа
      const data = detailedBooking || booking;
      const tariff = data.tariff || {};
      const duration = data.duration || 1;

      // Базовая сумма тарифа
      let calculatedAmount = tariff.price || 0;

      // Для переговорных умножаем на длительность
      if (tariff.purpose === 'meeting_room' && duration) {
        calculatedAmount = tariff.price * duration;
      }

      await bookingApi.updateBooking(booking.id, {
        confirmed: false,
        paid: false,
        amount: calculatedAmount
      });

      toast({
        title: 'Бронирование отменено',
        description: 'Пользователь получит уведомление об отмене',
        status: 'warning',
        duration: 3000,
        isClosable: true,
      });

      // Перезагружаем данные из API для актуального отображения
      await fetchBookingDetails(false);

      // Вызываем callback для обновления родительского компонента
      if (onUpdate) {
        onUpdate();
      }

    } catch (error) {
      console.error('Ошибка отмены бронирования:', error);
      toast({
        title: 'Ошибка отмены',
        description: error.message || 'Не удалось отменить бронирование',
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    } finally {
      setActionLoading(prev => ({ ...prev, cancel: false }));
    }
  };

  // Начать редактирование
  const handleStartEdit = () => {
    if (!detailedBooking) return;

    setEditData({
      visit_date: detailedBooking.visit_date || '',
      visit_time: detailedBooking.visit_time || '',
      duration: detailedBooking.duration || ''
    });
    setRecalculatedAmount(detailedBooking.amount);
    setIsEditing(true);
  };

  // Отменить редактирование
  const handleCancelEdit = () => {
    setIsEditing(false);
    setEditData({ visit_date: null, visit_time: null, duration: null });
    setRecalculatedAmount(null);
  };

  // Пересчет суммы при изменении полей
  const handleRecalculate = async () => {
    try {
      const result = await bookingApi.recalculateAmount(booking.id, {
        visit_date: editData.visit_date,
        visit_time: editData.visit_time,
        duration: editData.duration ? parseInt(editData.duration) : null
      });

      setRecalculatedAmount(result.amount);

      toast({
        title: 'Сумма пересчитана',
        description: `Новая сумма: ${result.amount} ₽ ${result.discount > 0 ? `(скидка ${result.discount}%)` : ''}`,
        status: 'info',
        duration: 3000,
        isClosable: true,
      });
    } catch (error) {
      console.error('Ошибка пересчета суммы:', error);
      toast({
        title: 'Ошибка пересчета',
        description: error.message || 'Не удалось пересчитать сумму',
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    }
  };

  // Сохранить изменения
  const handleSaveEdit = async () => {
    setActionLoading(prev => ({ ...prev, save: true }));

    try {
      await bookingApi.updateBookingFull(booking.id, {
        visit_date: editData.visit_date,
        visit_time: editData.visit_time,
        duration: editData.duration ? parseInt(editData.duration) : null,
        amount: recalculatedAmount
      });

      toast({
        title: 'Бронирование обновлено',
        description: 'Пользователь получит уведомление об изменениях',
        status: 'success',
        duration: 3000,
        isClosable: true,
      });

      setIsEditing(false);

      // Перезагрузить данные
      await fetchBookingDetails();

      // Вызываем callback для обновления родительского компонента
      if (onUpdate) {
        onUpdate();
      }

    } catch (error) {
      console.error('Ошибка сохранения:', error);
      toast({
        title: 'Ошибка сохранения',
        description: error.message || 'Не удалось сохранить изменения',
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    } finally {
      setActionLoading(prev => ({ ...prev, save: false }));
    }
  };

  // Отправить платежную ссылку
  const handleSendPaymentLink = async () => {
    setActionLoading(prev => ({ ...prev, sendLink: true }));

    try {
      const result = await bookingApi.sendPaymentLink(booking.id);

      toast({
        title: 'Ссылка отправлена',
        description: result.message || 'Платежная ссылка отправлена пользователю в Telegram',
        status: 'success',
        duration: 5000,
        isClosable: true,
      });

      // Перезагрузить данные (payment_id должен появиться)
      await fetchBookingDetails();

      // Вызываем callback для обновления родительского компонента
      if (onUpdate) {
        onUpdate();
      }

    } catch (error) {
      console.error('Ошибка отправки ссылки:', error);
      toast({
        title: 'Ошибка отправки',
        description: error.message || 'Не удалось отправить платежную ссылку',
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    } finally {
      setActionLoading(prev => ({ ...prev, sendLink: false }));
    }
  };

  if (!booking) return null;

  const data = detailedBooking || booking;
  const user = data.user || {};
  const tariff = data.tariff || {};
  const promocode = data.promocode;

  return (
    <Modal isOpen={isOpen} onClose={onClose} size="2xl" scrollBehavior="inside">
      <ModalOverlay />
      <ModalContent maxH="90vh">
        <ModalHeader bg="gray.50" borderTopRadius="md">
          <HStack justify="space-between" align="center">
            <HStack>
              <Text fontSize="xl" fontWeight="bold">Бронирование #{data.id}</Text>
              <Badge colorScheme={getStatusColor(data.paid ? 'paid' : 'unpaid')} fontSize="sm">
                {data.paid ? 'Оплачено' : 'Не оплачено'}
              </Badge>
              <Badge colorScheme={getStatusColor(data.confirmed ? 'confirmed' : 'pending')} fontSize="sm">
                {data.confirmed ? 'Подтверждено' : 'Ожидает'}
              </Badge>
            </HStack>
          </HStack>
        </ModalHeader>
        <ModalCloseButton />

        <ModalBody p={6}>
          <VStack align="stretch" spacing={6}>

            {/* Показываем ошибку если есть */}
            {error && (
              <Alert status="error">
                <AlertIcon />
                <Box>
                  <AlertTitle>Ошибка загрузки данных!</AlertTitle>
                  <AlertDescription>
                    {error}
                    <HStack mt={2} spacing={2}>
                      <Button size="sm" colorScheme="red" onClick={handleRetry}>
                        <FiRefreshCw style={{ marginRight: '8px' }} />
                        Повторить ({retryCount})
                      </Button>
                      <Button size="sm" variant="outline" onClick={debugBooking}>
                        <FiAlertTriangle style={{ marginRight: '8px' }} />
                        Отладка
                      </Button>
                    </HStack>
                  </AlertDescription>
                </Box>
              </Alert>
            )}

            {/* Блок 1: Информация о клиенте */}
            <Card>
              <CardBody>
                <VStack align="stretch" spacing={4}>
                  <HStack>
                    <Icon as={FiUser} color="blue.500" boxSize={5} />
                    <Text fontSize="lg" fontWeight="semibold">Информация о клиенте</Text>
                  </HStack>

                  {loading ? (
                    <VStack spacing={3}>
                      <Skeleton height="20px" />
                      <Skeleton height="20px" />
                      <Skeleton height="20px" />
                      <Skeleton height="20px" />
                    </VStack>
                  ) : (
                    <VStack align="stretch" spacing={3}>
                      <HStack justify="space-between">
                        <Text fontWeight="medium">Имя:</Text>
                        <Text>{user.full_name || 'Не указано'}</Text>
                      </HStack>

                      <HStack justify="space-between">
                        <HStack>
                          <Icon as={FiPhone} color="green.500" />
                          <Text fontWeight="medium">Телефон:</Text>
                        </HStack>
                        {user.phone ? (
                          <HStack>
                            <Text>{user.phone}</Text>
                            <Tooltip label="Скопировать">
                              <Button
                                size="xs"
                                variant="ghost"
                                onClick={() => copyToClipboard(user.phone, 'Телефон')}
                              >
                                <FiCopy />
                              </Button>
                            </Tooltip>
                          </HStack>
                        ) : (
                          <Text color="gray.500">Не указан</Text>
                        )}
                      </HStack>

                      <HStack justify="space-between">
                        <HStack>
                          <Icon as={FiMail} color="orange.500" />
                          <Text fontWeight="medium">Почта:</Text>
                        </HStack>
                        {user.email ? (
                          <Link href={getMailtoUrl(user.email)} color="blue.500" isExternal>
                            {user.email}
                            <Icon as={FiExternalLink} mx="2px" />
                          </Link>
                        ) : (
                          <Text color="gray.500">Не указана</Text>
                        )}
                      </HStack>

                      <HStack justify="space-between">
                        <HStack>
                          <Icon as={FiMessageCircle} color="purple.500" />
                          <Text fontWeight="medium">Telegram:</Text>
                        </HStack>
                        {user.username ? (
                          <Link href={getTelegramUrl(user.username)} color="blue.500" isExternal>
                            @{user.username}
                            <Icon as={FiExternalLink} mx="2px" />
                          </Link>
                        ) : (
                          <Text color="gray.500">Не указан</Text>
                        )}
                      </HStack>
                    </VStack>
                  )}
                </VStack>
              </CardBody>
            </Card>

            {/* Блок 2: Детали бронирования */}
            <Card>
              <CardBody>
                <VStack align="stretch" spacing={4}>
                  <HStack>
                    <Icon as={FiCalendar} color="orange.500" boxSize={5} />
                    <Text fontSize="lg" fontWeight="semibold">Детали бронирования</Text>
                  </HStack>

                  {loading ? (
                    <VStack spacing={3}>
                      <Skeleton height="20px" />
                      <Skeleton height="20px" />
                      <Skeleton height="20px" />
                      <Skeleton height="20px" />
                      <Skeleton height="20px" />
                      <Skeleton height="20px" />
                    </VStack>
                  ) : isEditing ? (
                    <VStack align="stretch" spacing={4}>
                      <HStack justify="space-between">
                        <HStack>
                          <Icon as={FiTag} color="cyan.500" />
                          <Text fontWeight="medium">Название тарифа:</Text>
                        </HStack>
                        <Text fontSize="lg" fontWeight="semibold">{tariff.name || 'Неизвестно'}</Text>
                      </HStack>

                      <FormControl>
                        <FormLabel fontSize="sm">Дата визита</FormLabel>
                        <Input
                          type="date"
                          value={editData.visit_date}
                          onChange={(e) => setEditData({ ...editData, visit_date: e.target.value })}
                        />
                      </FormControl>

                      {tariff.purpose === 'meeting_room' && (
                        <>
                          <FormControl>
                            <FormLabel fontSize="sm">Время</FormLabel>
                            <Input
                              type="time"
                              value={editData.visit_time}
                              onChange={(e) => setEditData({ ...editData, visit_time: e.target.value })}
                            />
                          </FormControl>

                          <FormControl>
                            <FormLabel fontSize="sm">Длительность (часов)</FormLabel>
                            <NumberInput
                              min={1}
                              max={24}
                              value={editData.duration}
                              onChange={(val) => setEditData({ ...editData, duration: val })}
                            >
                              <NumberInputField />
                              <NumberInputStepper>
                                <NumberIncrementStepper />
                                <NumberDecrementStepper />
                              </NumberInputStepper>
                            </NumberInput>
                          </FormControl>
                        </>
                      )}

                      <Divider />

                      <HStack justify="space-between">
                        <HStack>
                          <Icon as={FiDollarSign} color="green.500" />
                          <Text fontWeight="medium">Пересчитанная сумма:</Text>
                        </HStack>
                        <Text fontSize="lg" fontWeight="bold" color="green.500">
                          {recalculatedAmount !== null ? `${recalculatedAmount} ₽` : `${data.amount} ₽`}
                        </Text>
                      </HStack>

                      <HStack spacing={2} width="100%">
                        <Button
                          leftIcon={<FiRefreshCw />}
                          colorScheme="blue"
                          variant="outline"
                          size="sm"
                          onClick={handleRecalculate}
                          flex={1}
                        >
                          Пересчитать
                        </Button>
                        <Button
                          leftIcon={<FiSave />}
                          colorScheme="green"
                          size="sm"
                          onClick={handleSaveEdit}
                          isLoading={actionLoading.save}
                          loadingText="Сохранение..."
                          flex={1}
                        >
                          Сохранить
                        </Button>
                        <Button
                          leftIcon={<FiX />}
                          colorScheme="red"
                          variant="outline"
                          size="sm"
                          onClick={handleCancelEdit}
                          flex={1}
                        >
                          Отмена
                        </Button>
                      </HStack>
                    </VStack>
                  ) : (
                    <VStack align="stretch" spacing={3}>
                      <HStack justify="space-between">
                        <HStack>
                          <Icon as={FiTag} color="cyan.500" />
                          <Text fontWeight="medium">Название тарифа:</Text>
                        </HStack>
                        <Text fontSize="lg" fontWeight="semibold">{tariff.name || 'Неизвестно'}</Text>
                      </HStack>

                      <HStack justify="space-between">
                        <HStack>
                          <Icon as={FiCalendar} color="blue.500" />
                          <Text fontWeight="medium">Дата визита:</Text>
                        </HStack>
                        <Text fontSize="lg">{formatDate(data.visit_date)}</Text>
                      </HStack>

                      <HStack justify="space-between">
                        <HStack>
                          <Icon as={FiClock} color="purple.500" />
                          <Text fontWeight="medium">Время:</Text>
                        </HStack>
                        <Text>{formatTime(data.visit_time)}</Text>
                      </HStack>

                      {data.duration && (
                        <HStack justify="space-between">
                          <Text fontWeight="medium">Длительность:</Text>
                          <Badge colorScheme="orange">{data.duration} час(ов)</Badge>
                        </HStack>
                      )}

                      <HStack justify="space-between">
                        <HStack>
                          <Icon as={FiDollarSign} color="green.500" />
                          <Text fontWeight="medium">Итоговая сумма:</Text>
                        </HStack>
                        <Text fontSize="lg" fontWeight="bold" color="green.500">
                          {data.amount} ₽
                        </Text>
                      </HStack>

                      <HStack justify="space-between">
                        <Text fontWeight="medium">Статус оплаты:</Text>
                        <Badge colorScheme={getStatusColor(data.paid ? 'paid' : 'unpaid')}>
                          {data.paid ? (
                            <HStack spacing={1}>
                              <Icon as={FiCheck} />
                              <Text>Оплачено</Text>
                            </HStack>
                          ) : (
                            <HStack spacing={1}>
                              <Icon as={FiX} />
                              <Text>Не оплачено</Text>
                            </HStack>
                          )}
                        </Badge>
                      </HStack>

                      <HStack justify="space-between">
                        <Text fontWeight="medium">Подтверждение:</Text>
                        <Badge colorScheme={getStatusColor(data.confirmed ? 'confirmed' : 'pending')}>
                          {data.confirmed ? (
                            <HStack spacing={1}>
                              <Icon as={FiCheck} />
                              <Text>Подтверждено</Text>
                            </HStack>
                          ) : (
                            <Text>Ожидает подтверждения</Text>
                          )}
                        </Badge>
                      </HStack>
                    </VStack>
                  )}
                </VStack>
              </CardBody>
            </Card>

            {/* Блок 3: Дополнительная информация */}
            <Card>
              <CardBody>
                <VStack align="stretch" spacing={4}>
                  <HStack>
                    <Icon as={FiInfo} color="gray.500" boxSize={5} />
                    <Text fontSize="lg" fontWeight="semibold">Дополнительная информация</Text>
                  </HStack>

                  {loading ? (
                    <VStack spacing={3}>
                      <Skeleton height="20px" />
                      <Skeleton height="20px" />
                      <Skeleton height="20px" />
                    </VStack>
                  ) : (
                    <VStack align="stretch" spacing={3}>
                      <HStack justify="space-between">
                        <Text fontWeight="medium">Дата создания:</Text>
                        <Text fontSize="sm">{formatDateTime(data.created_at)}</Text>
                      </HStack>

                      {data.rubitime_id && (
                        <HStack justify="space-between">
                          <Text fontWeight="medium">Rubitime ID:</Text>
                          <HStack>
                            <Text fontFamily="mono" fontSize="sm">{data.rubitime_id}</Text>
                            <Tooltip label="Скопировать">
                              <Button
                                size="xs"
                                variant="ghost"
                                onClick={() => copyToClipboard(data.rubitime_id, 'Rubitime ID')}
                              >
                                <FiCopy />
                              </Button>
                            </Tooltip>
                          </HStack>
                        </HStack>
                      )}

                      {data.payment_id && (
                        <HStack justify="space-between">
                          <Text fontWeight="medium">ID платежа:</Text>
                          <HStack>
                            <Text fontFamily="mono" fontSize="sm">{data.payment_id}</Text>
                            <Tooltip label="Скопировать">
                              <Button
                                size="xs"
                                variant="ghost"
                                onClick={() => copyToClipboard(data.payment_id, 'ID платежа')}
                              >
                                <FiCopy />
                              </Button>
                            </Tooltip>
                          </HStack>
                        </HStack>
                      )}
                    </VStack>
                  )}
                </VStack>
              </CardBody>
            </Card>

            {/* Информация о промокоде (если есть) */}
            {data.promocode_id && (
              <Card>
                <CardBody>
                  <VStack align="stretch" spacing={4}>
                    <HStack>
                      <Icon as={FiPercent} color="purple.500" boxSize={5} />
                      <Text fontSize="lg" fontWeight="semibold">Использованный промокод</Text>
                    </HStack>

                    {loading ? (
                      <Skeleton height="40px" />
                    ) : promocode ? (
                      <VStack align="stretch" spacing={3}>
                        <HStack justify="space-between">
                          <Text fontWeight="medium">Название:</Text>
                          <Text fontSize="lg" fontWeight="bold" fontFamily="mono" color="purple.500">
                            {promocode.name}
                          </Text>
                        </HStack>
                        <HStack justify="space-between">
                          <Text fontWeight="medium">Скидка:</Text>
                          <Badge colorScheme="purple" fontSize="md">
                            -{promocode.discount}%
                          </Badge>
                        </HStack>
                        <HStack justify="space-between">
                          <Text fontWeight="medium">Статус:</Text>
                          <Badge colorScheme={promocode.is_active ? 'green' : 'red'}>
                            {promocode.is_active ? 'Активен' : 'Неактивен'}
                          </Badge>
                        </HStack>
                        <HStack justify="space-between">
                          <Text fontWeight="medium">Остается использований:</Text>
                          <Text>{promocode.usage_quantity || 0}</Text>
                        </HStack>
                      </VStack>
                    ) : (
                      <Box p={3} bg="orange.50" borderRadius="md" borderLeft="4px solid" borderLeftColor="orange.400">
                        <Text fontSize="sm" color="orange.700">
                          Промокод не найден (возможно, был удален)
                        </Text>
                      </Box>
                    )}
                  </VStack>
                </CardBody>
              </Card>
            )}

            {/* Предупреждения */}
            {!data.confirmed && data.paid && (
              <Box p={3} bg="yellow.50" borderRadius="md" borderLeft="4px solid" borderLeftColor="yellow.400">
                <Text fontSize="sm" color="yellow.700">
                  ⚠️ Бронирование оплачено, но требует подтверждения администратора
                </Text>
              </Box>
            )}

            {!data.paid && (
              <Box p={3} bg="red.50" borderRadius="md" borderLeft="4px solid" borderLeftColor="red.400">
                <Text fontSize="sm" color="red.700">
                  ❌ Бронирование не оплачено. Клиент может не иметь доступа к услуге.
                </Text>
              </Box>
            )}

          </VStack>
        </ModalBody>

        <ModalFooter p={4}>
          <VStack spacing={2} width="100%">
            {/* Первый ряд - основные действия с бронированием */}
            {(!data.confirmed || data.confirmed || error) && (
              <HStack spacing={2} width="100%" justify="center" flexWrap="wrap">
                {/* Кнопка редактирования */}
                {!isEditing && !loading && !error && (currentAdmin?.role === 'super_admin' || currentAdmin?.permissions?.includes('edit_bookings')) && (
                  <Button
                    leftIcon={<FiEdit2 />}
                    colorScheme="blue"
                    variant="outline"
                    size="sm"
                    onClick={handleStartEdit}
                    flex={1}
                    maxW="150px"
                  >
                    Редактировать
                  </Button>
                )}

                {/* Кнопка подтверждения */}
                {!data.confirmed && (currentAdmin?.role === 'super_admin' || currentAdmin?.permissions?.includes('edit_bookings')) && (
                  <Button
                    leftIcon={<FiCheck />}
                    colorScheme="green"
                    size="sm"
                    onClick={handleConfirmBooking}
                    isLoading={actionLoading.confirm}
                    loadingText="Подтверждение..."
                    flex={1}
                    maxW="150px"
                  >
                    Подтвердить
                  </Button>
                )}

                {/* Кнопка отмены бронирования */}
                {data.confirmed && (currentAdmin?.role === 'super_admin' || currentAdmin?.permissions?.includes('edit_bookings')) && (
                  <Button
                    leftIcon={<FiX />}
                    colorScheme="red"
                    variant="outline"
                    size="sm"
                    onClick={handleCancelBooking}
                    isLoading={actionLoading.cancel}
                    loadingText="Отмена..."
                    flex={1}
                    maxW="150px"
                  >
                    Отменить бронь
                  </Button>
                )}

                {/* Кнопка повтора при ошибке */}
                {error && (
                  <Button
                    leftIcon={<FiRefreshCw />}
                    colorScheme="red"
                    variant="outline"
                    size="sm"
                    onClick={handleRetry}
                    flex={1}
                    maxW="150px"
                  >
                    Повторить ({retryCount})
                  </Button>
                )}
              </HStack>
            )}

            {/* Второй ряд - платежные операции */}
            {!data.paid && (
              <HStack spacing={2} width="100%" justify="center" flexWrap="wrap">
                {/* Кнопка отметки об оплате */}
                {(currentAdmin?.role === 'super_admin' || currentAdmin?.permissions?.includes('edit_bookings')) && (
                  <Button
                    leftIcon={<FiDollarSign />}
                    colorScheme="teal"
                    variant="outline"
                    size="sm"
                    onClick={handleMarkAsPaid}
                    isLoading={actionLoading.markPaid}
                    loadingText="Обновление..."
                    flex={1}
                    maxW="200px"
                  >
                    Оплачено
                  </Button>
                )}

                {/* Кнопка "Без оплаты" */}
                {(currentAdmin?.role === 'super_admin' || currentAdmin?.permissions?.includes('edit_bookings')) && (
                  <Button
                    leftIcon={<FiCheck />}
                    colorScheme="purple"
                    variant="outline"
                    size="sm"
                    onClick={handleMarkAsFree}
                    isLoading={actionLoading.markFree}
                    loadingText="Обновление..."
                    flex={1}
                    maxW="200px"
                  >
                    Без оплаты
                  </Button>
                )}

                {/* Кнопка отправки платежной ссылки */}
                {data.confirmed && tariff.purpose === 'meeting_room' && (currentAdmin?.role === 'super_admin' || currentAdmin?.permissions?.includes('edit_bookings')) && (
                  <Button
                    leftIcon={<FiSend />}
                    colorScheme="blue"
                    size="sm"
                    onClick={handleSendPaymentLink}
                    isLoading={actionLoading.sendLink}
                    loadingText="Отправка..."
                    flex={1}
                    maxW="240px"
                  >
                    Отправить ссылку на оплату
                  </Button>
                )}
              </HStack>
            )}

            {/* Второй ряд - основные кнопки */}
            <HStack spacing={2} width="100%" justify="center">
              <Button colorScheme="blue" onClick={onClose} size="sm">
                Закрыть
              </Button>

              {user.username && (
                <Link href={getTelegramUrl(user.username)} isExternal>
                  <Button leftIcon={<FiMessageCircle />} colorScheme="purple" variant="outline" size="sm">
                    Telegram
                  </Button>
                </Link>
              )}

              {error && (
                <Button leftIcon={<FiAlertTriangle />} variant="outline" onClick={debugBooking} size="sm">
                  Отладка
                </Button>
              )}
            </HStack>
          </VStack>
        </ModalFooter>
      </ModalContent>
    </Modal>
  );
};

export default BookingDetailModal;