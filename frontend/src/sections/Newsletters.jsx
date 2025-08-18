// sections/Newsletters.jsx
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
  FiRefreshCw
} from 'react-icons/fi';
import { sizes, styles } from '../styles/styles';
import { newsletterApi, userApi } from '../utils/api';

const Newsletters = ({ newsletters: initialNewsletters = [] }) => {
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

  const toast = useToast();

  // Загрузка пользователей
  useEffect(() => {
    fetchUsers();
    fetchNewsletters();
  }, []);

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
      toast({
        title: 'Ошибка',
        description: 'Не удалось загрузить историю рассылок',
        status: 'error',
        duration: 5000,
      });
    } finally {
      setIsLoading(false);
    }
  };

  // Форматирование текста
  const formatText = (type) => {
    const textarea = document.getElementById('message-textarea');
    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    const selectedText = message.substring(start, end);

    if (!selectedText) {
      toast({
        title: 'Выделите текст',
        description: 'Сначала выделите текст для форматирования',
        status: 'info',
        duration: 2000,
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
      });
      return;
    }

    if (recipientType === 'selected' && selectedUsers.length === 0) {
      toast({
        title: 'Ошибка',
        description: 'Выберите получателей',
        status: 'error',
        duration: 3000,
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

      photos.forEach((photo, index) => {
        formData.append(`photos`, photo.file);
      });

      const result = await newsletterApi.send(formData);

      toast({
        title: 'Успешно',
        description: `Рассылка отправлена ${result.success_count} из ${result.total_count} пользователей`,
        status: 'success',
        duration: 5000,
      });

      // Очищаем форму
      setMessage('');
      setPhotos([]);
      setSelectedUsers([]);
      setRecipientType('all');

      // Обновляем историю
      fetchNewsletters();

    } catch (error) {
      console.error('Ошибка отправки:', error);
      toast({
        title: 'Ошибка отправки',
        description: error.response?.data?.detail || 'Не удалось отправить рассылку',
        status: 'error',
        duration: 5000,
      });
    } finally {
      setIsSending(false);
    }
  };

  // Компонент выбора пользователей
  const UserSelectionModal = () => (
    <Modal isOpen={isUserModalOpen} onClose={() => setUserModalOpen(false)} size="xl">
      <ModalOverlay />
      <ModalContent maxH="80vh">
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

  return (
    <Box p={sizes.content.padding} bg="gray.50" minH={sizes.content.minHeight}>
      <VStack spacing={6} align="stretch">
        {/* Форма отправки */}
        <Card borderRadius={styles.card.borderRadius} boxShadow={styles.card.boxShadow}>
          <CardHeader>
            <Heading size="md">Новая рассылка</Heading>
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

        {/* История рассылок */}
        <Card borderRadius={styles.card.borderRadius} boxShadow={styles.card.boxShadow}>
          <CardHeader>
            <HStack justify="space-between">
              <Heading size="md">История рассылок</Heading>
              <IconButton
                icon={<FiRefreshCw />}
                size="sm"
                variant="ghost"
                onClick={fetchNewsletters}
                isLoading={isLoading}
              />
            </HStack>
          </CardHeader>
          <CardBody>
            {isLoading ? (
              <Box textAlign="center" py={8}>
                <Spinner size="lg" color="purple.500" />
              </Box>
            ) : newsletters.length === 0 ? (
              <Box textAlign="center" py={8}>
                <Text color="gray.500">История рассылок пуста</Text>
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
                          <Badge
                            colorScheme={newsletter.status === 'success' ? 'green' : 'red'}
                          >
                            {newsletter.status === 'success' ? (
                              <HStack spacing={1}>
                                <Icon as={FiCheck} />
                                <Text>Успешно</Text>
                              </HStack>
                            ) : (
                              <HStack spacing={1}>
                                <Icon as={FiAlertCircle} />
                                <Text>Ошибка</Text>
                              </HStack>
                            )}
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
                          <Tooltip label={newsletter.message}>
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
      <UserSelectionModal />
    </Box>
  );
};

export default Newsletters;