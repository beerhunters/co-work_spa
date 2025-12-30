import React, { useState, useMemo } from 'react';
import {
  Box,
  Button,
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  Badge,
  IconButton,
  Input,
  InputGroup,
  InputLeftElement,
  HStack,
  VStack,
  Text,
  useColorModeValue,
  Select,
  Flex,
  useDisclosure,
  SimpleGrid,
  Card,
  CardBody,
  Stat,
  StatLabel,
  StatNumber,
  StatHelpText,
  Divider,
  Icon,
  Heading
} from '@chakra-ui/react';
import { FiSearch, FiEdit, FiTrash2, FiPlus, FiEye, FiChevronLeft, FiChevronRight, FiShield, FiUser, FiCheckCircle, FiXCircle } from 'react-icons/fi';
import { getStatusColor } from '../styles/styles';
import AdminDetailModal from '../components/modals/AdminDetailModal';

const Admins = ({ admins, onUpdate, currentAdmin }) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [currentPage, setCurrentPage] = useState(1);
  const [itemsPerPage, setItemsPerPage] = useState(20);
  const [statusFilter, setStatusFilter] = useState('all');
  const [selectedAdmin, setSelectedAdmin] = useState(null);

  const tableBg = useColorModeValue('white', 'gray.800');
  const borderColor = useColorModeValue('gray.200', 'gray.600');

  // Для модального окна
  const { isOpen: isModalOpen, onOpen: onModalOpen, onClose: onModalClose } = useDisclosure();

  const filteredAdmins = useMemo(() => {
    let filtered = admins;

    // Фильтр по статусу
    if (statusFilter === 'active') {
      filtered = filtered.filter(a => a.is_active);
    } else if (statusFilter === 'inactive') {
      filtered = filtered.filter(a => !a.is_active);
    }

    // Поиск
    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase().trim();
      filtered = filtered.filter(admin =>
        admin.login.toLowerCase().includes(query) ||
        admin.role.toLowerCase().includes(query) ||
        (admin.creator_login && admin.creator_login.toLowerCase().includes(query))
      );
    }

    return filtered;
  }, [admins, searchQuery, statusFilter]);

  // Пагинация
  const totalPages = Math.ceil(filteredAdmins.length / itemsPerPage);
  const startIndex = (currentPage - 1) * itemsPerPage;
  const endIndex = startIndex + itemsPerPage;
  const currentAdmins = filteredAdmins.slice(startIndex, endIndex);

  React.useEffect(() => {
    setCurrentPage(1);
  }, [searchQuery, statusFilter, itemsPerPage]);

  const handlePageChange = (newPage) => {
    setCurrentPage(Math.max(1, Math.min(newPage, totalPages)));
  };

  const getRoleLabel = (role) => {
    const labels = {
      'super_admin': 'Главный админ',
      'manager': 'Менеджер'
    };
    return labels[role] || role;
  };

  const getRoleColor = (role) => {
    return role === 'super_admin' ? 'purple' : 'blue';
  };

  // Статистика
  const stats = useMemo(() => {
    const active = admins.filter(a => a.is_active).length;
    const inactive = admins.filter(a => !a.is_active).length;
    const superAdmins = admins.filter(a => a.role === 'super_admin').length;
    const managers = admins.filter(a => a.role === 'manager').length;

    return {
      total: admins.length,
      active,
      inactive,
      superAdmins,
      managers
    };
  }, [admins]);

  const formatDateTime = (dateString) => {
    if (!dateString) return 'Не указано';
    return new Date(dateString).toLocaleString('ru-RU', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const canManageAdmin = (admin) => {
    // Нельзя управлять супер админом
    if (admin.role === 'super_admin') return false;
    // Нельзя управлять самим собой
    if (admin.id === currentAdmin?.id) return false;
    return true;
  };

  // Обработчики модального окна
  const handleOpenModal = (admin = null) => {
    setSelectedAdmin(admin);
    onModalOpen();
  };

  const handleCloseModal = () => {
    setSelectedAdmin(null);
    onModalClose();
  };

  // Обработчик создания админа
  const handleCreateAdmin = () => {
    handleOpenModal(null); // null означает создание нового админа
  };

  // Обработчик просмотра/редактирования админа
  const handleViewAdmin = (admin) => {
    handleOpenModal(admin);
  };

  return (
    <Box p={6}>
      <VStack spacing={6} align="stretch">
        {/* Заголовок */}
        <Box>
          <HStack justify="space-between" align="center" mb={2}>
            <HStack spacing={4}>
              <Icon as={FiShield} boxSize={8} color="purple.500" />
              <Heading size="lg">
                Администраторы
              </Heading>
            </HStack>

            {currentAdmin?.role === 'super_admin' && (
              <Button
                leftIcon={<FiPlus />}
                colorScheme="purple"
                onClick={handleCreateAdmin}
                size="sm"
              >
                Добавить админа
              </Button>
            )}
          </HStack>
          <Text color="gray.600">
            Управление учетными записями администраторов и распределение ролей
          </Text>
        </Box>

        {/* Статистика */}
        <SimpleGrid columns={{ base: 1, md: 2, lg: 4 }} spacing={4}>
          <Card>
            <CardBody>
              <Stat>
                <StatLabel>Всего админов</StatLabel>
                <StatNumber>{stats.total}</StatNumber>
                <StatHelpText>
                  <Icon as={FiUser} mr={1} />
                  В системе
                </StatHelpText>
              </Stat>
            </CardBody>
          </Card>

          <Card>
            <CardBody>
              <Stat>
                <StatLabel>Активные</StatLabel>
                <StatNumber color="green.500">{stats.active}</StatNumber>
                <StatHelpText>
                  <Icon as={FiCheckCircle} mr={1} />
                  Имеют доступ
                </StatHelpText>
              </Stat>
            </CardBody>
          </Card>

          <Card>
            <CardBody>
              <Stat>
                <StatLabel>Неактивные</StatLabel>
                <StatNumber color="red.500">{stats.inactive}</StatNumber>
                <StatHelpText>
                  <Icon as={FiXCircle} mr={1} />
                  Доступ закрыт
                </StatHelpText>
              </Stat>
            </CardBody>
          </Card>

          <Card>
            <CardBody>
              <Stat>
                <StatLabel>Роли</StatLabel>
                <StatNumber color="purple.500">{stats.superAdmins} / {stats.managers}</StatNumber>
                <StatHelpText>
                  <Icon as={FiShield} mr={1} />
                  Главные / Менеджеры
                </StatHelpText>
              </Stat>
            </CardBody>
          </Card>
        </SimpleGrid>

        <Divider />

        {/* Фильтры */}
        <HStack spacing={4} wrap="wrap">
          <InputGroup maxW="300px">
            <InputLeftElement pointerEvents="none">
              <FiSearch color="gray.300" />
            </InputLeftElement>
            <Input
              placeholder="Поиск по логину, роли..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </InputGroup>

          <Select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            maxW="150px"
          >
            <option value="all">Все</option>
            <option value="active">Активные</option>
            <option value="inactive">Неактивные</option>
          </Select>

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

        {/* Таблица админов */}
        {currentAdmins.length > 0 ? (
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
                  <Th>Логин</Th>
                  <Th>Роль</Th>
                  <Th>Статус</Th>
                  <Th>Создатель</Th>
                  <Th>Дата создания</Th>
                  <Th>Разрешения</Th>
                  <Th>Действия</Th>
                </Tr>
              </Thead>
              <Tbody>
                {currentAdmins.map(admin => (
                  <Tr
                    key={admin.id}
                    _hover={{
                      bg: useColorModeValue('gray.50', 'gray.700'),
                    }}
                  >
                    <Td>
                      <VStack align="start" spacing={1}>
                        <Text fontWeight="medium">
                          {admin.login}
                        </Text>
                        {admin.id === currentAdmin?.id && (
                          <Badge colorScheme="green" fontSize="xs">
                            Вы
                          </Badge>
                        )}
                      </VStack>
                    </Td>

                    <Td>
                      <Badge colorScheme={getRoleColor(admin.role)}>
                        {getRoleLabel(admin.role)}
                      </Badge>
                    </Td>

                    <Td>
                      <Badge colorScheme={getStatusColor(admin.is_active ? 'active' : 'inactive')}>
                        {admin.is_active ? 'Активен' : 'Неактивен'}
                      </Badge>
                    </Td>

                    <Td>
                      <Text fontSize="sm">
                        {admin.creator_login || 'Система'}
                      </Text>
                    </Td>

                    <Td>
                      <Text fontSize="sm">
                        {formatDateTime(admin.created_at)}
                      </Text>
                    </Td>

                    <Td>
                      <Text fontSize="sm" color="gray.500">
                        {admin.role === 'super_admin'
                          ? 'Все права'
                          : `${admin.permissions?.length || 0} разрешений`
                        }
                      </Text>
                    </Td>

                    <Td>
                      <HStack spacing={2}>
                        <IconButton
                          icon={<FiEye />}
                          size="sm"
                          variant="ghost"
                          colorScheme="blue"
                          aria-label="Просмотр"
                          onClick={() => handleViewAdmin(admin)}
                        />

                        {canManageAdmin(admin) && currentAdmin?.role === 'super_admin' && (
                          <>
                            <IconButton
                              icon={<FiEdit />}
                              size="sm"
                              variant="ghost"
                              colorScheme="orange"
                              aria-label="Редактировать"
                              onClick={() => handleViewAdmin(admin)}
                            />

                            <IconButton
                              icon={<FiTrash2 />}
                              size="sm"
                              variant="ghost"
                              colorScheme="red"
                              aria-label="Удалить"
                              onClick={() => handleViewAdmin(admin)}
                            />
                          </>
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
                <Text fontSize="lg">Администраторы не найдены</Text>
                <Text fontSize="sm">Попробуйте изменить запрос поиска</Text>
              </VStack>
            ) : (
              <Text fontSize="lg">Администраторы не найдены</Text>
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

      {/* Модальное окно администратора */}
      <AdminDetailModal
        isOpen={isModalOpen}
        onClose={handleCloseModal}
        admin={selectedAdmin}
        onUpdate={onUpdate}
        currentAdmin={currentAdmin}
      />
    </Box>
  );
};

export default Admins;