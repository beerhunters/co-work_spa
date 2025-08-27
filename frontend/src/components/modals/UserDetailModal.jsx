import React, { useState, useEffect } from 'react';
import {
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalBody,
  ModalCloseButton,
  VStack,
  HStack,
  Text,
  Button,
  Input,
  FormControl,
  FormLabel,
  Badge,
  useToast,
  Modal as ChakraModal,
  ModalFooter,
  Box,
  Image,
  Link
} from '@chakra-ui/react';
import { FiEdit, FiTrash2, FiUpload, FiExternalLink } from 'react-icons/fi';
import { userApi } from '../../utils/api';
import { getStatusColor } from '../../styles/styles';

// const API_BASE_URL = process.env.REACT_APP_API_BASE_URL || 'http://localhost/api';
const API_BASE_URL = 'https://parta.webhop.me/api';

// Утилита для получения URL аватара с защитой от кэширования
const getAvatarUrl = (avatar, forceRefresh = false) => {
  // ИСПРАВЛЕНИЕ: Если аватар отсутствует или null, всегда возвращаем placeholder
  if (!avatar || avatar === 'placeholder_avatar.png' || avatar === null) {
    return `${API_BASE_URL}/avatars/placeholder_avatar.png?v=${Date.now()}`;
  }

  // Добавляем timestamp для предотвращения кэширования
  const timestamp = forceRefresh ? Date.now() : new Date().getTime();
  return `${API_BASE_URL}/avatars/${avatar}?v=${timestamp}`;
};

