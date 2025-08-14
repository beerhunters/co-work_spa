import React, { useState, useMemo } from 'react';
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
  FiCalendar,
  FiClock,
  FiDollarSign,
  FiCheck,
  FiX,
  FiEye,
  FiTag
} from 'react-icons/fi';
import { getStatusColor } from '../styles/styles';

const Bookings = ({ bookings, bookingsMeta, openDetailModal, onRefresh }) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [currentPage, setCurrentPage] = useState(1);
  const [itemsPerPage, setItemsPerPage] = useState(20);

  const tableBg = useColorModeValue('white', 'gray.800');
  const borderColor = useColorModeValue('gray.200', 'gray.600');

  const formatDate = (dateString) => {
    try {
      return new Date(dateString).toLocaleDateString('ru-RU');
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

  const formatDateTime = (dateString) => {
    try {
      return new Date(dateString).toLocaleString('ru-RU');
    } catch {
      return 'Неизвестно';
    }
  };

  // Используем данные из props (они уже отфильтрованы на сервере)
  const displayedBookings = bookings || [];
  const totalPages = bookingsMeta?.total_pages || 1;
  const totalCount = bookingsMeta?.total_count || 0;

  const handlePageChange = (newPage) => {
    setCurrentPage(Math.max(1, Math.min(newPage, totalPages)));
    // Здесь нужно вызвать обновление данных с новой страницей
    // Это будет реализовано в родительском компоненте
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
              <Button size="sm" onClick={onRefresh} colorScheme="blue" variant="outline">
                Обновить
              </Button>
            </HStack>
          </HStack>

          {/* Фильтры */}
          <HStack spacing={4} wrap="wrap">
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
          </HStack>
        </VStack>

        {/* Таблица бронирований */}
        {displayedBookings.length > 0 ? (
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
                  <Th>Дата и время</Th>
                  <Th>Тариф ID</Th>
                  <Th>Статусы</Th>
                  <Th isNumeric>Сумма</Th>
                  <Th>Создано</Th>
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
                      <VStack align="start" spacing={1}>
                        <HStack spacing={2}>
                          <Icon as={FiCalendar} color="blue.500" />
                          <Text fontWeight="medium">
                            {formatDate(booking.visit_date)}
                          </Text>
                        </HStack>
                        <HStack spacing={2}>
                          <Icon as={FiClock} color="gray.500" />
                          <Text fontSize="sm" color="gray.600">
                            {formatTime(booking.visit_time)}
                          </Text>
                          {booking.duration && (
                            <Text fontSize="xs" color="gray.500">
                              ({booking.duration}ч)
                            </Text>
                          )}
                        </HStack>
                      </VStack>
                    </Td>

                    <Td>
                      <VStack align="start" spacing={1}>
                        <HStack spacing={2}>
                          <Icon as={FiTag} color="purple.500" />
                          <Text fontWeight="medium" fontSize="sm">
                            Тариф #{booking.tariff_id}
                          </Text>
                        </HStack>
                        {booking.promocode_id && (
                          <Badge colorScheme="purple" fontSize="xs">
                            Промокод #{booking.promocode_id}
                          </Badge>
                        )}
                      </VStack>
                    </Td>

                    <Td>
                      <VStack align="start" spacing={1}>
                        <Badge
                          colorScheme={getStatusColor(booking.paid ? 'paid' : 'unpaid')}
                          size="sm"
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
                          size="sm"
                        >
                          {booking.confirmed ? 'Подтверждено' : 'Ожидает'}
                        </Badge>
                      </VStack>
                    </Td>

                    <Td isNumeric>
                      <HStack spacing={1} justify="flex-end">
                        <Icon as={FiDollarSign} color="green.500" />
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
              <Text fontSize="sm">Попробуйте изменить фильтры или обновить страницу</Text>
            </VStack>
          </Box>
        )}

        {/* Пагинация */}
        {totalPages > 1 && (
          <Flex justify="center" align="center" wrap="wrap" gap={2}>
            <Button
              leftIcon={<FiChevronLeft />}
              onClick={() => handlePageChange(currentPage - 1)}
              isDisabled={currentPage === 1}
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
              isDisabled={currentPage === totalPages}
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