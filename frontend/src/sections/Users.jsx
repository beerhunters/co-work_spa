import React, { useState, useMemo } from 'react';
import {
  Box,
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  Text,
  HStack,
  VStack,
  Badge,
  useColorModeValue,
  Input,
  InputGroup,
  InputLeftElement,
  Button,
  Flex,
  Select
} from '@chakra-ui/react';
import { FiSearch, FiChevronLeft, FiChevronRight } from 'react-icons/fi';

const Users = ({ users, openDetailModal }) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [currentPage, setCurrentPage] = useState(1);
  const [itemsPerPage, setItemsPerPage] = useState(20);

  const tableBg = useColorModeValue('white', 'gray.800');
  const borderColor = useColorModeValue('gray.200', 'gray.600');

  // Фильтрация пользователей по поиску
  const filteredUsers = useMemo(() => {
    if (!searchQuery.trim()) return users;

    const query = searchQuery.toLowerCase().trim();
    return users.filter(user => {
      const fullName = (user.full_name || '').toLowerCase();
      const phone = (user.phone || '').toLowerCase();
      const username = (user.username || '').toLowerCase();

      return fullName.includes(query) ||
             phone.includes(query) ||
             username.includes(query);
    });
  }, [users, searchQuery]);

  // Пагинация
  const totalPages = Math.ceil(filteredUsers.length / itemsPerPage);
  const startIndex = (currentPage - 1) * itemsPerPage;
  const endIndex = startIndex + itemsPerPage;
  const currentUsers = filteredUsers.slice(startIndex, endIndex);

  // Сброс на первую страницу при изменении поиска
  React.useEffect(() => {
    setCurrentPage(1);
  }, [searchQuery, itemsPerPage]);

  const handlePageChange = (newPage) => {
    setCurrentPage(Math.max(1, Math.min(newPage, totalPages)));
  };

  return (
    <Box p={6}>
      <VStack spacing={6} align="stretch">
        {/* Заголовок и поиск */}
        <HStack justify="space-between" align="center" wrap="wrap" spacing={4}>
          <VStack align="start" spacing={1}>
            <Text fontSize="2xl" fontWeight="bold">
              Пользователи
            </Text>
            <Text fontSize="sm" color="gray.500">
              Всего: {users.length} | Показано: {currentUsers.length} из {filteredUsers.length}
            </Text>
          </VStack>

          <HStack spacing={4}>
            <InputGroup maxWidth="300px">
              <InputLeftElement pointerEvents="none">
                <FiSearch color="gray.300" />
              </InputLeftElement>
              <Input
                placeholder="Поиск по ФИО или телефону..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
            </InputGroup>

            <Select
              value={itemsPerPage}
              onChange={(e) => setItemsPerPage(Number(e.target.value))}
              width="150px"
            >
              <option value={10}>по 10</option>
              <option value={20}>по 20</option>
              <option value={50}>по 50</option>
              <option value={100}>по 100</option>
            </Select>
          </HStack>
        </HStack>

        {/* Таблица пользователей */}
        {currentUsers.length > 0 ? (
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
                  <Th>ФИО</Th>
                  <Th>Username</Th>
                  <Th>Телефон</Th>
                  <Th>Дата регистрации</Th>
                  <Th>Статистика</Th>
                </Tr>
              </Thead>
              <Tbody>
                {currentUsers.map(user => (
                  <Tr
                    key={user.id}
                    _hover={{
                      bg: useColorModeValue('gray.50', 'gray.700'),
                      cursor: 'pointer'
                    }}
                    onClick={() => openDetailModal(user, 'user')}
                  >
                    <Td>
                      <VStack align="start" spacing={1}>
                        <Text fontWeight="semibold">
                          {user.full_name || 'Не указано'}
                        </Text>
                        <Badge colorScheme="blue" fontSize="xs">
                          ID: {user.telegram_id}
                        </Badge>
                      </VStack>
                    </Td>

                    <Td>
                      <Text color="gray.500">
                        @{user.username || 'Не указано'}
                      </Text>
                    </Td>

                    <Td>
                      <Text>
                        {user.phone || 'Не указан'}
                      </Text>
                    </Td>

                    <Td>
                      <Text fontSize="sm">
                        {new Date(user.reg_date || user.first_join_time).toLocaleDateString('ru-RU')}
                      </Text>
                    </Td>

                    <Td>
                      <HStack spacing={2} wrap="wrap">
                        {user.successful_bookings > 0 && (
                          <Badge colorScheme="green" fontSize="xs">
                            {user.successful_bookings} броней
                          </Badge>
                        )}

                        {user.invited_count > 0 && (
                          <Badge colorScheme="purple" fontSize="xs">
                            +{user.invited_count}
                          </Badge>
                        )}

                        {user.agreed_to_terms && (
                          <Badge colorScheme="blue" fontSize="xs">
                            ✓ Соглашение
                          </Badge>
                        )}
                      </HStack>
                    </Td>
                  </Tr>
                ))}
              </Tbody>
            </Table>
          </Box>
        ) : (
          <Box
            textAlign="center"
            py={10}
            color="gray.500"
          >
            {searchQuery ? (
              <VStack spacing={2}>
                <Text fontSize="lg">Пользователи не найдены</Text>
                <Text fontSize="sm">Попробуйте изменить запрос поиска</Text>
              </VStack>
            ) : (
              <Text fontSize="lg">Пользователи не найдены</Text>
            )}
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
              {/* Показываем страницы */}
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
                    colorScheme={currentPage === pageNum ? "purple" : "gray"}
                    onClick={() => handlePageChange(pageNum)}
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

export default Users;