const UserDetailModal = ({ isOpen, onClose, user, onUpdate }) => {
  const [isEditing, setIsEditing] = useState(false);
  const [formData, setFormData] = useState({});
  const [avatarFile, setAvatarFile] = useState(null);
  const [isAvatarModalOpen, setAvatarModalOpen] = useState(false);
  const [isDownloadingAvatar, setIsDownloadingAvatar] = useState(false);
  const [avatarVersion, setAvatarVersion] = useState(Date.now()); // Для форсированного обновления
  const [currentUser, setCurrentUser] = useState(user); // Локальное состояние пользователя
  const toast = useToast();

  useEffect(() => {
    if (user) {
      setCurrentUser(user); // Обновляем локальное состояние
      setFormData({
        full_name: user.full_name || '',
        phone: user.phone || '',
        email: user.email || '',
        language_code: user.language_code || 'ru'
      });
      // Обновляем версию при изменении пользователя
      setAvatarVersion(Date.now());
    }
  }, [user]);

  // ИСПРАВЛЕНИЕ: Проверяем локальное состояние пользователя
  const isPlaceholderAvatar = !currentUser?.avatar || currentUser.avatar === 'placeholder_avatar.png' || currentUser.avatar === null;

  // URL аватара с версионированием - используем локальное состояние
  const avatarUrl = avatarFile
    ? URL.createObjectURL(avatarFile)
    : getAvatarUrl(currentUser?.avatar, true);

  // Формирование ссылок
  const getTelegramUrl = (username) => {
    if (!username) return null;
    const cleanUsername = username.startsWith('@') ? username.slice(1) : username;
    return `https://t.me/${cleanUsername}`;
  };

  const getMailtoUrl = (email) => {
    if (!email) return null;
    return `mailto:${email}`;
  };

  const handleDownloadTelegramAvatar = async () => {
    setIsDownloadingAvatar(true);
    try {
      console.log('Начинаем скачивание аватара из Telegram для пользователя:', currentUser.id);

      const result = await userApi.downloadTelegramAvatar(currentUser.id);
      console.log('Аватар успешно скачан:', result);

      // ИСПРАВЛЕНИЕ: Обновляем локальное состояние пользователя
      setCurrentUser(prev => ({
        ...prev,
        avatar: result.avatar_filename
      }));

      // Форсируем обновление версии для перезагрузки изображения
      setAvatarVersion(Date.now());

      // Обновляем данные пользователя
      await onUpdate();

      // Закрываем модальное окно аватара
      setAvatarModalOpen(false);

      toast({
        title: 'Аватар загружен',
        description: 'Аватар успешно скачан из Telegram и сохранен',
        status: 'success',
        duration: 4000,
        isClosable: true,
      });

    } catch (error) {
      console.error('Ошибка при скачивании аватара:', error);

      let errorMessage = 'Произошла ошибка при скачивании аватара из Telegram';
      if (error.message) {
        errorMessage = error.message;
      }

      toast({
        title: 'Не удалось загрузить аватар',
        description: errorMessage,
        status: 'error',
        duration: 6000,
        isClosable: true,
      });
    } finally {
      setIsDownloadingAvatar(false);
    }
  };

  const handleSave = async () => {
    try {
      await userApi.update(currentUser.id, formData);

      if (avatarFile) {
        const uploadResult = await userApi.uploadAvatar(currentUser.id, avatarFile);
        setAvatarFile(null);

        // ИСПРАВЛЕНИЕ: Обновляем локальное состояние пользователя
        setCurrentUser(prev => ({
          ...prev,
          avatar: uploadResult.filename
        }));

        // Форсируем обновление версии
        setAvatarVersion(Date.now());
      }

      await onUpdate();

      toast({
        title: 'Пользователь обновлён',
        status: 'success',
        duration: 3000,
        isClosable: true,
      });

      setIsEditing(false);
    } catch (error) {
      console.error('Ошибка при сохранении:', error);
      toast({
        title: 'Ошибка при сохранении',
        description: error.response?.data?.detail || 'Произошла ошибка',
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    }
  };

  const handleAvatarDelete = async () => {
    try {
      console.log('Удаляем аватар для пользователя:', currentUser.id);

      const result = await userApi.deleteAvatar(currentUser.id);
      console.log('Результат удаления аватара:', result);

      setAvatarFile(null);

      // ИСПРАВЛЕНИЕ: Сразу обновляем локальное состояние пользователя
      setCurrentUser(prev => ({
        ...prev,
        avatar: null
      }));

      // Форсируем обновление версии
      setAvatarVersion(Date.now());

      // Обновляем общие данные
      await onUpdate();

      toast({
        title: 'Аватар удалён',
        description: 'Аватар пользователя успешно удален',
        status: 'success',
        duration: 3000,
        isClosable: true,
      });

      setAvatarModalOpen(false);
    } catch (error) {
      console.error('Ошибка при удалении аватара:', error);
      toast({
        title: 'Ошибка при удалении аватара',
        description: error.response?.data?.detail || 'Произошла ошибка',
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    }
  };

  // Функция для форсированной перезагрузки изображения
  const handleImageError = (e) => {
    console.log('Ошибка загрузки изображения, переключаемся на placeholder');

    // Если это не placeholder, устанавливаем placeholder
    if (!e.target.src.includes('placeholder_avatar.png')) {
      e.target.src = `${API_BASE_URL}/avatars/placeholder_avatar.png?v=${Date.now()}`;
    }
  };

  if (!currentUser) return null;

  const telegramUrl = getTelegramUrl(currentUser.username);
  const mailtoUrl = getMailtoUrl(currentUser.email);

  return (
    <>
      <Modal isOpen={isOpen} onClose={onClose} size="xl">
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>Пользователь #{currentUser.id}</ModalHeader>
          <ModalCloseButton />
          <ModalBody>
            <VStack spacing={4} align="stretch">
              {/* Аватар с версионированием */}
              <Box textAlign="center">
                <Image
                  key={`avatar-${currentUser.id}-${avatarVersion}`} // Ключ для форсированного обновления
                  src={`${avatarUrl}&t=${avatarVersion}`} // Дополнительный параметр времени
                  alt="Аватар пользователя"
                  boxSize="120px"
                  borderRadius="full"
                  objectFit="cover"
                  fallbackSrc={`${API_BASE_URL}/avatars/placeholder_avatar.png?v=${Date.now()}`}
                  mx="auto"
                  mb={4}
                  cursor="pointer"
                  onClick={() => setAvatarModalOpen(true)}
                  onError={handleImageError}
                  _hover={{ boxShadow: 'md', transform: 'scale(1.05)', transition: '0.2s' }}
                  loading="eager" // Отключаем lazy loading
                />

                {/* Кнопка загрузки аватара из Telegram */}
                {isPlaceholderAvatar && (
                  <Button
                    leftIcon={<FiUpload />}
                    colorScheme="blue"
                    variant="outline"
                    size="sm"
                    onClick={handleDownloadTelegramAvatar}
                    isLoading={isDownloadingAvatar}
                    loadingText="Загружаем..."
                    mt={2}
                  >
                    Загрузить из Telegram
                  </Button>
                )}

                <VStack spacing={2}>
                  <Text fontSize="lg" fontWeight="bold">
                    {currentUser.full_name || 'Не указано'}
                  </Text>

                  {currentUser.username ? (
                    <Link
                      href={telegramUrl}
                      isExternal
                      color="blue.500"
                      fontSize="sm"
                      _hover={{
                        color: 'blue.600',
                        textDecoration: 'underline'
                      }}
                      display="flex"
                      alignItems="center"
                      gap={1}
                    >
                      @{currentUser.username}
                      <FiExternalLink size={12} />
                    </Link>
                  ) : (
                    <Text fontSize="sm" color="gray.500">
                      @Не указано
                    </Text>
                  )}

                  <Badge colorScheme="blue">
                    ID: {currentUser.telegram_id}
                  </Badge>
                </VStack>
              </Box>

              {/* Форма редактирования */}
              {isEditing ? (
                <VStack spacing={3} align="stretch">
                  <FormControl>
                    <FormLabel>Полное имя</FormLabel>
                    <Input
                      value={formData.full_name}
                      onChange={(e) => setFormData({...formData, full_name: e.target.value})}
                      placeholder="Введите полное имя"
                    />
                  </FormControl>

                  <FormControl>
                    <FormLabel>Телефон</FormLabel>
                    <Input
                      value={formData.phone}
                      onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                      placeholder="Введите телефон"
                    />
                  </FormControl>

                  <FormControl>
                    <FormLabel>Email</FormLabel>
                    <Input
                      type="email"
                      value={formData.email}
                      onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                      placeholder="Введите email"
                    />
                  </FormControl>

                  <FormControl>
                    <FormLabel>Язык</FormLabel>
                    <Input
                      value={formData.language_code}
                      onChange={(e) => setFormData({ ...formData, language_code: e.target.value })}
                      placeholder="Код языка"
                    />
                  </FormControl>

                  <FormControl>
                    <FormLabel>Новый аватар</FormLabel>
                    <Input
                      type="file"
                      accept="image/*"
                      onChange={(e) => setAvatarFile(e.target.files[0])}
                    />
                  </FormControl>
                </VStack>
              ) : (
                <VStack spacing={3} align="stretch">
                  <HStack justify="space-between">
                    <Text fontWeight="bold">Телефон:</Text>
                    <Text>{currentUser.phone || 'Не указано'}</Text>
                  </HStack>

                  <HStack justify="space-between">
                    <Text fontWeight="bold">Email:</Text>
                    {currentUser.email && mailtoUrl ? (
                      <Link
                        href={mailtoUrl}
                        color="blue.500"
                        _hover={{
                          color: 'blue.600',
                          textDecoration: 'underline'
                        }}
                        display="flex"
                        alignItems="center"
                        gap={1}
                      >
                        {currentUser.email}
                        <FiExternalLink size={12} />
                      </Link>
                    ) : (
                      <Text>Не указано</Text>
                    )}
                  </HStack>

                  <HStack justify="space-between">
                    <Text fontWeight="bold">Язык:</Text>
                    <Text>{currentUser.language_code}</Text>
                  </HStack>

                  <HStack justify="space-between">
                    <Text fontWeight="bold">Успешных броней:</Text>
                    <Badge colorScheme="green">{currentUser.successful_bookings}</Badge>
                  </HStack>

                  <HStack justify="space-between">
                    <Text fontWeight="bold">Приглашено:</Text>
                    <Badge colorScheme="purple">{currentUser.invited_count}</Badge>
                  </HStack>

                  <HStack justify="space-between">
                    <Text fontWeight="bold">Дата регистрации:</Text>
                    <Text>{new Date(currentUser.reg_date || currentUser.first_join_time).toLocaleDateString('ru-RU')}</Text>
                  </HStack>

                  <HStack justify="space-between">
                    <Text fontWeight="bold">Согласие с условиями:</Text>
                    <Badge colorScheme={currentUser.agreed_to_terms ? 'green' : 'red'}>
                      {currentUser.agreed_to_terms ? 'Да' : 'Нет'}
                    </Badge>
                  </HStack>
                </VStack>
              )}
            </VStack>
          </ModalBody>

          <ModalFooter>
            {isEditing ? (
              <HStack spacing={3}>
                <Button onClick={() => setIsEditing(false)}>Отмена</Button>
                <Button colorScheme="purple" onClick={handleSave}>
                  Сохранить
                </Button>
              </HStack>
            ) : (
              <HStack spacing={3}>
                <Button leftIcon={<FiEdit />} colorScheme="purple" onClick={() => setIsEditing(true)}>
                  Редактировать
                </Button>

                {telegramUrl && (
                  <Button
                    as={Link}
                    href={telegramUrl}
                    isExternal
                    leftIcon={<FiExternalLink />}
                    colorScheme="blue"
                    variant="outline"
                    size="sm"
                  >
                    Telegram
                  </Button>
                )}

                {mailtoUrl && (
                  <Button
                    as={Link}
                    href={mailtoUrl}
                    leftIcon={<FiExternalLink />}
                    colorScheme="green"
                    variant="outline"
                    size="sm"
                  >
                    Email
                  </Button>
                )}
              </HStack>
            )}
          </ModalFooter>
        </ModalContent>
      </Modal>

      {/* Модальное окно для аватара */}
      <ChakraModal isOpen={isAvatarModalOpen} onClose={() => setAvatarModalOpen(false)} size="xl">
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>Аватар пользователя</ModalHeader>
          <ModalCloseButton />
          <ModalBody>
            <VStack spacing={4}>
              <Image
                key={`modal-avatar-${currentUser.id}-${avatarVersion}`}
                src={`${avatarUrl}&t=${avatarVersion}`}
                alt="Аватар в полном размере"
                boxSize="300px"
                objectFit="contain"
                fallbackSrc={`${API_BASE_URL}/avatars/placeholder_avatar.png?v=${Date.now()}`}
                mx="auto"
                onError={handleImageError}
                loading="eager"
              />

              <HStack spacing={3}>
                {currentUser.avatar && !isPlaceholderAvatar && (
                  <Button
                    leftIcon={<FiTrash2 />}
                    colorScheme="red"
                    variant="outline"
                    onClick={handleAvatarDelete}
                  >
                    Удалить
                  </Button>
                )}

                {isPlaceholderAvatar && (
                  <Button
                    leftIcon={<FiUpload />}
                    colorScheme="blue"
                    variant="outline"
                    onClick={handleDownloadTelegramAvatar}
                    isLoading={isDownloadingAvatar}
                    loadingText="Загружаем..."
                  >
                    Загрузить из Telegram
                  </Button>
                )}
              </HStack>

              <input
                id="avatar-upload"
                type="file"
                accept="image/*"
                style={{ display: 'none' }}
                onChange={(e) => setAvatarFile(e.target.files[0])}
              />
            </VStack>
          </ModalBody>
        </ModalContent>
      </ChakraModal>
    </>
  );
};

export default UserDetailModal;