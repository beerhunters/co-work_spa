import React, { useState, useEffect } from 'react';
import {
  Box,
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  Badge,
  Button,
  HStack,
  VStack,
  Text,
  useToast,
  useDisclosure,
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalBody,
  ModalFooter,
  ModalCloseButton,
  Textarea,
  Select,
  AlertDialog,
  AlertDialogOverlay,
  AlertDialogContent,
  AlertDialogHeader,
  AlertDialogBody,
  AlertDialogFooter,
  Spinner,
  Flex,
  Icon,
  Heading,
  Card,
  CardBody,
  SimpleGrid,
  Stat,
  StatLabel,
  StatNumber,
  StatHelpText,
  Divider,
  Alert,
  AlertIcon,
  AlertTitle,
  AlertDescription
} from '@chakra-ui/react';
import { FaBell, FaTrash, FaFilter, FaUserPlus, FaBuilding, FaUsers } from 'react-icons/fa';
import api from '../utils/api';

const OfficeSubscriptions = () => {
  const [subscriptions, setSubscriptions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filterSize, setFilterSize] = useState(null);
  const [notifyMessage, setNotifyMessage] = useState('');
  const [notifySize, setNotifySize] = useState(null);
  const [deleteId, setDeleteId] = useState(null);
  const [sendingNotification, setSendingNotification] = useState(false);

  const toast = useToast();
  const { isOpen: isNotifyOpen, onOpen: onNotifyOpen, onClose: onNotifyClose } = useDisclosure();
  const { isOpen: isDeleteOpen, onOpen: onDeleteOpen, onClose: onDeleteClose } = useDisclosure();
  const cancelRef = React.useRef();

  const fetchSubscriptions = async () => {
    try {
      setLoading(true);
      const params = filterSize ? { office_size: filterSize } : {};
      const response = await api.get('/office-subscriptions/', { params });

      // Проверяем, что response.data это массив
      const data = Array.isArray(response.data) ? response.data : [];
      setSubscriptions(data);
    } catch (error) {
      console.error('Error loading subscriptions:', error);
      setSubscriptions([]); // Сбрасываем на пустой массив при ошибке
      toast({
        title: 'Ошибка загрузки подписок',
        description: error.response?.data?.detail || 'Произошла ошибка',
        status: 'error',
        duration: 3000,
        isClosable: true,
      });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSubscriptions();
  }, [filterSize]);

  const handleDelete = async () => {
    try {
      await api.delete(`/office-subscriptions/${deleteId}`);
      toast({
        title: 'Подписка удалена',
        description: 'Подписка успешно удалена из системы',
        status: 'success',
        duration: 2000,
        isClosable: true,
      });
      fetchSubscriptions();
    } catch (error) {
      toast({
        title: 'Ошибка удаления',
        description: error.response?.data?.detail || 'Произошла ошибка',
        status: 'error',
        duration: 3000,
        isClosable: true,
      });
    } finally {
      onDeleteClose();
      setDeleteId(null);
    }
  };

  const handleSendNotification = async () => {
    if (!notifyMessage.trim()) {
      toast({
        title: 'Пустое сообщение',
        description: 'Введите текст сообщения для отправки',
        status: 'warning',
        duration: 2000,
        isClosable: true,
      });
      return;
    }

    try {
      setSendingNotification(true);
      const response = await api.post('/office-subscriptions/notify', {
        message: notifyMessage,
        office_size: notifySize || null
      });

      toast({
        title: 'Уведомления отправлены!',
        description: `✅ Успешно: ${response.data.sent} | ❌ Ошибок: ${response.data.failed}`,
        status: 'success',
        duration: 5000,
        isClosable: true,
      });

      setNotifyMessage('');
      setNotifySize(null);
      onNotifyClose();
    } catch (error) {
      const errorMsg = error.response?.data?.detail || 'Произошла ошибка при отправке';

      // Специальная обработка ошибки "нет подписчиков"
      if (errorMsg.includes('Нет подписчиков')) {
        toast({
          title: 'Нет получателей',
          description: 'По указанному фильтру не найдено подписчиков. Попробуйте выбрать другой размер офиса или отправить всем.',
          status: 'info',
          duration: 4000,
          isClosable: true,
        });
      } else {
        toast({
          title: 'Ошибка отправки',
          description: errorMsg,
          status: 'error',
          duration: 3000,
          isClosable: true,
        });
      }
    } finally {
      setSendingNotification(false);
    }
  };

  const renderOfficeSizes = (subscription) => {
    const sizes = [];
    if (subscription.office_1) sizes.push({ value: '1', color: 'purple' });
    if (subscription.office_2) sizes.push({ value: '2', color: 'blue' });
    if (subscription.office_4) sizes.push({ value: '4', color: 'green' });
    if (subscription.office_6) sizes.push({ value: '6', color: 'orange' });

    return (
      <HStack spacing={2} flexWrap="wrap">
        {sizes.map(size => (
          <Badge key={size.value} colorScheme={size.color} fontSize="sm" px={2} py={1}>
            <Icon as={FaBuilding} mr={1} />
            {size.value} чел.
          </Badge>
        ))}
      </HStack>
    );
  };

  // Подсчет статистики
  const getStats = () => {
    const stats = {
      total: subscriptions.length,
      office1: subscriptions.filter(s => s.office_1).length,
      office2: subscriptions.filter(s => s.office_2).length,
      office4: subscriptions.filter(s => s.office_4).length,
      office6: subscriptions.filter(s => s.office_6).length,
    };
    return stats;
  };

  const stats = getStats();

  if (loading) {
    return (
      <Flex justify="center" align="center" h="400px" direction="column" gap={4}>
        <Spinner size="xl" color="orange.500" thickness="4px" />
        <Text color="gray.500">Загрузка подписок...</Text>
      </Flex>
    );
  }

  return (
    <Box p={6}>
      {/* Header */}
      <VStack align="stretch" spacing={6}>
        <Flex justify="space-between" align="center">
          <Box>
            <Heading size="lg" mb={2}>
              <Icon as={FaBell} color="orange.500" mr={3} />
              Подписки на офисы
            </Heading>
            <Text color="gray.600">
              Управление подписками пользователей на уведомления о доступности офисов
            </Text>
          </Box>

          <HStack spacing={3}>
            <Button
              leftIcon={<FaBell />}
              colorScheme="orange"
              onClick={onNotifyOpen}
              isDisabled={subscriptions.length === 0}
              size="md"
            >
              Отправить уведомление
            </Button>
          </HStack>
        </Flex>

        {/* Statistics Cards */}
        {subscriptions.length > 0 && (
          <SimpleGrid columns={{ base: 1, md: 5 }} spacing={4}>
            <Card>
              <CardBody>
                <Stat>
                  <StatLabel>Всего подписок</StatLabel>
                  <StatNumber color="orange.500">{stats.total}</StatNumber>
                  <StatHelpText>
                    <Icon as={FaUsers} mr={1} />
                    Активных пользователей
                  </StatHelpText>
                </Stat>
              </CardBody>
            </Card>

            <Card>
              <CardBody>
                <Stat>
                  <StatLabel>Офис на 1 чел.</StatLabel>
                  <StatNumber color="purple.500">{stats.office1}</StatNumber>
                  <StatHelpText>{stats.office1 > 0 ? 'подписчиков' : 'нет подписок'}</StatHelpText>
                </Stat>
              </CardBody>
            </Card>

            <Card>
              <CardBody>
                <Stat>
                  <StatLabel>Офис на 2 чел.</StatLabel>
                  <StatNumber color="blue.500">{stats.office2}</StatNumber>
                  <StatHelpText>{stats.office2 > 0 ? 'подписчиков' : 'нет подписок'}</StatHelpText>
                </Stat>
              </CardBody>
            </Card>

            <Card>
              <CardBody>
                <Stat>
                  <StatLabel>Офис на 4 чел.</StatLabel>
                  <StatNumber color="green.500">{stats.office4}</StatNumber>
                  <StatHelpText>{stats.office4 > 0 ? 'подписчиков' : 'нет подписок'}</StatHelpText>
                </Stat>
              </CardBody>
            </Card>

            <Card>
              <CardBody>
                <Stat>
                  <StatLabel>Офис на 6 чел.</StatLabel>
                  <StatNumber color="orange.500">{stats.office6}</StatNumber>
                  <StatHelpText>{stats.office6 > 0 ? 'подписчиков' : 'нет подписок'}</StatHelpText>
                </Stat>
              </CardBody>
            </Card>
          </SimpleGrid>
        )}

        <Divider />

        {/* Filter */}
        <HStack spacing={3}>
          <Icon as={FaFilter} color="gray.500" />
          <Text fontWeight="medium">Фильтр:</Text>
          <Select
            placeholder="Все размеры офисов"
            value={filterSize || ''}
            onChange={(e) => setFilterSize(e.target.value ? parseInt(e.target.value) : null)}
            w="250px"
            bg="white"
          >
            <option value="1">Офис на 1 человека</option>
            <option value="2">Офис на 2 человека</option>
            <option value="4">Офис на 4 человека</option>
            <option value="6">Офис на 6 человек</option>
          </Select>
          {filterSize && (
            <Button size="sm" variant="ghost" onClick={() => setFilterSize(null)}>
              Сбросить
            </Button>
          )}
        </HStack>

        {/* Subscriptions table or empty state */}
        {subscriptions.length === 0 ? (
          <Card>
            <CardBody>
              <VStack spacing={4} py={10}>
                <Icon as={FaUserPlus} boxSize={16} color="gray.300" />
                <VStack spacing={2}>
                  <Heading size="md" color="gray.600">
                    {filterSize ? 'Нет подписок с выбранным фильтром' : 'Пока нет активных подписок'}
                  </Heading>
                  <Text color="gray.500" textAlign="center" maxW="500px">
                    {filterSize
                      ? `Никто еще не подписался на уведомления об офисах на ${filterSize} чел. Попробуйте выбрать другой размер или посмотреть все подписки.`
                      : 'Когда пользователи начнут подписываться на уведомления о доступности офисов, они появятся здесь.'}
                  </Text>
                </VStack>
                {filterSize && (
                  <Button colorScheme="orange" variant="outline" onClick={() => setFilterSize(null)}>
                    Посмотреть все подписки
                  </Button>
                )}
              </VStack>
            </CardBody>
          </Card>
        ) : (
          <Card>
            <CardBody p={0}>
              <Box overflowX="auto">
                <Table variant="simple">
                  <Thead bg="gray.50">
                    <Tr>
                      <Th>ID</Th>
                      <Th>Пользователь</Th>
                      <Th>Telegram</Th>
                      <Th>Размеры офисов</Th>
                      <Th>Дата подписки</Th>
                      <Th textAlign="right">Действия</Th>
                    </Tr>
                  </Thead>
                  <Tbody>
                    {subscriptions.map((sub) => (
                      <Tr key={sub.id} _hover={{ bg: 'gray.50' }}>
                        <Td fontWeight="medium">#{sub.id}</Td>
                        <Td>
                          <Text fontWeight="medium">{sub.full_name || 'Не указано'}</Text>
                        </Td>
                        <Td>
                          {sub.username ? (
                            <Text color="blue.500" fontWeight="medium">@{sub.username}</Text>
                          ) : (
                            <Text color="gray.400" fontSize="sm">Нет username</Text>
                          )}
                        </Td>
                        <Td>{renderOfficeSizes(sub)}</Td>
                        <Td>
                          <Text fontSize="sm" color="gray.600">
                            {new Date(sub.created_at).toLocaleString('ru-RU', {
                              day: '2-digit',
                              month: '2-digit',
                              year: 'numeric',
                              hour: '2-digit',
                              minute: '2-digit'
                            })}
                          </Text>
                        </Td>
                        <Td textAlign="right">
                          <Button
                            size="sm"
                            colorScheme="red"
                            variant="ghost"
                            leftIcon={<FaTrash />}
                            onClick={() => {
                              setDeleteId(sub.id);
                              onDeleteOpen();
                            }}
                          >
                            Удалить
                          </Button>
                        </Td>
                      </Tr>
                    ))}
                  </Tbody>
                </Table>
              </Box>
            </CardBody>
          </Card>
        )}
      </VStack>

      {/* Notification Modal */}
      <Modal isOpen={isNotifyOpen} onClose={onNotifyClose} size="lg">
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>
            <HStack>
              <Icon as={FaBell} color="orange.500" />
              <Text>Отправить уведомление подписчикам</Text>
            </HStack>
          </ModalHeader>
          <ModalCloseButton />
          <ModalBody>
            <VStack spacing={4} align="stretch">
              <Alert status="info" borderRadius="md">
                <AlertIcon />
                <Box>
                  <AlertTitle fontSize="sm">Выберите получателей</AlertTitle>
                  <AlertDescription fontSize="sm">
                    Вы можете отправить уведомление всем подписчикам или только тем, кто подписан на конкретный размер офиса.
                  </AlertDescription>
                </Box>
              </Alert>

              <Box>
                <Text mb={2} fontWeight="medium">Фильтр по размеру офиса</Text>
                <Select
                  placeholder="📢 Отправить всем подписчикам"
                  value={notifySize || ''}
                  onChange={(e) => setNotifySize(e.target.value ? parseInt(e.target.value) : null)}
                >
                  <option value="1">🏢 Только подписчикам на офисы на 1 чел. ({stats.office1})</option>
                  <option value="2">🏢 Только подписчикам на офисы на 2 чел. ({stats.office2})</option>
                  <option value="4">🏢 Только подписчикам на офисы на 4 чел. ({stats.office4})</option>
                  <option value="6">🏢 Только подписчикам на офисы на 6 чел. ({stats.office6})</option>
                </Select>
                <Text fontSize="xs" color="gray.500" mt={1}>
                  {notifySize
                    ? `Сообщение получат пользователи, подписанные на офисы на ${notifySize} чел.`
                    : 'Сообщение получат все подписчики'}
                </Text>
              </Box>

              <Box>
                <Text mb={2} fontWeight="medium">Текст сообщения</Text>
                <Textarea
                  value={notifyMessage}
                  onChange={(e) => setNotifyMessage(e.target.value)}
                  placeholder="Например: Освободился офис на 4 человека! Успейте забронировать по специальной цене."
                  rows={6}
                  maxLength={1000}
                />
                <HStack justify="space-between" mt={1}>
                  <Text fontSize="xs" color="gray.500">
                    {notifyMessage.length} / 1000 символов
                  </Text>
                  {notifyMessage.length > 800 && (
                    <Text fontSize="xs" color="orange.500">
                      Приближается лимит
                    </Text>
                  )}
                </HStack>
              </Box>
            </VStack>
          </ModalBody>
          <ModalFooter>
            <Button variant="ghost" mr={3} onClick={onNotifyClose}>
              Отмена
            </Button>
            <Button
              colorScheme="orange"
              onClick={handleSendNotification}
              isLoading={sendingNotification}
              loadingText="Отправка..."
              leftIcon={<FaBell />}
            >
              Отправить уведомление
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>

      {/* Delete Confirmation Dialog */}
      <AlertDialog
        isOpen={isDeleteOpen}
        leastDestructiveRef={cancelRef}
        onClose={onDeleteClose}
      >
        <AlertDialogOverlay>
          <AlertDialogContent>
            <AlertDialogHeader fontSize="lg" fontWeight="bold">
              <HStack>
                <Icon as={FaTrash} color="red.500" />
                <Text>Удаление подписки</Text>
              </HStack>
            </AlertDialogHeader>
            <AlertDialogBody>
              <VStack align="start" spacing={3}>
                <Text>
                  Вы уверены, что хотите удалить эту подписку?
                </Text>
                <Alert status="warning" borderRadius="md">
                  <AlertIcon />
                  <Box>
                    <AlertDescription fontSize="sm">
                      Пользователь больше не будет получать уведомления о доступности офисов. Это действие нельзя отменить.
                    </AlertDescription>
                  </Box>
                </Alert>
              </VStack>
            </AlertDialogBody>
            <AlertDialogFooter>
              <Button ref={cancelRef} onClick={onDeleteClose}>
                Отмена
              </Button>
              <Button colorScheme="red" onClick={handleDelete} ml={3}>
                Удалить подписку
              </Button>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialogOverlay>
      </AlertDialog>
    </Box>
  );
};

export default OfficeSubscriptions;
