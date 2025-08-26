import React, { useState, useEffect, useMemo } from 'react';
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
  Checkbox,
  useDisclosure,
  AlertDialog,
  AlertDialogOverlay,
  AlertDialogContent,
  AlertDialogHeader,
  AlertDialogBody,
  AlertDialogFooter,
  useToast
} from '@chakra-ui/react';
import {
  FiImage,
  FiMessageSquare,
  FiSearch,
  FiChevronLeft,
  FiChevronRight,
  FiTrash2,
  FiCheckSquare,
  FiSquare
} from 'react-icons/fi';
import { getStatusColor } from '../styles/styles';
import { ticketApi } from '../utils/api';

const Tickets = ({
  tickets,
  ticketsMeta,
  openDetailModal,
  onRefresh,
  onFiltersChange,
  isLoading = false
}) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [currentPage, setCurrentPage] = useState(1);
  const [itemsPerPage, setItemsPerPage] = useState(20);
  // Состояния для массового выбора
  const [isSelectionMode, setIsSelectionMode] = useState(false);
  const [selectedTickets, setSelectedTickets] = useState(new Set());
  const [isDeleting, setIsDeleting] = useState(false);

  const tableBg = useColorModeValue('white', 'gray.800');
  const borderColor = useColorModeValue('gray.200', 'gray.600');
  const toast = useToast();
  const { isOpen: isDeleteDialogOpen, onOpen: onDeleteDialogOpen, onClose: onDeleteDialogClose } = useDisclosure();
  const cancelRef = React.useRef();

  // Эффект для отправки фильтров в родительский компонент
  useEffect(() => {
    const params = {
      page: currentPage,
      per_page: itemsPerPage
    };

    // Добавляем фильтры только если они не дефолтные
    if (statusFilter && statusFilter !== 'all') {
      params.status = statusFilter;
    }

    if (searchQuery && searchQuery.trim()) {
      params.user_query = searchQuery.trim();
    }

    console.log('Отправляем параметры фильтрации тикетов:', params);
    console.log('Текущее состояние фильтров тикетов:', {
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
    console.log('Сброс фильтров тикетов к изначальным значениям');

    setSearchQuery('');
    setStatusFilter('all');
    setCurrentPage(1);
    setItemsPerPage(20);

    // Принудительно отправляем дефолтные параметры
    const defaultParams = {
      page: 1,
      per_page: 20
    };

    console.log('Принудительно отправляем дефолтные параметры тикетов:', defaultParams);

    if (onFiltersChange) {
      onFiltersChange(defaultParams);
    }
  };

  // Проверка, активны ли какие-либо фильтры
  const hasActiveFilters = searchQuery.trim() || statusFilter !== 'all' || itemsPerPage !== 20;

  const handleSearchSubmit = (e) => {
    e.preventDefault();
    // Поиск будет выполнен через useEffect
  };

  const handlePageChange = (newPage) => {
    const page = Math.max(1, Math.min(newPage, totalPages));
    setCurrentPage(page);
  };

  // Используем данные из props
  const displayedTickets = tickets || [];
  const totalPages = ticketsMeta?.total_pages || 1;
  const totalCount = ticketsMeta?.total_count || 0;

  // Статистика для отображения
  const stats = useMemo(() => {
    const total = totalCount;
    const open = displayedTickets.filter(t => t.status === 'OPEN').length;
    const inProgress = displayedTickets.filter(t => t.status === 'IN_PROGRESS').length;
    const closed = displayedTickets.filter(t => t.status === 'CLOSED').length;

    return { total, open, inProgress, closed };
  }, [displayedTickets, totalCount]);

  const getStatusLabel = (status) => {
    const statusLabels = {
      'OPEN': 'Открыта',
      'IN_PROGRESS': 'В работе',
      'CLOSED': 'Закрыта'
    };
    return statusLabels[status] || status;
  };

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

  // Функции для массового выбора
  const handleToggleSelectionMode = () => {
    setIsSelectionMode(!isSelectionMode);
    setSelectedTickets(new Set());
  };

  const handleSelectTicket = (ticketId, isSelected) => {
    const newSelected = new Set(selectedTickets);
    if (isSelected) {
      newSelected.add(ticketId);
    } else {
      newSelected.delete(ticketId);
    }
    setSelectedTickets(newSelected);
  };

  const handleSelectAll = (isSelected) => {
    if (isSelected) {
      const allIds = new Set(displayedTickets.map(ticket => ticket.id));
      setSelectedTickets(allIds);
    } else {
      setSelectedTickets(new Set());
    }
  };

  const handleDeleteSelected = async () => {
    setIsDeleting(true);
    const selectedArray = Array.from(selectedTickets);
    
    try {
      const promises = selectedArray.map(ticketId => ticketApi.delete(ticketId));
      await Promise.all(promises);

      toast({
        title: 'Успешно',
        description: `Удалено тикетов: ${selectedArray.length}`,
        status: 'success',
        duration: 3000,
        isClosable: true,
      });

      // Сбрасываем выбор и режим выбора
      setSelectedTickets(new Set());
      setIsSelectionMode(false);

      // Обновляем данные
      if (onRefresh) {
        onRefresh();
      }
    } catch (error) {
      console.error('Ошибка при удалении тикетов:', error);
      toast({
        title: 'Ошибка',
        description: 'Не удалось удалить выбранные тикеты',
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    } finally {
      setIsDeleting(false);
      onDeleteDialogClose();
    }
  };

  const isAllSelected = displayedTickets.length > 0 && selectedTickets.size === displayedTickets.length;
  const isIndeterminate = selectedTickets.size > 0 && selectedTickets.size < displayedTickets.length;

  return (
    <Box p={6}>
      <VStack spacing={6} align="stretch">
        {/* Заголовок и статистика */}
        <VStack align="stretch" spacing={4}>
          <HStack justify="space-between" align="center" wrap="wrap">
            <VStack align="start" spacing={1}>
              <Text fontSize="2xl" fontWeight="bold">
                Тикеты поддержки
              </Text>
              <HStack spacing={4} fontSize="sm" color="gray.600">
                <Text>Всего: {stats.total}</Text>
                <Text>На странице - Открыто: {stats.open}</Text>
                <Text>В работе: {stats.inProgress}</Text>
                <Text>Закрыто: {stats.closed}</Text>
              </HStack>
            </VStack>

            <HStack spacing={3}>
              <Text fontSize="sm" color="gray.500">
                Показано: {displayedTickets.length} из {totalCount}
              </Text>
              <Button
                size="sm"
                leftIcon={<Icon as={isSelectionMode ? FiSquare : FiCheckSquare} />}
                onClick={handleToggleSelectionMode}
                colorScheme={isSelectionMode ? "gray" : "purple"}
                variant="outline"
                isDisabled={isLoading || displayedTickets.length === 0}
              >
                {isSelectionMode ? 'Отменить' : 'Выбрать'}
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
                  placeholder="Поиск по ФИО или описанию..."
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
              <option value="all">Все тикеты</option>
              <option value="OPEN">Открытые</option>
              <option value="IN_PROGRESS">В работе</option>
              <option value="CLOSED">Закрытые</option>
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

          {/* Панель массовых действий */}
          {isSelectionMode && (
            <Box
              bg={useColorModeValue('purple.50', 'purple.900')}
              borderWidth="1px"
              borderColor={useColorModeValue('purple.200', 'purple.600')}
              borderRadius="lg"
              p={4}
            >
              <HStack justify="space-between" align="center" wrap="wrap">
                <HStack spacing={4}>
                  <Text fontSize="sm" fontWeight="medium" color="purple.700">
                    {selectedTickets.size > 0 
                      ? `Выбрано: ${selectedTickets.size} из ${displayedTickets.length}`
                      : 'Выберите тикеты для удаления'
                    }
                  </Text>
                  <Checkbox
                    isChecked={isAllSelected}
                    isIndeterminate={isIndeterminate}
                    onChange={(e) => handleSelectAll(e.target.checked)}
                    colorScheme="purple"
                  >
                    Выбрать все на странице
                  </Checkbox>
                </HStack>
                
                {selectedTickets.size > 0 && (
                  <Button
                    leftIcon={<Icon as={FiTrash2} />}
                    onClick={onDeleteDialogOpen}
                    colorScheme="red"
                    size="sm"
                    variant="outline"
                  >
                    Удалить выбранные ({selectedTickets.size})
                  </Button>
                )}
              </HStack>
            </Box>
          )}
        </VStack>

        {/* Таблица тикетов */}
        {isLoading ? (
          <Box textAlign="center" py={10}>
            <Text>Загрузка...</Text>
          </Box>
        ) : displayedTickets.length > 0 ? (
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
                  {isSelectionMode && <Th w="40px"></Th>}
                  <Th>ID</Th>
                  <Th>Пользователь</Th>
                  <Th>Описание</Th>
                  <Th>Статус</Th>
                  <Th>Дата создания</Th>
                  <Th>Файлы</Th>
                </Tr>
              </Thead>
              <Tbody>
                {displayedTickets.map(ticket => {
                  const isSelected = selectedTickets.has(ticket.id);
                  
                  return (
                    <Tr
                      key={ticket.id}
                      cursor="pointer"
                      bg={isSelectionMode && isSelected ? useColorModeValue('purple.50', 'purple.900') : 'transparent'}
                      _hover={{
                        bg: isSelectionMode && isSelected 
                          ? useColorModeValue('purple.100', 'purple.800')
                          : useColorModeValue('gray.50', 'gray.700'),
                        transform: 'translateY(-1px)',
                        boxShadow: 'md'
                      }}
                      transition="all 0.2s"
                      onClick={(e) => {
                        if (isSelectionMode) {
                          // В режиме выбора - переключаем выбор
                          e.stopPropagation();
                          handleSelectTicket(ticket.id, !isSelected);
                        } else {
                          // В обычном режиме - открываем детали
                          openDetailModal(ticket, 'ticket');
                        }
                      }}
                    >
                      {isSelectionMode && (
                        <Td onClick={(e) => e.stopPropagation()}>
                          <Checkbox
                            isChecked={isSelected}
                            onChange={(e) => handleSelectTicket(ticket.id, e.target.checked)}
                            colorScheme="purple"
                          />
                        </Td>
                      )}
                      <Td fontWeight="semibold">#{ticket.id}</Td>
                    <Td>
                      <VStack align="start" spacing={0}>
                        <Text fontWeight="medium">
                          {ticket.user?.full_name || 'Неизвестно'}
                        </Text>
                        <Text fontSize="sm" color="gray.500">
                          @{ticket.user?.username || 'Неизвестно'}
                        </Text>
                      </VStack>
                    </Td>
                    <Td>
                      <Text noOfLines={2} maxW="300px">
                        {ticket.description.length > 100
                          ? `${ticket.description.substring(0, 100)}...`
                          : ticket.description
                        }
                      </Text>
                    </Td>
                    <Td>
                      <Badge colorScheme={getStatusColor(ticket.status)}>
                        {getStatusLabel(ticket.status)}
                      </Badge>
                    </Td>
                    <Td>
                      <Text fontSize="sm">
                        {formatDateTime(ticket.created_at)}
                      </Text>
                    </Td>
                    <Td>
                      <HStack spacing={2}>
                        {ticket.photo_id && (
                          <Tooltip label="Есть прикрепленное фото от пользователя">
                            <Box>
                              <Icon
                                as={FiImage}
                                color="blue.500"
                              />
                            </Box>
                          </Tooltip>
                        )}
                        {ticket.comment && (
                          <Tooltip label="Есть комментарий администратора">
                            <Box>
                              <Icon
                                as={FiMessageSquare}
                                color="green.500"
                              />
                            </Box>
                          </Tooltip>
                        )}
                        {ticket.response_photo_id && (
                          <Tooltip label="Есть фото в ответе администратора">
                            <Box>
                              <Icon
                                as={FiImage}
                                color="purple.500"
                              />
                            </Box>
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
              <Text fontSize="lg">Тикетов не найдено</Text>
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

        {/* Диалог подтверждения удаления */}
        <AlertDialog
          isOpen={isDeleteDialogOpen}
          leastDestructiveRef={cancelRef}
          onClose={onDeleteDialogClose}
        >
          <AlertDialogOverlay>
            <AlertDialogContent>
              <AlertDialogHeader fontSize="lg" fontWeight="bold">
                Удалить выбранные тикеты
              </AlertDialogHeader>

              <AlertDialogBody>
                Вы уверены, что хотите удалить {selectedTickets.size} выбранных тикетов? 
                Это действие нельзя отменить.
              </AlertDialogBody>

              <AlertDialogFooter>
                <Button ref={cancelRef} onClick={onDeleteDialogClose}>
                  Отменить
                </Button>
                <Button
                  colorScheme="red"
                  onClick={handleDeleteSelected}
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
      </VStack>
    </Box>
  );
};

export default Tickets;