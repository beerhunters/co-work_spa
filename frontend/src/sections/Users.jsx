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
  Select,
  IconButton,
  useToast,
  AlertDialog,
  AlertDialogBody,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogContent,
  AlertDialogOverlay,
  useDisclosure,
  Tooltip
} from '@chakra-ui/react';
import { FiSearch, FiChevronLeft, FiChevronRight, FiTrash2 } from 'react-icons/fi';
import { userApi } from '../utils/api';

const Users = ({ users, openDetailModal, onUpdate, currentAdmin }) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [currentPage, setCurrentPage] = useState(1);
  const [itemsPerPage, setItemsPerPage] = useState(20);
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [isDeleting, setIsDeleting] = useState(false);

  const { isOpen: isDeleteOpen, onOpen: onDeleteOpen, onClose: onDeleteClose } = useDisclosure();
  const cancelRef = React.useRef();
  const toast = useToast();

  const tableBg = useColorModeValue('white', 'gray.800');
  const borderColor = useColorModeValue('gray.200', 'gray.600');

  // Проверка прав на удаление пользователей
  const canDeleteUsers = currentAdmin?.role === 'super_admin' ||
    (currentAdmin?.permissions && currentAdmin.permissions.includes('delete_users'));

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

  // Обработчик удаления пользователя
  const handleDeleteUser = (user) => {
    setDeleteTarget(user);
    onDeleteOpen();
  };

  const confirmDeleteUser = async () => {
    if (!deleteTarget) return;

    setIsDeleting(true);
    try {
      await userApi.delete(deleteTarget.id);

      toast({
        title: 'Пользователь удален',
        description: `Пользователь ${deleteTarget.full_name || deleteTarget.telegram_id} успешно удален`,
        status: 'success',
        duration: 3000,
        isClosable: true,
      });

      // Обновляем данные в родительском компоненте
      if (onUpdate) {
        await onUpdate();
      }

      // Закрываем диалог
      onDeleteClose();
      setDeleteTarget(null);

    } catch (error) {
      console.error('Ошибка удаления пользователя:', error);

      let errorMessage = 'Не удалось удалить пользователя';
      if (error.response?.status === 403) {
        errorMessage = 'У вас нет прав для удаления пользователей';
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
                  {canDeleteUsers && <Th>Действия</Th>}
                </Tr>
              </Thead>
              <Tbody>
                {currentUsers.map(user => (
                  <Tr
                    key={user.id}
                    _hover={{
                      bg: useColorModeValue('gray.50', 'gray.700')
                    }}
                  >
                    <Td
                      cursor="pointer"
                      onClick={() => openDetailModal(user, 'user')}
                    >
                      <VStack align="start" spacing={1}>
                        <Text fontWeight="semibold">
                          {user.full_name || 'Не указано'}
                        </Text>
                        <Badge colorScheme="blue" fontSize="xs">
                          ID: {user.telegram_id}
                        </Badge>
                      </VStack>
                    </Td>

                    <Td
                      cursor="pointer"
                      onClick={() => openDetailModal(user, 'user')}
                    >
                      <Text color="gray.500">
                        @{user.username || 'Не указано'}
                      </Text>
                    </Td>

                    <Td
                      cursor="pointer"
                      onClick={() => openDetailModal(user, 'user')}
                    >
                      <Text>
                        {user.phone || 'Не указан'}
                      </Text>
                    </Td>

                    <Td
                      cursor="pointer"
                      onClick={() => openDetailModal(user, 'user')}
                    >
                      <Text fontSize="sm">
                        {new Date(user.reg_date || user.first_join_time).toLocaleDateString('ru-RU')}
                      </Text>
                    </Td>

                    <Td
                      cursor="pointer"
                      onClick={() => openDetailModal(user, 'user')}
                    >
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

                    {canDeleteUsers && (
                      <Td>
                        <Tooltip label="Удалить пользователя">
                          <IconButton
                            icon={<FiTrash2 />}
                            size="sm"
                            variant="ghost"
                            colorScheme="red"
                            aria-label="Удалить пользователя"
                            onClick={(e) => {
                              e.stopPropagation();
                              handleDeleteUser(user);
                            }}
                          />
                        </Tooltip>
                      </Td>
                    )}
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

      {/* Диалог подтверждения удаления */}
      <AlertDialog
        isOpen={isDeleteOpen}
        leastDestructiveRef={cancelRef}
        onClose={onDeleteClose}
      >
        <AlertDialogOverlay>
          <AlertDialogContent>
            <AlertDialogHeader fontSize="lg" fontWeight="bold">
              Удалить пользователя
            </AlertDialogHeader>

            <AlertDialogBody>
              Вы уверены, что хотите удалить пользователя{' '}
              <strong>
                {deleteTarget?.full_name || `ID: ${deleteTarget?.telegram_id}`}
              </strong>?
              <br />
              <br />
              Это действие также удалит:
              <br />
              • Все бронирования пользователя
              <br />
              • Все уведомления
              <br />
              • Все тикеты
              <br />
              • Аватар пользователя
              <br />
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
                onClick={confirmDeleteUser}
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
    </Box>
  );
};

export default Users;