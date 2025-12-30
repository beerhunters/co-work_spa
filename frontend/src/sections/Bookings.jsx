import React, { useState, useMemo, useEffect } from 'react';
import {
  Box,
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  Badge,
  Text,
  useColorModeValue,
  VStack,
  HStack,
  Icon,
  Input,
  InputGroup,
  InputLeftElement,
  Button,
  Flex,
  Select,
  Tooltip,
  IconButton,
  useToast,
  AlertDialog,
  AlertDialogBody,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogContent,
  AlertDialogOverlay,
  useDisclosure,
  Checkbox,
  Heading,
  Card,
  CardBody,
  SimpleGrid,
  Stat,
  StatLabel,
  StatNumber,
  StatHelpText,
  Divider,
  Spinner,
  Alert,
  AlertIcon,
  AlertDescription
} from '@chakra-ui/react';
import {
  FiSearch,
  FiChevronLeft,
  FiChevronRight,
  FiCheck,
  FiX,
  FiTrash2,
  FiCheckSquare,
  FiSquare,
  FiDownload,
  FiPlus,
  FiCalendar,
  FiCreditCard,
  FiAlertCircle
} from 'react-icons/fi';
import { getStatusColor } from '../styles/styles';
import { bookingApi } from '../utils/api';
import { TableSkeleton } from '../components/LoadingSkeletons';
import { PaginationControls } from '../components/PaginationControls';
import { BulkActionsBar } from '../components/BulkActionsBar';
import CreateBookingModal from '../components/modals/CreateBookingModal';

