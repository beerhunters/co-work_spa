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
  Tooltip
} from '@chakra-ui/react';
import {
  FiSearch,
  FiChevronLeft,
  FiChevronRight,
  FiCheck,
  FiX,
  FiEye
} from 'react-icons/fi';
import { getStatusColor } from '../styles/styles';

const Bookings = ({
  bookings,
  bookingsMeta,
  openDetailModal,
  onRefresh,
  onFiltersChange, // Новый пропс для передачи фильтров в родительский компонент
  isLoading = false // Пропс для индикации загрузки
}) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [currentPage, setCurrentPage] = useState(1);
  const [itemsPerPage, setItemsPerPage] = useState(20);

  const tableBg = useColorModeValue('white', 'gray.800');
  const borderColor = useColorModeValue('gray.200', 'gray.600');

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

    if (searchQuery && searchQuery.trim()) {
      params.user_query = searchQuery.trim();
    }

    console.log('Отправляем параметры фильтрации:', params);
    console.log('Текущее состояние фильтров:', {
      searchQuery,
      statusFilter,
      currentPage,
      itemsPerPage
    });

    if (onFiltersChange) {
      onFiltersChange(params);
    }
  }, [currentPage, itemsPerPage, statusFilter, searchQuery, onFiltersChange]);

  // Сброс на первую страницу при изменении фильтров
  useEffect(() => {
    if (currentPage !== 1) {
      setCurrentPage(1);
    }
  }, [statusFilter, searchQuery, itemsPerPage]);

  // Функция сброса всех фильтров
  const handleResetFilters = () => {
    console.log('Сброс фильтров к изначальным значениям');

    setSearchQuery('');
    setStatusFilter('all');
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
  const hasActiveFilters = searchQuery.trim() || statusFilter !== 'all' || itemsPerPage !== 20;

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
                  placeholder="Поиск по ФИО пользователя..."
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

            {/* Количество элементов на странице */}
            <Select
              value={itemsPerPage}
              onChange={(e) => setItemsPerPage(Number(e.target.value))}
              maxW="150px"
            >
              <option value={10}>по 10</option>
              <option value={20}>по 20</option>
              <option value={50}>по 50</option>
              <option value={100}>по 100</option>
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
        </VStack>

        {/* Таблица бронирований */}
        {isLoading ? (
          <Box textAlign="center" py={10}>
            <Text>Загрузка...</Text>
          </Box>
        ) : displayedBookings.length > 0 ? (
          <Box
            bg={tableBg}
            borderWidth="1px"
            borderColor={borderColor}
            borderRadius="lg"
            overflow="hidden"
          >
            <Table variant="simple">
              <Thead bg={useColorModeValue('gray.50', 'gray.700')}>
                <Tr>
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
                {displayedBookings.map(booking => (
                  <Tr
                    key={booking.id}
                    _hover={{
                      bg: useColorModeValue('gray.50', 'gray.700'),
                    }}
                  >
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

                    <Td>
                      <VStack align="start" spacing={1}>
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
                    </Td>
                  </Tr>
                ))}
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
        {totalPages > 1 && (
          <Flex justify="center" align="center" wrap="wrap" gap={2}>
            <Button
              leftIcon={<FiChevronLeft />}
              onClick={() => handlePageChange(currentPage - 1)}
              isDisabled={currentPage === 1 || isLoading}
              size="sm"
            >
              Назад
            </Button>

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
                    isDisabled={isLoading}
                    minW="40px"
                  >
                    {pageNum}
                  </Button>
                );
              })}
            </HStack>

            <Button
              rightIcon={<FiChevronRight />}
              onClick={() => handlePageChange(currentPage + 1)}
              isDisabled={currentPage === totalPages || isLoading}
              size="sm"
            >
              Вперёд
            </Button>

            <Text fontSize="sm" color="gray.500" ml={4}>
              Стр. {currentPage} из {totalPages}
            </Text>
          </Flex>
        )}
      </VStack>
    </Box>
  );
};

export default Bookings;