import React, { useState, useEffect } from 'react';
import {
  Box,
  Card,
  CardHeader,
  CardBody,
  Heading,
  VStack,
  HStack,
  Text,
  Icon,
  Button,
  FormControl,
  FormLabel,
  Select,
  Textarea,
  Badge,
  useToast,
  Divider,
  SimpleGrid,
  Image,
  IconButton,
  Checkbox,
  CheckboxGroup,
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalBody,
  ModalFooter,
  ModalCloseButton,
  Spinner,
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  TableContainer,
  Tooltip,
  Input,
  FormHelperText,
  Alert,
  AlertIcon,
  AlertDescription,
  useColorModeValue,
  AlertDialog,
  AlertDialogBody,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogContent,
  AlertDialogOverlay,
  useDisclosure,
} from '@chakra-ui/react';
import {
  FiUsers,
  FiSend,
  FiImage,
  FiX,
  FiCheck,
  FiAlertCircle,
  FiBold,
  FiItalic,
  FiCode,
  FiUnderline,
  FiRefreshCw,
  FiTrash2,
  FiTrash
} from 'react-icons/fi';
import { newsletterApi, userApi } from '../utils/api';

const Newsletters = ({ newsletters: initialNewsletters = [], currentAdmin }) => {
  const [newsletters, setNewsletters] = useState(initialNewsletters);
  const [users, setUsers] = useState([]);
  const [recipientType, setRecipientType] = useState('all');
  const [selectedUsers, setSelectedUsers] = useState([]);
  const [message, setMessage] = useState('');
  const [photos, setPhotos] = useState([]);
  const [isSending, setIsSending] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [isUserModalOpen, setUserModalOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [isDeleting, setIsDeleting] = useState(false);

  const toast = useToast();
  const bgColor = useColorModeValue('gray.50', 'gray.900');
  const cardBg = useColorModeValue('white', 'gray.800');

  const { isOpen: isDeleteOpen, onOpen: onDeleteOpen, onClose: onDeleteClose } = useDisclosure();
  const { isOpen: isClearOpen, onOpen: onClearOpen, onClose: onClearClose } = useDisclosure();
  const cancelRef = React.useRef();

  // Проверка прав доступа
  const canViewNewsletters = currentAdmin?.role === 'super_admin' ||
                           (currentAdmin?.permissions && currentAdmin.permissions.includes('view_newsletters'));

  const canSendNewsletters = currentAdmin?.role === 'super_admin' ||
                           (currentAdmin?.permissions && currentAdmin.permissions.includes('send_newsletters'));

  const canManageNewsletters = currentAdmin?.role === 'super_admin' ||
                             (currentAdmin?.permissions && currentAdmin.permissions.includes('manage_newsletters'));

  // Если нет прав на просмотр, показываем сообщение об ошибке
  if (!canViewNewsletters) {
    return (
      <Box p={8} textAlign="center">
        <Text fontSize="xl" color="red.500" mb={4}>
          Доступ запрещен
        </Text>
        <Text color="gray.500">
          У вас нет прав для просмотра рассылок
        </Text>
      </Box>
    );
  }

  // Загрузка данных при монтировании
  useEffect(() => {
    fetchNewsletters();
    if (canSendNewsletters) {
      fetchUsers();
    }
  }, [canSendNewsletters]);

  const fetchUsers = async () => {
    try {
      const data = await userApi.getAll();
      setUsers(data);
    } catch (error) {
      console.error('Ошибка загрузки пользователей:', error);
      toast({
        title: 'Ошибка',
        description: 'Не удалось загрузить список пользователей',
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    }
  };

  const fetchNewsletters = async () => {
    setIsLoading(true);
    try {
      const data = await newsletterApi.getHistory();
      setNewsletters(data);
    } catch (error) {
      console.error('Ошибка загрузки истории:', error);

      // Проверяем, не связана ли ошибка с правами доступа
      if (error.response?.status === 403) {
        toast({
          title: 'Доступ запрещен',
          description: 'У вас нет прав для просмотра истории рассылок',
          status: 'error',
          duration: 5000,
          isClosable: true,
        });
      } else {
        toast({
          title: 'Ошибка',
          description: 'Не удалось загрузить историю рассылок',
          status: 'error',
          duration: 5000,
          isClosable: true,
        });
      }
    } finally {
      setIsLoading(false);
    }
  };

  // Удаление конкретной рассылки
  const handleDeleteNewsletter = async (newsletter) => {
    setDeleteTarget(newsletter);
    onDeleteOpen();
  };

  const confirmDeleteNewsletter = async () => {
    if (!deleteTarget) return;

    setIsDeleting(true);
    try {
      await newsletterApi.delete(deleteTarget.id);

      toast({
        title: 'Успешно',
        description: 'Рассылка удалена',
        status: 'success',
        duration: 3000,
        isClosable: true,
      });

      // Обновляем список
      await fetchNewsletters();

    } catch (error) {
      console.error('Ошибка удаления рассылки:', error);

      let errorMessage = 'Не удалось удалить рассылку';
      if (error.response?.status === 403) {
        errorMessage = 'У вас нет прав для удаления рассылок';
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
      setDeleteTarget(null);
      onDeleteClose();
    }
  };

  // Очистка всей истории
  const handleClearHistory = () => {
    onClearOpen();
  };

  const confirmClearHistory = async () => {
    setIsDeleting(true);
    try {
      await newsletterApi.clearHistory();

      toast({
        title: 'Успешно',
        description: 'История рассылок очищена',
        status: 'success',
        duration: 3000,
        isClosable: true,
      });

      // Обновляем список
      setNewsletters([]);

    } catch (error) {
      console.error('Ошибка очистки истории:', error);

      let errorMessage = 'Не удалось очистить историю';
      if (error.response?.status === 403) {
        errorMessage = 'У вас нет прав для очистки истории рассылок';
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
      onClearClose();
    }
  };

  // Форматирование текста
  const formatText = (type) => {
    const textarea = document.getElementById('message-textarea');
    if (!textarea) return;

    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    const selectedText = message.substring(start, end);

    if (!selectedText) {
      toast({
        title: 'Выделите текст',
        description: 'Сначала выделите текст для форматирования',
        status: 'info',
        duration: 2000,
        isClosable: true,
      });
      return;
    }

    let formattedText = '';
    switch (type) {
      case 'bold':
        formattedText = `<b>${selectedText}</b>`;
        break;
      case 'italic':
        formattedText = `<i>${selectedText}</i>`;
        break;
      case 'underline':
        formattedText = `<u>${selectedText}</u>`;
        break;
      case 'code':
        formattedText = `<code>${selectedText}</code>`;
        break;
      default:
        formattedText = selectedText;
    }

    const newMessage = message.substring(0, start) + formattedText + message.substring(end);
    setMessage(newMessage);

    // Восстанавливаем фокус и позицию курсора
    setTimeout(() => {
      textarea.focus();
      textarea.setSelectionRange(start + formattedText.length, start + formattedText.length);
    }, 0);
  };

  // Обработка загрузки фото
  const handlePhotoUpload = (e) => {
    const files = Array.from(e.target.files);

    if (photos.length + files.length > 10) {
      toast({
        title: 'Ограничение',
        description: 'Максимум 10 фотографий',
        status: 'warning',
        duration: 3000,
        isClosable: true,
      });
      return;
    }

    const newPhotos = files.map(file => ({
      file,
      preview: URL.createObjectURL(file),
      id: Date.now() + Math.random()
    }));

    setPhotos([...photos, ...newPhotos]);
  };

  // Удаление фото
  const removePhoto = (photoId) => {
    const photo = photos.find(p => p.id === photoId);
    if (photo?.preview) {
      URL.revokeObjectURL(photo.preview);
    }
    setPhotos(photos.filter(p => p.id !== photoId));
  };

  // Фильтрованные пользователи для модального окна
  const filteredUsers = users.filter(user => {
    const query = searchQuery.toLowerCase();
    return (
      user.full_name?.toLowerCase().includes(query) ||
      user.username?.toLowerCase().includes(query) ||
      user.email?.toLowerCase().includes(query) ||
      user.phone?.includes(query)
    );
  });

  // Отправка рассылки
  const handleSendNewsletter = async () => {
    if (!message.trim()) {
      toast({
        title: 'Ошибка',
        description: 'Введите текст сообщения',
        status: 'error',
        duration: 3000,
        isClosable: true,
      });
      return;
    }

    if (recipientType === 'selected' && selectedUsers.length === 0) {
      toast({
        title: 'Ошибка',
        description: 'Выберите получателей',
        status: 'error',
        duration: 3000,
        isClosable: true,
      });
      return;
    }

    setIsSending(true);

    try {
      const formData = new FormData();
      formData.append('message', message);
      formData.append('recipient_type', recipientType);

      if (recipientType === 'selected') {
        selectedUsers.forEach(userId => {
          formData.append('user_ids', userId);
        });
      }

      photos.forEach((photo) => {
        formData.append('photos', photo.file);
      });

      const result = await newsletterApi.send(formData);

      toast({
        title: 'Успешно',
        description: `Рассылка отправлена ${result.success_count} из ${result.total_count} пользователей`,
        status: 'success',
        duration: 5000,
        isClosable: true,
      });

      // Очищаем форму
      setMessage('');
      setPhotos([]);
      setSelectedUsers([]);
      setRecipientType('all');

      // Обновляем историю
      await fetchNewsletters();

    } catch (error) {
      console.error('Ошибка отправки:', error);

      let errorMessage = 'Не удалось отправить рассылку';
      if (error.response?.status === 403) {
        errorMessage = 'У вас нет прав для отправки рассылок';
      } else if (error.response?.data?.detail) {
        errorMessage = error.response.data.detail;
      }

      toast({
        title: 'Ошибка отправки',
        description: errorMessage,
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    } finally {
      setIsSending(false);
    }
  };

  // Компонент выбора пользователей
  const UserSelectionModal = () => (
    <Modal isOpen={isUserModalOpen} onClose={() => setUserModalOpen(false)} size="xl">
      <ModalOverlay />
      <ModalContent maxH="80vh" bg={cardBg}>
        <ModalHeader>Выбор получателей</ModalHeader>
        <ModalCloseButton />
        <ModalBody>
          <VStack spacing={4} align="stretch">
            <Input
              placeholder="Поиск по имени, username, email или телефону..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              mb={2}
            />

            <Box maxH="400px" overflowY="auto">
              <CheckboxGroup value={selectedUsers} onChange={setSelectedUsers}>
                <VStack align="stretch" spacing={2}>
                  {filteredUsers.map(user => (
                    <Checkbox
                      key={user.id}
                      value={user.telegram_id?.toString()}
                      isDisabled={!user.telegram_id}
                    >
                      <HStack spacing={3} flex={1}>
                        <Text fontWeight="medium">
                          {user.full_name || 'Без имени'}
                        </Text>
                        {user.username && (
                          <Badge colorScheme="blue">@{user.username}</Badge>
                        )}
                        {!user.telegram_id && (
                          <Badge colorScheme="red">Нет Telegram ID</Badge>
                        )}
                      </HStack>
                    </Checkbox>
                  ))}
                </VStack>
              </CheckboxGroup>
            </Box>

            <Text fontSize="sm" color="gray.600">
              Выбрано: {selectedUsers.length} из {users.filter(u => u.telegram_id).length} пользователей
            </Text>
          </VStack>
        </ModalBody>
        <ModalFooter>
          <Button variant="ghost" mr={3} onClick={() => setUserModalOpen(false)}>
            Отмена
          </Button>
          <Button colorScheme="purple" onClick={() => setUserModalOpen(false)}>
            Применить
          </Button>
        </ModalFooter>
      </ModalContent>
    </Modal>
  );

  // Получение цвета статуса
  const getStatusColor = (status) => {
    switch (status) {
      case 'success':
        return 'green';
      case 'failed':
        return 'red';
      case 'partial':
        return 'orange';
      default:
        return 'gray';
    }
  };

  // Получение иконки статуса
  const getStatusIcon = (status) => {
    switch (status) {
      case 'success':
        return FiCheck;
      case 'failed':
        return FiAlertCircle;
      case 'partial':
        return FiAlertCircle;
      default:
        return FiAlertCircle;
    }
  };

  // Получение текста статуса
  const getStatusText = (status) => {
    switch (status) {
      case 'success':
        return 'Успешно';
      case 'failed':
        return 'Ошибка';
      case 'partial':
        return 'Частично';
      default:
        return 'Неизвестно';
    }
  };

  return (
    <Box p={6} bg={bgColor} minH="calc(100vh - 64px)">
      <VStack spacing={6} align="stretch">
        {/* Форма отправки - показываем только если есть права */}
        {canSendNewsletters && (
          <Card bg={cardBg} borderRadius="lg" boxShadow="sm">
            <CardHeader>
              <Heading size="md" color="purple.600">
                <HStack>
                  <Icon as={FiSend} />
                  <Text>Новая рассылка</Text>
                </HStack>
              </Heading>
            </CardHeader>
            <CardBody>
              <VStack spacing={4} align="stretch">
                {/* Выбор получателей */}
                <FormControl>
                  <FormLabel>Получатели</FormLabel>
                  <HStack spacing={3}>
                    <Select
                      value={recipientType}
                      onChange={(e) => setRecipientType(e.target.value)}
                      maxW="200px"
                    >
                      <option value="all">Все пользователи</option>
                      <option value="selected">Выбранные</option>
                    </Select>

                    {recipientType === 'selected' && (
                      <>
                        <Button
                          size="sm"
                          leftIcon={<FiUsers />}
                          onClick={() => setUserModalOpen(true)}
                          variant="outline"
                          colorScheme="purple"
                        >
                          Выбрать ({selectedUsers.length})
                        </Button>
                        {selectedUsers.length > 0 && (
                          <Button
                            size="sm"
                            variant="ghost"
                            colorScheme="red"
                            onClick={() => setSelectedUsers([])}
                          >
                            Очистить
                          </Button>
                        )}
                      </>
                    )}
                  </HStack>
                  <FormHelperText>
                    {recipientType === 'all'
                      ? `Будет отправлено всем ${users.filter(u => u.telegram_id).length} пользователям`
                      : `Выбрано ${selectedUsers.length} получателей`}
                  </FormHelperText>
                </FormControl>

                {/* Сообщение с форматированием */}
                <FormControl>
                  <FormLabel>Сообщение</FormLabel>
                  <VStack align="stretch" spacing={2}>
                    <HStack spacing={2}>
                      <Tooltip label="Жирный">
                        <IconButton
                          icon={<FiBold />}
                          size="sm"
                          variant="outline"
                          onClick={() => formatText('bold')}
                        />
                      </Tooltip>
                      <Tooltip label="Курсив">
                        <IconButton
                          icon={<FiItalic />}
                          size="sm"
                          variant="outline"
                          onClick={() => formatText('italic')}
                        />
                      </Tooltip>
                      <Tooltip label="Подчеркнутый">
                        <IconButton
                          icon={<FiUnderline />}
                          size="sm"
                          variant="outline"
                          onClick={() => formatText('underline')}
                        />
                      </Tooltip>
                      <Tooltip label="Моноширинный">
                        <IconButton
                          icon={<FiCode />}
                          size="sm"
                          variant="outline"
                          onClick={() => formatText('code')}
                        />
                      </Tooltip>
                    </HStack>

                    <Textarea
                      id="message-textarea"
                      value={message}
                      onChange={(e) => setMessage(e.target.value)}
                      placeholder="Введите текст сообщения... Используйте HTML-теги для форматирования: <b>жирный</b>, <i>курсив</i>, <u>подчеркнутый</u>, <code>код</code>"
                      minH="150px"
                      resize="vertical"
                    />
                    <FormHelperText>
                      Поддерживаются HTML-теги: &lt;b&gt;, &lt;i&gt;, &lt;u&gt;, &lt;code&gt;, &lt;a href=""&gt;
                    </FormHelperText>
                  </VStack>
                </FormControl>

                {/* Загрузка фото */}
                <FormControl>
                  <FormLabel>Фотографии (до 10 штук)</FormLabel>
                  <VStack align="stretch" spacing={3}>
                    <Input
                      type="file"
                      accept="image/*"
                      multiple
                      onChange={handlePhotoUpload}
                      display="none"
                      id="photo-upload"
                    />
                    <Button
                      as="label"
                      htmlFor="photo-upload"
                      leftIcon={<FiImage />}
                      variant="outline"
                      cursor="pointer"
                      isDisabled={photos.length >= 10}
                      colorScheme="blue"
                    >
                      Добавить фото ({photos.length}/10)
                    </Button>

                    {photos.length > 0 && (
                      <SimpleGrid columns={5} spacing={2}>
                        {photos.map(photo => (
                          <Box key={photo.id} position="relative">
                            <Image
                              src={photo.preview}
                              alt="Preview"
                              boxSize="100px"
                              objectFit="cover"
                              borderRadius="md"
                              border="1px solid"
                              borderColor="gray.200"
                            />
                            <IconButton
                              icon={<FiX />}
                              size="xs"
                              position="absolute"
                              top={1}
                              right={1}
                              colorScheme="red"
                              onClick={() => removePhoto(photo.id)}
                            />
                          </Box>
                        ))}
                      </SimpleGrid>
                    )}
                  </VStack>
                </FormControl>

                {/* Предупреждение */}
                {message.includes('<') && (
                  <Alert status="info" borderRadius="md">
                    <AlertIcon />
                    <AlertDescription>
                      Убедитесь, что HTML-теги закрыты правильно для корректного отображения
                    </AlertDescription>
                  </Alert>
                )}

                {/* Кнопка отправки */}
                <Button
                  leftIcon={<FiSend />}
                  colorScheme="purple"
                  size="lg"
                  onClick={handleSendNewsletter}
                  isLoading={isSending}
                  loadingText="Отправка..."
                  isDisabled={!message.trim()}
                >
                  Отправить рассылку
                </Button>
              </VStack>
            </CardBody>
          </Card>
        )}

        {/* История рассылок */}
        <Card bg={cardBg} borderRadius="lg" boxShadow="sm">
          <CardHeader>
            <HStack justify="space-between">
              <Heading size="md">
                <HStack>
                  <Icon as={FiUsers} color="blue.500" />
                  <Text>История рассылок</Text>
                </HStack>
              </Heading>
              <HStack spacing={2}>
                <IconButton
                  icon={<FiRefreshCw />}
                  size="sm"
                  variant="ghost"
                  onClick={fetchNewsletters}
                  isLoading={isLoading}
                  colorScheme="blue"
                  aria-label="Обновить"
                />
                {canManageNewsletters && newsletters.length > 0 && (
                  <Button
                    leftIcon={<FiTrash />}
                    size="sm"
                    variant="outline"
                    colorScheme="red"
                    onClick={handleClearHistory}
                  >
                    Очистить историю
                  </Button>
                )}
              </HStack>
            </HStack>
          </CardHeader>
          <CardBody>
            {isLoading ? (
              <Box textAlign="center" py={8}>
                <Spinner size="lg" color="purple.500" />
                <Text mt={4} color="gray.500">Загрузка истории рассылок...</Text>
              </Box>
            ) : newsletters.length === 0 ? (
              <Box textAlign="center" py={8}>
                <Text color="gray.500" fontSize="lg">История рассылок пуста</Text>
                {canSendNewsletters && (
                  <Text color="gray.400" fontSize="sm" mt={2}>
                    Отправьте первую рассылку, чтобы увидеть её здесь
                  </Text>
                )}
              </Box>
            ) : (
              <TableContainer>
                <Table variant="simple" size="sm">
                  <Thead>
                    <Tr>
                      <Th>Дата отправки</Th>
                      <Th>Статус</Th>
                      <Th>Получатели</Th>
                      <Th>Сообщение</Th>
                      <Th>Фото</Th>
                      {canManageNewsletters && <Th>Действия</Th>}
                    </Tr>
                  </Thead>
                  <Tbody>
                    {newsletters.map(newsletter => (
                      <Tr key={newsletter.id}>
                        <Td>
                          <Text fontSize="sm">
                            {new Date(newsletter.created_at).toLocaleString('ru-RU')}
                          </Text>
                        </Td>
                        <Td>
                          <Badge colorScheme={getStatusColor(newsletter.status)}>
                            <HStack spacing={1}>
                              <Icon as={getStatusIcon(newsletter.status)} />
                              <Text>{getStatusText(newsletter.status)}</Text>
                            </HStack>
                          </Badge>
                        </Td>
                        <Td>
                          <VStack align="start" spacing={0}>
                            <Text fontSize="sm" fontWeight="medium">
                              {newsletter.success_count}/{newsletter.total_count}
                            </Text>
                            <Text fontSize="xs" color="gray.500">
                              успешно
                            </Text>
                          </VStack>
                        </Td>
                        <Td maxW="300px">
                          <Tooltip label={newsletter.message} hasArrow>
                            <Text fontSize="sm" noOfLines={2}>
                              {newsletter.message}
                            </Text>
                          </Tooltip>
                        </Td>
                        <Td>
                          {newsletter.photo_count > 0 && (
                            <Badge colorScheme="blue">
                              <HStack spacing={1}>
                                <Icon as={FiImage} />
                                <Text>{newsletter.photo_count}</Text>
                              </HStack>
                            </Badge>
                          )}
                        </Td>
                        {canManageNewsletters && (
                          <Td>
                            <Tooltip label="Удалить рассылку">
                              <IconButton
                                icon={<FiTrash2 />}
                                size="sm"
                                variant="ghost"
                                colorScheme="red"
                                onClick={() => handleDeleteNewsletter(newsletter)}
                                aria-label="Удалить рассылку"
                              />
                            </Tooltip>
                          </Td>
                        )}
                      </Tr>
                    ))}
                  </Tbody>
                </Table>
              </TableContainer>
            )}
          </CardBody>
        </Card>
      </VStack>

      {/* Модальное окно выбора пользователей */}
      {canSendNewsletters && <UserSelectionModal />}

      {/* Диалог подтверждения удаления рассылки */}
      <AlertDialog
        isOpen={isDeleteOpen}
        leastDestructiveRef={cancelRef}
        onClose={onDeleteClose}
      >
        <AlertDialogOverlay>
          <AlertDialogContent>
            <AlertDialogHeader fontSize="lg" fontWeight="bold">
              Удалить рассылку
            </AlertDialogHeader>

            <AlertDialogBody>
              Вы уверены, что хотите удалить эту рассылку?
              <Box mt={2} p={3} bg="gray.50" borderRadius="md">
                <Text fontSize="sm" fontWeight="medium">
                  {deleteTarget?.message.substring(0, 100)}
                  {deleteTarget?.message.length > 100 ? '...' : ''}
                </Text>
                <Text fontSize="xs" color="gray.500" mt={1}>
                  Отправлено: {deleteTarget && new Date(deleteTarget.created_at).toLocaleString('ru-RU')}
                </Text>
              </Box>
              <Text mt={2} color="red.500" fontSize="sm">
                Это действие нельзя отменить.
              </Text>
            </AlertDialogBody>

            <AlertDialogFooter>
              <Button ref={cancelRef} onClick={onDeleteClose}>
                Отмена
              </Button>
              <Button
                colorScheme="red"
                onClick={confirmDeleteNewsletter}
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

      {/* Диалог подтверждения очистки истории */}
      <AlertDialog
        isOpen={isClearOpen}
        leastDestructiveRef={cancelRef}
        onClose={onClearClose}
      >
        <AlertDialogOverlay>
          <AlertDialogContent>
            <AlertDialogHeader fontSize="lg" fontWeight="bold">
              Очистить всю историю рассылок
            </AlertDialogHeader>

            <AlertDialogBody>
              Вы уверены, что хотите удалить <strong>все рассылки</strong> из истории?
              <Box mt={2} p={3} bg="red.50" borderRadius="md" borderLeft="4px solid" borderColor="red.400">
                <Text fontSize="sm" color="red.700">
                  ⚠️ Будет удалено {newsletters.length} рассылок
                </Text>
                <Text fontSize="xs" color="red.600" mt={1}>
                  Это действие нельзя отменить!
                </Text>
              </Box>
            </AlertDialogBody>

            <AlertDialogFooter>
              <Button ref={cancelRef} onClick={onClearClose}>
                Отмена
              </Button>
              <Button
                colorScheme="red"
                onClick={confirmClearHistory}
                ml={3}
                isLoading={isDeleting}
                loadingText="Очистка..."
              >
                Очистить всё
              </Button>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialogOverlay>
      </AlertDialog>
    </Box>
  );
};

export default Newsletters;