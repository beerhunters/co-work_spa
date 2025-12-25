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
  Checkbox
} from '@chakra-ui/react';
import {
  FiSearch,
  FiChevronLeft,
  FiChevronRight,
  FiCheck,
  FiX,
  FiEye,
  FiTrash2,
  FiCheckSquare,
  FiSquare,
  FiDownload,
  FiPlus
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

  const handleSelectAll = (isSelected) => {
    if (isSelected) {
      const allIds = new Set(displayedBookings.map(booking => booking.id));
      setSelectedBookings(allIds);
    } else {
      setSelectedBookings(new Set());
    }
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
    const confirmed = displayedBookings.filter(b => b.confirmed).length;
    const totalAmount = displayedBookings.reduce((sum, b) => sum + (b.amount || 0), 0);

    return { total, paid, confirmed, totalAmount };
  }, [displayedBookings, totalCount]);

  return (
    <Box p={6}>
      <VStack spacing={6} align="stretch">
        {/* Заголовок и статистика */}
        <VStack align="stretch" spacing={4}>
          <HStack justify="space-between" align="center" wrap="wrap">
            <VStack align="start" spacing={1}>
              <Text fontSize="2xl" fontWeight="bold">
                Бронирования
              </Text>
              <HStack spacing={4} fontSize="sm" color="gray.600">
                <Text>Всего: {stats.total}</Text>
                <Text>На странице - Оплачено: {stats.paid}</Text>
                <Text>Подтверждено: {stats.confirmed}</Text>
                <Text>Сумма на странице: {stats.totalAmount.toLocaleString()} ₽</Text>
              </HStack>
            </VStack>

            <HStack spacing={3}>
              <Text fontSize="sm" color="gray.500">
                Показано: {displayedBookings.length} из {totalCount}
              </Text>
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
          </HStack>

          {/* Фильтры */}
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
              onSelectAll={handleSelectAll}
              onDeselectAll={() => setSelectedBookings(new Set())}
              isAllSelected={isAllSelected}
              isIndeterminate={isIndeterminate}
              entityName="бронирований"
            />
          )}
        </VStack>

        {/* Таблица бронирований */}
        {isLoading ? (
          <Box
            bg={tableBg}
            borderWidth="1px"
            borderColor={borderColor}
            borderRadius="lg"
            overflow="hidden"
          >
            <TableSkeleton rows={10} columns={canDeleteBookings ? 9 : 8} />
          </Box>
        ) : displayedBookings.length > 0 ? (
          <Box
            bg={tableBg}
            borderWidth="1px"
            borderColor={borderColor}
            borderRadius="lg"
            overflow="hidden"
            data-tour="bookings-list"
          >
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
                      <Td fontWeight="semibold">#{booking.id}</Td>

                    <Td>
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

                    <Td>
                      <Text fontWeight="medium" fontSize="md">
                        {booking.tariff?.name || `Тариф #${booking.tariff_id}`}
                      </Text>
                      {booking.tariff?.price && (
                        <Text fontSize="xs" color="gray.500">
                          Базовая цена: {booking.tariff.price.toLocaleString()} ₽
                        </Text>
                      )}
                    </Td>

                    <Td data-tour="bookings-status">
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

                    <Td isNumeric>
                      <HStack spacing={1} justify="flex-end">
                        <Text fontWeight="bold" color="green.500">
                          {booking.amount.toLocaleString()} ₽
                        </Text>
                      </HStack>
                    </Td>

                    <Td>
                      <Text fontSize="sm">
                        {formatDateTime(booking.created_at)}
                      </Text>
                    </Td>

                    <Td>
                      <HStack spacing={2}>
                        <Tooltip label="Подробная информация">
                          <Button
                            size="sm"
                            variant="outline"
                            leftIcon={<FiEye />}
                            onClick={() => openDetailModal(booking, 'booking')}
                          >
                            Детали
                          </Button>
                        </Tooltip>

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
                      </HStack>
                    </Td>
                  </Tr>
                  );
                })}
              </Tbody>
            </Table>
          </Box>
        ) : (
          <Box textAlign="center" py={10} color="gray.500">
            <VStack spacing={2}>
              <Text fontSize="lg">Бронирований не найдено</Text>
              <Text fontSize="sm">
                {hasActiveFilters
                  ? 'Попробуйте изменить фильтры или сбросить их'
                  : 'Попробуйте обновить страницу'
                }
              </Text>
              {hasActiveFilters && (
                <Button
                  size="sm"
                  variant="outline"
                  onClick={handleResetFilters}
                >
                  Сбросить фильтры
                </Button>
              )}
            </VStack>
          </Box>
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
              Удалить бронирование
            </AlertDialogHeader>

            <AlertDialogBody>
              Вы уверены, что хотите удалить бронирование{' '}
              <strong>#{deleteTarget?.id}</strong>?
              <br />
              <br />
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
              <br />
              <Text color="red.500" fontWeight="medium">
                Это действие нельзя отменить!
              </Text>
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
              Удалить выбранные бронирования
            </AlertDialogHeader>

            <AlertDialogBody>
              Вы уверены, что хотите удалить {selectedBookings.size} выбранных бронирований? 
              Это действие нельзя отменить.
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