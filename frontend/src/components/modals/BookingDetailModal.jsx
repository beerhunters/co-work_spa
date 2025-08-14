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
  AlertDescription
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
  FiInfo
} from 'react-icons/fi';
import { getStatusColor } from '../../styles/styles';
import { bookingApi } from '../../utils/api';

const BookingDetailModal = ({ isOpen, onClose, booking, onUpdate }) => {
  const [detailedBooking, setDetailedBooking] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [retryCount, setRetryCount] = useState(0);
  const [actionLoading, setActionLoading] = useState({ confirm: false, markPaid: false });
  const toast = useToast();

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

      // Обновляем локальные данные
      if (detailedBooking) {
        setDetailedBooking(prev => ({ ...prev, confirmed: true }));
      }

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

      // Обновляем локальные данные
      if (detailedBooking) {
        setDetailedBooking(prev => ({ ...prev, paid: true }));
      }

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
            {error && (
              <Tooltip label="Перезагрузить данные">
                <Button size="sm" variant="ghost" onClick={handleRetry}>
                  <FiRefreshCw />
                </Button>
              </Tooltip>
            )}
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
            {/* Первый ряд - кнопки действий */}
            {(!data.confirmed || !data.paid) && (
              <HStack spacing={2} width="100%" justify="center">
                {!data.confirmed && (
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

                {!data.paid && (
                  <Button
                    leftIcon={<FiDollarSign />}
                    colorScheme="teal"
                    variant="outline"
                    size="sm"
                    onClick={handleMarkAsPaid}
                    isLoading={actionLoading.markPaid}
                    loadingText="Обновление..."
                    flex={1}
                    maxW="150px"
                  >
                    Оплачено
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