const Bookings = ({
  bookings,
  bookingsMeta,
  openDetailModal,
  onRefresh,
  onFiltersChange,
  isLoading = false,
  currentAdmin, // Добавляем текущего администратора
  tariffs = [], // Добавляем список тарифов для фильтра
  users = [] // Добавляем список пользователей для создания бронирований
}) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [tariffFilter, setTariffFilter] = useState('all');
  const [currentPage, setCurrentPage] = useState(1);
  const [itemsPerPage, setItemsPerPage] = useState(20);
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [isDeleting, setIsDeleting] = useState(false);
  // Массовый выбор
  const [isSelectionMode, setIsSelectionMode] = useState(false);
  const [selectedBookings, setSelectedBookings] = useState(new Set());
  const [isExporting, setIsExporting] = useState(false);
  const [isCanceling, setIsCanceling] = useState(false);

  // Создание бронирования
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);

  const { isOpen: isDeleteOpen, onOpen: onDeleteOpen, onClose: onDeleteClose } = useDisclosure();
  const { isOpen: isBulkDeleteOpen, onOpen: onBulkDeleteOpen, onClose: onBulkDeleteClose } = useDisclosure();
  const cancelRef = React.useRef();
  const toast = useToast();

  const tableBg = useColorModeValue('white', 'gray.800');
  const borderColor = useColorModeValue('gray.200', 'gray.600');

  // Проверка прав на удаление бронирований
  const canDeleteBookings = currentAdmin?.role === 'super_admin' ||
    (currentAdmin?.permissions && currentAdmin.permissions.includes('delete_bookings'));

  // Проверяем сохраненный ID бронирования при инициализации
  useEffect(() => {
    const savedBookingId = localStorage.getItem('bookings_filter_id');
    if (savedBookingId) {
      setSearchQuery(savedBookingId);
      localStorage.removeItem('bookings_filter_id'); // Очищаем после использования
      
      // Ищем бронирование в текущем списке
      const booking = bookings.find(b => b.id.toString() === savedBookingId);
      if (booking) {
        // Небольшая задержка для того чтобы фильтр сработал
        setTimeout(() => {
          openDetailModal(booking, 'booking');
        }, 100);
      }
    }
  }, [bookings, openDetailModal]);

  // Эффект для отправки фильтров в родительский компонент
  useEffect(() => {
    const params = {
      page: currentPage,
      per_page: itemsPerPage
    };

    // Добавляем фильтры только если они не дефолтные
    if (statusFilter && statusFilter !== 'all') {
      params.status_filter = statusFilter;
    }

    if (tariffFilter && tariffFilter !== 'all') {
      params.tariff_filter = tariffFilter;
    }

    if (searchQuery && searchQuery.trim()) {
      params.user_query = searchQuery.trim();
    }

    console.log('Отправляем параметры фильтрации:', params);
    console.log('Текущее состояние фильтров:', {
      searchQuery,
      statusFilter,
      tariffFilter,
      currentPage,
      itemsPerPage
    });
    console.log('Доступные тарифы:', tariffs);
    
    if (tariffFilter && tariffFilter !== 'all') {
      console.log('Активный фильтр по тарифу:', tariffFilter);
      const selectedTariff = tariffs.find(t => t.id.toString() === tariffFilter.toString());
      console.log('Выбранный тариф:', selectedTariff);
    }

    if (onFiltersChange) {
      onFiltersChange(params);
    }
  }, [currentPage, itemsPerPage, statusFilter, tariffFilter, searchQuery, onFiltersChange]);

  // Сброс на первую страницу при изменении фильтров
  useEffect(() => {
    if (currentPage !== 1) {
      setCurrentPage(1);
    }
  }, [statusFilter, tariffFilter, searchQuery, itemsPerPage]);

  // Функция сброса всех фильтров
  const handleResetFilters = () => {
    console.log('Сброс фильтров к изначальным значениям');

    setSearchQuery('');
    setStatusFilter('all');
    setTariffFilter('all');
    setCurrentPage(1);
    setItemsPerPage(20);

    // Принудительно отправляем дефолтные параметры
    const defaultParams = {
      page: 1,
      per_page: 20
    };

    console.log('Принудительно отправляем дефолтные параметры:', defaultParams);

    if (onFiltersChange) {
      onFiltersChange(defaultParams);
    }
  };

  // Проверка, активны ли какие-либо фильтры
  const hasActiveFilters = searchQuery.trim() || statusFilter !== 'all' || tariffFilter !== 'all';

  const formatDateTime = (dateString) => {
    try {
      return new Date(dateString).toLocaleString('ru-RU', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      });
    } catch {
      return 'Неизвестно';
    }
  };

  // Используем данные из props (они уже отфильтрованы на сервере)
  const displayedBookings = bookings || [];
  const totalPages = bookingsMeta?.total_pages || 1;
  const totalCount = bookingsMeta?.total_count || 0;

  const handlePageChange = (newPage) => {
    const page = Math.max(1, Math.min(newPage, totalPages));
    setCurrentPage(page);
  };

  const handleSearchSubmit = (e) => {
    e.preventDefault();
    // Поиск будет выполнен через useEffect
  };

  // Обработчик удаления бронирования
  const handleDeleteBooking = (booking) => {
    setDeleteTarget(booking);
    onDeleteOpen();
  };

  const confirmDeleteBooking = async () => {
    if (!deleteTarget) return;

    setIsDeleting(true);
    try {
      const result = await bookingApi.delete(deleteTarget.id);

      // Основное уведомление об успехе
      toast({
        title: 'Успешно',
        description: 'Бронирование удалено',
        status: 'success',
        duration: 3000,
        isClosable: true,
      });

      // Дополнительное предупреждение если была проблема с Rubitime
      if (result.showRubitimeWarning) {
        toast({
          title: 'Предупреждение Rubitime',
          description: result.rubitimeWarningMessage,
          status: 'warning',
          duration: 7000,
          isClosable: true,
        });
      }

      // Обновляем данные
      if (onRefresh) {
        await onRefresh();
      }

      // Закрываем диалог
      onDeleteClose();
      setDeleteTarget(null);

    } catch (error) {
      console.error('Ошибка удаления бронирования:', error);

      let errorMessage = 'Не удалось удалить бронирование';
      if (error.response?.status === 403) {
        errorMessage = 'У вас нет прав для удаления бронирований';
      } else if (error.response?.status === 404) {
        errorMessage = 'Бронирование не найдено';
      } else if (error.response?.data?.detail) {
        errorMessage = error.response.data.detail;
      }

      toast({
        title: 'Ошибка',
        description: errorMessage,
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    } finally {
      setIsDeleting(false);
    }
  };

  // Функции массового выбора
  const handleToggleSelectionMode = () => {
    setIsSelectionMode(!isSelectionMode);
    setSelectedBookings(new Set());
  };

  // Обработчик успешного создания бронирования
  const handleCreateSuccess = (newBooking) => {
    // Обновить список бронирований
    onRefresh();

    // Закрыть модальное окно создания
    setIsCreateModalOpen(false);

    // Опционально: открыть детали созданного бронирования
    if (openDetailModal && newBooking) {
      openDetailModal(newBooking);
    }
  };

  const handleSelectBooking = (bookingId, isSelected) => {
    const newSelected = new Set(selectedBookings);
    if (isSelected) {
      newSelected.add(bookingId);
    } else {
      newSelected.delete(bookingId);
    }
    setSelectedBookings(newSelected);
  };

  // Выбрать все бронирования на текущей странице
  const handleSelectAllOnPage = () => {
    const allIds = new Set(displayedBookings.map(booking => booking.id));
    setSelectedBookings(allIds);
  };

  // Снять выбор со всех бронирований
  const handleDeselectAll = () => {
    setSelectedBookings(new Set());
  };

  const handleBulkDelete = async () => {
    const selectedArray = Array.from(selectedBookings);
    setIsDeleting(true);

    try {
      const response = await bookingApi.bulkDelete(selectedArray);

      toast({
        title: 'Успешно',
        description: `Удалено бронирований: ${response.deleted_count}`,
        status: 'success',
        duration: 3000,
        isClosable: true,
      });

      setSelectedBookings(new Set());
      setIsSelectionMode(false);

      if (onRefresh) {
        await onRefresh();
      }
    } catch (error) {
      toast({
        title: 'Ошибка',
        description: 'Не удалось удалить выбранные бронирования',
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    } finally {
      setIsDeleting(false);
      onBulkDeleteClose();
    }
  };

  const handleBulkCancel = async () => {
    const selectedArray = Array.from(selectedBookings);
    setIsCanceling(true);

    try {
      const response = await bookingApi.bulkCancel(selectedArray);

      toast({
        title: 'Успешно',
        description: `Отменено бронирований: ${response.updated_count}`,
        status: 'success',
        duration: 3000,
        isClosable: true,
      });

      setSelectedBookings(new Set());
      setIsSelectionMode(false);

      if (onRefresh) {
        await onRefresh();
      }
    } catch (error) {
      toast({
        title: 'Ошибка',
        description: 'Не удалось отменить выбранные бронирования',
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    } finally {
      setIsCanceling(false);
    }
  };

  const handleBulkExport = async () => {
    const selectedArray = Array.from(selectedBookings);
    setIsExporting(true);

    try {
      await bookingApi.bulkExport(selectedArray);

      toast({
        title: 'Экспорт завершен',
        description: `Экспортировано бронирований: ${selectedArray.length}`,
        status: 'success',
        duration: 3000,
        isClosable: true,
      });
    } catch (error) {
      toast({
        title: 'Ошибка',
        description: 'Не удалось экспортировать выбранные бронирования',
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    } finally {
      setIsExporting(false);
    }
  };

  const isAllSelected = displayedBookings.length > 0 && selectedBookings.size === displayedBookings.length;
  const isIndeterminate = selectedBookings.size > 0 && selectedBookings.size < displayedBookings.length;

  // Статистика для отображения
  const stats = useMemo(() => {
    const total = totalCount;
    const paid = displayedBookings.filter(b => b.paid).length;
    const unpaid = displayedBookings.filter(b => !b.paid).length;
    const confirmed = displayedBookings.filter(b => b.confirmed).length;
    const totalAmount = displayedBookings.reduce((sum, b) => sum + (b.amount || 0), 0);
    const paidAmount = displayedBookings.filter(b => b.paid).reduce((sum, b) => sum + (b.amount || 0), 0);

    return { total, paid, unpaid, confirmed, totalAmount, paidAmount };
  }, [displayedBookings, totalCount]);

  // Loading state
  if (isLoading && displayedBookings.length === 0) {
    return (
      <Flex justify="center" align="center" h="400px" direction="column" gap={4}>
        <Spinner size="xl" color="blue.500" thickness="4px" />
        <Text color="gray.500">Загрузка бронирований...</Text>
      </Flex>
    );
  }

  return (
    <Box p={6}>
      <VStack spacing={6} align="stretch">
        {/* Заголовок */}
        <Flex justify="space-between" align="center">
          <Box>
            <Heading size="lg" mb={2}>
              <Icon as={FiCalendar} color="blue.500" mr={3} />
              Бронирования
            </Heading>
            <Text color="gray.600">
              Управление бронированиями рабочих мест и офисов
            </Text>
          </Box>

          <HStack spacing={3}>
              {canDeleteBookings && (
                <Button
                  size="sm"
                  leftIcon={<Icon as={isSelectionMode ? FiSquare : FiCheckSquare} />}
                  onClick={handleToggleSelectionMode}
                  colorScheme={isSelectionMode ? "gray" : "purple"}
                  variant="outline"
                  isDisabled={isLoading || displayedBookings.length === 0}
                >
                  {isSelectionMode ? 'Отменить' : 'Выбрать'}
                </Button>
              )}
              <Button
                size="sm"
                leftIcon={<Icon as={FiPlus} />}
                onClick={() => setIsCreateModalOpen(true)}
                colorScheme="green"
                variant="solid"
              >
                Создать бронирование
              </Button>
              <Button
                size="sm"
                onClick={onRefresh}
                colorScheme="blue"
                variant="outline"
                isLoading={isLoading}
                loadingText="Загрузка..."
              >
                Обновить
              </Button>
            </HStack>
        </Flex>

        {/* Statistics Cards */}
        {displayedBookings.length > 0 && (
          <SimpleGrid columns={{ base: 1, md: 5 }} spacing={4}>
            <Card>
              <CardBody>
                <Stat>
                  <StatLabel>Всего бронирований</StatLabel>
                  <StatNumber color="blue.500">{stats.total}</StatNumber>
                  <StatHelpText>
                    <Icon as={FiCalendar} mr={1} />
                    В системе
                  </StatHelpText>
                </Stat>
              </CardBody>
            </Card>

            <Card>
              <CardBody>
                <Stat>
                  <StatLabel>Оплачено</StatLabel>
                  <StatNumber color="green.500">{stats.paid}</StatNumber>
                  <StatHelpText>
                    <Icon as={FiCreditCard} mr={1} />
                    На текущей странице
                  </StatHelpText>
                </Stat>
              </CardBody>
            </Card>

            <Card>
              <CardBody>
                <Stat>
                  <StatLabel>Не оплачено</StatLabel>
                  <StatNumber color="orange.500">{stats.unpaid}</StatNumber>
                  <StatHelpText>
                    <Icon as={FiAlertCircle} mr={1} />
                    Ожидают оплаты
                  </StatHelpText>
                </Stat>
              </CardBody>
            </Card>

            <Card>
              <CardBody>
                <Stat>
                  <StatLabel>Подтверждено</StatLabel>
                  <StatNumber color="purple.500">{stats.confirmed}</StatNumber>
                  <StatHelpText>
                    <Icon as={FiCheck} mr={1} />
                    Администратором
                  </StatHelpText>
                </Stat>
              </CardBody>
            </Card>

            <Card>
              <CardBody>
                <Stat>
                  <StatLabel>Сумма (оплачено)</StatLabel>
                  <StatNumber color="green.600">{stats.paidAmount.toLocaleString()} ₽</StatNumber>
                  <StatHelpText>
                    <Icon as={FiCreditCard} mr={1} />
                    На странице
                  </StatHelpText>
                </Stat>
              </CardBody>
            </Card>
          </SimpleGrid>
        )}

        <Divider />

        {/* Фильтры */}
        <VStack align="stretch" spacing={4}>
          <HStack spacing={4} wrap="wrap">
            {/* Поиск по пользователю */}
            <form onSubmit={handleSearchSubmit}>
              <InputGroup maxW="300px">
                <InputLeftElement pointerEvents="none">
                  <Icon as={FiSearch} color="gray.400" />
                </InputLeftElement>
                <Input
                  placeholder="Поиск по ID, ФИО или тарифу..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                />
              </InputGroup>
            </form>

            {/* Фильтр по статусу */}
            <Select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              maxW="200px"
            >
              <option value="all">Все бронирования</option>
              <option value="paid">Только оплаченные</option>
              <option value="unpaid">Неоплаченные</option>
              <option value="confirmed">Подтвержденные</option>
              <option value="pending">Ожидающие</option>
            </Select>

            {/* Фильтр по тарифу */}
            <Select
              value={tariffFilter}
              onChange={(e) => setTariffFilter(e.target.value)}
              maxW="200px"
            >
              <option value="all">Все тарифы</option>
              {tariffs.map(tariff => (
                <option key={tariff.id} value={tariff.id}>
                  {tariff.name}
                </option>
              ))}
            </Select>

            {/* Кнопка сброса фильтров */}
            {hasActiveFilters && (
              <Button
                size="sm"
                variant="outline"
                colorScheme="gray"
                onClick={handleResetFilters}
                isDisabled={isLoading}
              >
                Сбросить фильтры
              </Button>
            )}
          </HStack>

          {/* Панель массовых действий */}
          {isSelectionMode && (
            <BulkActionsBar
              selectedCount={selectedBookings.size}
              currentPageCount={displayedBookings.length}
              actions={[
                {
                  label: 'Удалить',
                  icon: FiTrash2,
                  onClick: onBulkDeleteOpen,
                  colorScheme: 'red',
                  showCount: true,
                  isLoading: isDeleting
                },
                {
                  label: 'Отменить',
                  icon: FiX,
                  onClick: handleBulkCancel,
                  colorScheme: 'orange',
                  showCount: true,
                  isLoading: isCanceling
                },
                {
                  label: 'Экспорт',
                  icon: FiDownload,
                  onClick: handleBulkExport,
                  colorScheme: 'green',
                  isLoading: isExporting
                }
              ]}
              onSelectAll={handleSelectAllOnPage}
              onDeselectAll={handleDeselectAll}
              isAllSelected={isAllSelected}
              isIndeterminate={isIndeterminate}
              entityName="бронирований"
            />
          )}
        </VStack>

        {/* Таблица бронирований */}
        {displayedBookings.length > 0 ? (
          <Card data-tour="bookings-list">
            <CardBody p={0}>
              <Box overflowX="auto">
                <Table variant="simple">
              <Thead bg={useColorModeValue('gray.50', 'gray.700')}>
                <Tr>
                  {isSelectionMode && <Th w="40px"></Th>}
                  <Th>ID</Th>
                  <Th>Пользователь</Th>
                  <Th>Название тарифа</Th>
                  <Th>Статусы</Th>
                  <Th isNumeric>Сумма</Th>
                  <Th>Дата создания</Th>
                  <Th>Действия</Th>
                </Tr>
              </Thead>
              <Tbody>
                {displayedBookings.map(booking => {
                  const isSelected = selectedBookings.has(booking.id);
                  
                  return (
                    <Tr
                      key={booking.id}
                      bg={isSelectionMode && isSelected ? useColorModeValue('purple.50', 'purple.900') : 'transparent'}
                      _hover={{
                        bg: isSelectionMode && isSelected 
                          ? useColorModeValue('purple.100', 'purple.800')
                          : useColorModeValue('gray.50', 'gray.700'),
                      }}
                      cursor={isSelectionMode ? "pointer" : "default"}
                      onClick={(e) => {
                        if (isSelectionMode) {
                          e.stopPropagation();
                          handleSelectBooking(booking.id, !isSelected);
                        }
                      }}
                    >
                      {isSelectionMode && (
                        <Td onClick={(e) => e.stopPropagation()}>
                          <Checkbox
                            isChecked={isSelected}
                            onChange={(e) => handleSelectBooking(booking.id, e.target.checked)}
                            colorScheme="purple"
                          />
                        </Td>
                      )}
                      <Td
                        fontWeight="semibold"
                        cursor="pointer"
                        onClick={(e) => {
                          if (isSelectionMode) {
                            e.stopPropagation();
                            handleSelectBooking(booking.id, !isSelected);
                          } else {
                            openDetailModal(booking, 'booking');
                          }
                        }}
                      >
                        #{booking.id}
                      </Td>

                    <Td
                      cursor="pointer"
                      onClick={(e) => {
                        if (isSelectionMode) {
                          e.stopPropagation();
                          handleSelectBooking(booking.id, !isSelected);
                        } else {
                          openDetailModal(booking, 'booking');
                        }
                      }}
                    >
                      <VStack align="start" spacing={0}>
                        <Text fontWeight="medium" fontSize="sm">
                          {booking.user?.full_name || 'Имя не указано'}
                        </Text>
                        {booking.user?.phone && (
                          <Text fontSize="xs" color="gray.500">
                            {booking.user.phone}
                          </Text>
                        )}
                      </VStack>
                    </Td>

                    <Td
                      cursor="pointer"
                      onClick={(e) => {
                        if (isSelectionMode) {
                          e.stopPropagation();
                          handleSelectBooking(booking.id, !isSelected);
                        } else {
                          openDetailModal(booking, 'booking');
                        }
                      }}
                    >
                      <Text fontWeight="medium" fontSize="md">
                        {booking.tariff?.name || `Тариф #${booking.tariff_id}`}
                      </Text>
                      {booking.tariff?.price && (
                        <Text fontSize="xs" color="gray.500">
                          Базовая цена: {booking.tariff.price.toLocaleString()} ₽
                        </Text>
                      )}
                    </Td>

                    <Td
                      data-tour="bookings-status"
                      cursor="pointer"
                      onClick={(e) => {
                        if (isSelectionMode) {
                          e.stopPropagation();
                          handleSelectBooking(booking.id, !isSelected);
                        } else {
                          openDetailModal(booking, 'booking');
                        }
                      }}
                    >
                      <VStack align="start" spacing={1}>
                        {booking.cancelled ? (
                          <Badge
                            colorScheme="red"
                            fontSize="sm"
                          >
                            <HStack spacing={1}>
                              <Icon as={FiX} />
                              <Text>Отменено</Text>
                            </HStack>
                          </Badge>
                        ) : (
                          <>
                            <Badge
                              colorScheme={getStatusColor(booking.paid ? 'paid' : 'unpaid')}
                              fontSize="sm"
                            >
                              {booking.paid ? (
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
                            <Badge
                              colorScheme={getStatusColor(booking.confirmed ? 'confirmed' : 'pending')}
                              fontSize="sm"
                            >
                              {booking.confirmed ? 'Подтверждено' : 'Ожидает'}
                            </Badge>
                          </>
                        )}
                      </VStack>
                    </Td>

                    <Td
                      isNumeric
                      cursor="pointer"
                      onClick={(e) => {
                        if (isSelectionMode) {
                          e.stopPropagation();
                          handleSelectBooking(booking.id, !isSelected);
                        } else {
                          openDetailModal(booking, 'booking');
                        }
                      }}
                    >
                      <HStack spacing={1} justify="flex-end">
                        <Text fontWeight="bold" color="green.500">
                          {booking.amount.toLocaleString()} ₽
                        </Text>
                      </HStack>
                    </Td>

                    <Td
                      cursor="pointer"
                      onClick={(e) => {
                        if (isSelectionMode) {
                          e.stopPropagation();
                          handleSelectBooking(booking.id, !isSelected);
                        } else {
                          openDetailModal(booking, 'booking');
                        }
                      }}
                    >
                      <Text fontSize="sm">
                        {formatDateTime(booking.created_at)}
                      </Text>
                    </Td>

                    <Td>
                      {canDeleteBookings && !isSelectionMode && (
                        <Tooltip label="Удалить бронирование">
                          <IconButton
                            icon={<FiTrash2 />}
                            size="sm"
                            variant="ghost"
                            colorScheme="red"
                            aria-label="Удалить бронирование"
                            onClick={(e) => {
                              e.stopPropagation();
                              handleDeleteBooking(booking);
                            }}
                          />
                        </Tooltip>
                      )}
                    </Td>
                  </Tr>
                  );
                })}
              </Tbody>
            </Table>
              </Box>
            </CardBody>
          </Card>
        ) : (
          <Card>
            <CardBody>
              <VStack spacing={4} py={10}>
                <Icon as={FiCalendar} boxSize={16} color="gray.300" />
                <VStack spacing={2}>
                  <Heading size="md" color="gray.600">
                    {hasActiveFilters ? 'Бронирования не найдены' : 'Пока нет бронирований'}
                  </Heading>
                  <Text color="gray.500" textAlign="center" maxW="500px">
                    {hasActiveFilters
                      ? 'По заданным фильтрам бронирования не найдены. Попробуйте изменить критерии поиска или сбросить все фильтры.'
                      : 'Когда пользователи начнут создавать бронирования, они появятся здесь. Вы также можете создать бронирование вручную.'}
                  </Text>
                </VStack>
                {hasActiveFilters && (
                  <Button
                    colorScheme="blue"
                    variant="outline"
                    onClick={handleResetFilters}
                  >
                    Сбросить фильтры
                  </Button>
                )}
              </VStack>
            </CardBody>
          </Card>
        )}

        {/* Пагинация */}
        <PaginationControls
          currentPage={currentPage}
          totalPages={totalPages}
          totalItems={totalCount}
          itemsPerPage={itemsPerPage}
          onPageChange={handlePageChange}
          onItemsPerPageChange={setItemsPerPage}
        />
      </VStack>

      {/* Диалог подтверждения удаления */}
      <AlertDialog
        isOpen={isDeleteOpen}
        leastDestructiveRef={cancelRef}
        onClose={onDeleteClose}
      >
        <AlertDialogOverlay>
          <AlertDialogContent>
            <AlertDialogHeader fontSize="lg" fontWeight="bold">
              <HStack>
                <Icon as={FiTrash2} color="red.500" />
                <Text>Удаление бронирования</Text>
              </HStack>
            </AlertDialogHeader>

            <AlertDialogBody>
              <VStack align="start" spacing={3}>
                <Text>
                  Вы уверены, что хотите удалить бронирование{' '}
                  <strong>#{deleteTarget?.id}</strong>?
                </Text>

                <Box w="full" p={3} bg="gray.50" borderRadius="md">
                  <VStack align="start" spacing={1} fontSize="sm">
                    <Text>
                      <strong>Пользователь:</strong> {deleteTarget?.user?.full_name || 'Не указано'}
                    </Text>
                    <Text>
                      <strong>Тариф:</strong> {deleteTarget?.tariff?.name || 'Не указан'}
                    </Text>
                    <Text>
                      <strong>Сумма:</strong> {deleteTarget?.amount?.toLocaleString()} ₽
                    </Text>
                    <Text>
                      <strong>Статус:</strong> {deleteTarget?.paid ? 'Оплачено' : 'Не оплачено'}, {deleteTarget?.confirmed ? 'Подтверждено' : 'Ожидает'}
                    </Text>
                  </VStack>
                </Box>

                <Alert status="warning" borderRadius="md">
                  <AlertIcon />
                  <Box>
                    <AlertDescription fontSize="sm">
                      Это действие удалит бронирование и все связанные с ним данные.
                      <br />
                      <Text color="red.500" fontWeight="medium" mt={2}>
                        Это действие нельзя отменить!
                      </Text>
                    </AlertDescription>
                  </Box>
                </Alert>
              </VStack>
            </AlertDialogBody>

            <AlertDialogFooter>
              <Button ref={cancelRef} onClick={onDeleteClose}>
                Отмена
              </Button>
              <Button
                colorScheme="red"
                onClick={confirmDeleteBooking}
                ml={3}
                isLoading={isDeleting}
                loadingText="Удаление..."
              >
                Удалить
              </Button>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialogOverlay>
      </AlertDialog>

      {/* Диалог массового удаления */}
      <AlertDialog
        isOpen={isBulkDeleteOpen}
        leastDestructiveRef={cancelRef}
        onClose={onBulkDeleteClose}
      >
        <AlertDialogOverlay>
          <AlertDialogContent>
            <AlertDialogHeader fontSize="lg" fontWeight="bold">
              <HStack>
                <Icon as={FiTrash2} color="red.500" />
                <Text>Массовое удаление бронирований</Text>
              </HStack>
            </AlertDialogHeader>

            <AlertDialogBody>
              <VStack align="start" spacing={3}>
                <Text>
                  Вы уверены, что хотите удалить <strong>{selectedBookings.size}</strong> выбранных бронирований?
                </Text>

                <Alert status="error" borderRadius="md">
                  <AlertIcon />
                  <Box>
                    <AlertDescription fontSize="sm">
                      Будут удалены все данные выбранных бронирований, включая платежную информацию и уведомления.
                      <br />
                      <Text color="red.500" fontWeight="medium" mt={2}>
                        Это действие нельзя отменить!
                      </Text>
                    </AlertDescription>
                  </Box>
                </Alert>
              </VStack>
            </AlertDialogBody>

            <AlertDialogFooter>
              <Button ref={cancelRef} onClick={onBulkDeleteClose}>
                Отменить
              </Button>
              <Button
                colorScheme="red"
                onClick={handleBulkDelete}
                ml={3}
                isLoading={isDeleting}
                loadingText="Удаление..."
              >
                Удалить
              </Button>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialogOverlay>
      </AlertDialog>

      {/* Модальное окно создания бронирования */}
      <CreateBookingModal
        isOpen={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
        onSuccess={handleCreateSuccess}
        tariffs={tariffs}
        users={users}
      />
    </Box>
  );
};

export default Bookings;