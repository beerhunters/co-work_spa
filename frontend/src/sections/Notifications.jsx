import React, { useState, useMemo } from 'react';
import {
  Box,
  Card,
  CardHeader,
  CardBody,
  Heading,
  VStack,
  HStack,
  Text,
  Badge,
  Button,
  ButtonGroup,
  Select,
  Input,
  InputGroup,
  InputLeftElement,
  useToast,
  Alert,
  AlertIcon,
  AlertDescription,
  useDisclosure,
  AlertDialog,
  AlertDialogBody,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogContent,
  AlertDialogOverlay,
  Spinner,
  Flex,
  IconButton,
  Tooltip
} from '@chakra-ui/react';
import {
  FiSearch,
  FiCheckCircle,
  FiTrash2,
  FiChevronLeft,
  FiChevronRight,
  FiUser,
  FiCalendar,
  FiMessageSquare,
  FiExternalLink
} from 'react-icons/fi';
import { sizes, styles, colors, getStatusColor } from '../styles/styles';
import { notificationApi } from '../utils/api';

const Notifications = ({
  notifications,
  openDetailModal,
  setSection,
  onRefresh
}) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('all'); // all, read, unread
  const [currentPage, setCurrentPage] = useState(1);
  const [itemsPerPage, setItemsPerPage] = useState(20);
  const [isMarkingAll, setIsMarkingAll] = useState(false);
  const [isClearing, setIsClearing] = useState(false);
  const { isOpen: clearDialogOpen, onOpen: openClearDialog, onClose: closeClearDialog } = useDisclosure();
  const toast = useToast();
  const cancelRef = React.useRef();

  // Фильтрация и поиск
  const filteredNotifications = useMemo(() => {
    let filtered = notifications;

    // Фильтр по статусу
    if (statusFilter === 'read') {
      filtered = filtered.filter(n => n.is_read);
    } else if (statusFilter === 'unread') {
      filtered = filtered.filter(n => !n.is_read);
    }

    // Поиск по тексту
    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase().trim();
      filtered = filtered.filter(n =>
        n.message.toLowerCase().includes(query)
      );
    }

    return filtered;
  }, [notifications, searchQuery, statusFilter]);

  // Пагинация
  const totalPages = Math.ceil(filteredNotifications.length / itemsPerPage);
  const startIndex = (currentPage - 1) * itemsPerPage;
  const endIndex = startIndex + itemsPerPage;
  const currentNotifications = filteredNotifications.slice(startIndex, endIndex);

  // Сброс на первую страницу при изменении фильтров
  React.useEffect(() => {
    setCurrentPage(1);
  }, [searchQuery, statusFilter]);

  const handlePageChange = (newPage) => {
    setCurrentPage(Math.max(1, Math.min(newPage, totalPages)));
  };

  const getNotificationIcon = (notification) => {
    if (notification.ticket_id) return FiMessageSquare;
    if (notification.booking_id) return FiCalendar;
    if (notification.user_id) return FiUser;
    return FiExternalLink;
  };

  const getNotificationIconColor = (notification) => {
    if (notification.ticket_id) return 'orange.500';
    if (notification.booking_id) return 'blue.500';
    if (notification.user_id) return 'green.500';
    return 'gray.500';
  };

  const handleNotificationClick = async (notification) => {
    try {
      // Помечаем как прочитанное
      if (!notification.is_read) {
        await notificationApi.markRead(notification.id);
        await onRefresh();
      }

      // Навигация к связанному объекту
      if (notification.ticket_id) {
        // Переходим к тикетам и открываем конкретный тикет
        setSection('tickets');
        // Здесь можно добавить логику для автоматического открытия тикета
        // openDetailModal(ticket, 'ticket') после получения данных тикета
      } else if (notification.booking_id) {
        setSection('bookings');
      } else if (notification.user_id) {
        setSection('users');
      } else if (notification.target_url) {
        const urlParts = notification.target_url.split('/');
        if (urlParts.length >= 2) {
          setSection(urlParts[1]);
        }
      }

      toast({
        title: 'Переход выполнен',
        description: 'Переходим к связанному событию',
        status: 'info',
        duration: 2000,
        isClosable: true,
      });

    } catch (error) {
      console.error('Ошибка при обработке уведомления:', error);
      toast({
        title: 'Ошибка',
        description: 'Не удалось обработать уведомление',
        status: 'error',
        duration: 3000,
        isClosable: true,
      });
    }
  };

  const handleMarkAllRead = async () => {
    setIsMarkingAll(true);
    try {
      await notificationApi.markAllRead();
      await onRefresh();

      toast({
        title: 'Успешно',
        description: 'Все уведомления помечены как прочитанные',
        status: 'success',
        duration: 3000,
        isClosable: true,
      });
    } catch (error) {
      console.error('Ошибка при пометке всех уведомлений:', error);
      toast({
        title: 'Ошибка',
        description: 'Не удалось пометить уведомления',
        status: 'error',
        duration: 3000,
        isClosable: true,
      });
    } finally {
      setIsMarkingAll(false);
    }
  };

  const handleClearAll = async () => {
    setIsClearing(true);
    try {
      await notificationApi.clearAll();
      await onRefresh();

      toast({
        title: 'Успешно',
        description: 'Все уведомления удалены',
        status: 'success',
        duration: 3000,
        isClosable: true,
      });
    } catch (error) {
      console.error('Ошибка при очистке уведомлений:', error);

      let errorMessage = 'Не удалось очистить уведомления';
      let toastStatus = 'error';
      let duration = 5000;

      if (error.response?.status === 503) {
        errorMessage = error.response.data.detail || 'Временная проблема с базой данных';
        toastStatus = 'warning';
        duration = 8000;
      } else if (error.response?.data?.detail) {
        errorMessage = error.response.data.detail;
      }

      toast({
        title: toastStatus === 'warning' ? 'Предупреждение' : 'Ошибка',
        description: errorMessage,
        status: toastStatus,
        duration: duration,
        isClosable: true,
      });
    } finally {
      setIsClearing(false);
      closeClearDialog();
    }
  };

  const unreadCount = notifications.filter(n => !n.is_read).length;

  return (
    <>
      <Box p={sizes.content.padding} bg="gray.50" minH={sizes.content.minHeight}>
        <Card borderRadius={styles.card.borderRadius} boxShadow={styles.card.boxShadow}>
          <CardHeader>
            <VStack align="stretch" spacing={4}>
              <HStack justify="space-between">
                <Heading size="md">
                  Уведомления {unreadCount > 0 && (
                    <Badge colorScheme="red" ml={2}>{unreadCount} новых</Badge>
                  )}
                </Heading>
                <HStack spacing={2}>
                  <Button
                    leftIcon={<FiCheckCircle />}
                    colorScheme="green"
                    variant="outline"
                    size="sm"
                    onClick={handleMarkAllRead}
                    isLoading={isMarkingAll}
                    loadingText="Обработка..."
                    isDisabled={unreadCount === 0}
                  >
                    Отметить все как прочитанные
                  </Button>
                  <Button
                    leftIcon={<FiTrash2 />}
                    colorScheme="red"
                    variant="outline"
                    size="sm"
                    onClick={openClearDialog}
                  >
                    Очистить все
                  </Button>
                </HStack>
              </HStack>

              {/* Фильтры и поиск */}
              <HStack spacing={4}>
                <InputGroup maxW="300px">
                  <InputLeftElement>
                    <FiSearch color="gray" />
                  </InputLeftElement>
                  <Input
                    placeholder="Поиск по тексту уведомления..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                  />
                </InputGroup>

                <Select
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                  maxW="200px"
                >
                  <option value="all">Все уведомления</option>
                  <option value="unread">Только непрочитанные</option>
                  <option value="read">Только прочитанные</option>
                </Select>

                <Select
                  value={itemsPerPage}
                  onChange={(e) => setItemsPerPage(Number(e.target.value))}
                  maxW="120px"
                >
                  <option value={10}>10 на странице</option>
                  <option value={20}>20 на странице</option>
                  <option value={50}>50 на странице</option>
                </Select>
              </HStack>

              {/* Статистика */}
              <Alert status="info" bg="blue.50" borderRadius="md">
                <AlertIcon />
                <AlertDescription>
                  Всего уведомлений: {notifications.length} |
                  Найдено: {filteredNotifications.length} |
                  Непрочитанных: {unreadCount}
                </AlertDescription>
              </Alert>
            </VStack>
          </CardHeader>

          <CardBody>
            <VStack align="stretch" spacing={2}>
              {currentNotifications.length === 0 ? (
                <Box textAlign="center" py={8}>
                  <Text color="gray.500">
                    {searchQuery || statusFilter !== 'all'
                      ? 'Уведомлений по заданным критериям не найдено'
                      : 'Уведомлений пока нет'
                    }
                  </Text>
                </Box>
              ) : (
                currentNotifications.map(notification => {
                  const IconComponent = getNotificationIcon(notification);
                  const iconColor = getNotificationIconColor(notification);

                  return (
                    <Box
                      key={notification.id}
                      p={styles.listItem.padding}
                      borderRadius={styles.listItem.borderRadius}
                      border={styles.listItem.border}
                      borderColor={styles.listItem.borderColor}
                      bg={notification.is_read ? colors.notification.readBg : colors.notification.unreadBg}
                      cursor="pointer"
                      _hover={styles.listItem.hover}
                      transition={styles.listItem.transition}
                      onClick={() => handleNotificationClick(notification)}
                      borderLeft={!notification.is_read ? "4px solid" : "none"}
                      borderLeftColor={!notification.is_read ? "blue.400" : "transparent"}
                    >
                      <HStack justify="space-between" align="start">
                        <HStack spacing={3} align="start" flex={1}>
                          <Box pt={1}>
                            <IconComponent size={16} color={iconColor} />
                          </Box>
                          <VStack align="start" spacing={1} flex={1}>
                            <Text
                              fontSize="md"
                              fontWeight={notification.is_read ? "normal" : "semibold"}
                              lineHeight="1.4"
                            >
                              {notification.message}
                            </Text>
                            <HStack spacing={3} fontSize="sm" color="gray.600">
                              <Text>
                                {new Date(notification.created_at).toLocaleString('ru-RU')}
                              </Text>
                              {notification.ticket_id && (
                                <Badge colorScheme="orange" fontSize="xs">
                                  Тикет #{notification.ticket_id}
                                </Badge>
                              )}
                              {notification.booking_id && (
                                <Badge colorScheme="blue" fontSize="xs">
                                  Бронь #{notification.booking_id}
                                </Badge>
                              )}
                              {notification.user_id && !notification.ticket_id && !notification.booking_id && (
                                <Badge colorScheme="green" fontSize="xs">
                                  Пользователь
                                </Badge>
                              )}
                            </HStack>
                          </VStack>
                        </HStack>
                        <VStack spacing={1} align="end">
                          <Badge
                            colorScheme={getStatusColor(notification.is_read ? 'read' : 'unread')}
                            fontSize="xs"
                          >
                            {notification.is_read ? 'Прочитано' : 'Новое'}
                          </Badge>
                          <FiExternalLink size={12} color="gray" />
                        </VStack>
                      </HStack>
                    </Box>
                  );
                })
              )}
            </VStack>

            {/* Пагинация */}
            {totalPages > 1 && (
              <Flex justify="center" align="center" mt={6} gap={2}>
                <IconButton
                  icon={<FiChevronLeft />}
                  variant="outline"
                  size="sm"
                  onClick={() => handlePageChange(currentPage - 1)}
                  isDisabled={currentPage === 1}
                  aria-label="Предыдущая страница"
                />

                <HStack spacing={1}>
                  {Array.from({ length: Math.min(totalPages, 7) }, (_, i) => {
                    let pageNum;
                    if (totalPages <= 7) {
                      pageNum = i + 1;
                    } else if (currentPage <= 4) {
                      pageNum = i + 1;
                    } else if (currentPage >= totalPages - 3) {
                      pageNum = totalPages - 6 + i;
                    } else {
                      pageNum = currentPage - 3 + i;
                    }

                    return (
                      <Button
                        key={pageNum}
                        size="sm"
                        variant={currentPage === pageNum ? "solid" : "outline"}
                        colorScheme={currentPage === pageNum ? "blue" : "gray"}
                        onClick={() => handlePageChange(pageNum)}
                        minW="40px"
                      >
                        {pageNum}
                      </Button>
                    );
                  })}
                </HStack>

                <IconButton
                  icon={<FiChevronRight />}
                  variant="outline"
                  size="sm"
                  onClick={() => handlePageChange(currentPage + 1)}
                  isDisabled={currentPage === totalPages}
                  aria-label="Следующая страница"
                />

                <Text fontSize="sm" color="gray.600" ml={4}>
                  Страница {currentPage} из {totalPages}
                </Text>
              </Flex>
            )}
          </CardBody>
        </Card>
      </Box>

      {/* Диалог подтверждения очистки */}
      <AlertDialog
        isOpen={clearDialogOpen}
        leastDestructiveRef={cancelRef}
        onClose={closeClearDialog}
      >
        <AlertDialogOverlay>
          <AlertDialogContent>
            <AlertDialogHeader fontSize="lg" fontWeight="bold">
              Очистить все уведомления
            </AlertDialogHeader>

            <AlertDialogBody>
              Вы уверены, что хотите удалить <strong>все уведомления</strong>?
              <br />
              <br />
              <Text fontSize="sm" color="gray.600">
                Это действие нельзя отменить. Будут удалены все {notifications.length} уведомлений,
                включая {unreadCount} непрочитанных.
              </Text>
            </AlertDialogBody>

            <AlertDialogFooter>
              <Button ref={cancelRef} onClick={closeClearDialog}>
                Отмена
              </Button>
              <Button
                colorScheme="red"
                onClick={handleClearAll}
                ml={3}
                isLoading={isClearing}
                loadingText="Удаление..."
              >
                Удалить все
              </Button>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialogOverlay>
      </AlertDialog>
    </>
  );
};

export default Notifications;