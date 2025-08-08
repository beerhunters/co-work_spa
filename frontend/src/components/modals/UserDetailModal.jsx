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
  Image
} from '@chakra-ui/react';
import { FiEdit, FiTrash2, FiUpload } from 'react-icons/fi';
import { userApi } from '../../utils/api';
import { getStatusColor } from '../../styles/styles';

const API_BASE_URL = 'http://localhost/api';

const UserDetailModal = ({ isOpen, onClose, user, onUpdate }) => {
  const [isEditing, setIsEditing] = useState(false);
  const [formData, setFormData] = useState({});
  const [avatarFile, setAvatarFile] = useState(null);
  const [isAvatarModalOpen, setAvatarModalOpen] = useState(false);
  const toast = useToast();

  useEffect(() => {
    if (user) {
      setFormData({
        full_name: user.full_name || '',
        phone: user.phone || '',
        email: user.email || '',
        language_code: user.language_code || 'ru'
      });
    }
  }, [user]);

  // Логика аватара - исправленная с отладкой
  const avatarUrl = avatarFile
    ? URL.createObjectURL(avatarFile)
    : user?.avatar
      ? `${API_BASE_URL}/avatars/${user.avatar}`  // avatar содержит только имя файла
      : `${API_BASE_URL}/avatars/placeholder_avatar.png`;

  const handleSave = async () => {
    try {
      await userApi.update(user.id, formData);

      if (avatarFile) {
        await userApi.uploadAvatar(user.id, avatarFile);
        setAvatarFile(null);
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
      await userApi.deleteAvatar(user.id);
      setAvatarFile(null);

      await onUpdate();

      toast({
        title: 'Аватар удалён',
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

  if (!user) return null;

  return (
    <>
      <Modal isOpen={isOpen} onClose={onClose} size="xl">
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>Пользователь #{user.id}</ModalHeader>
          <ModalCloseButton />
          <ModalBody>
            <VStack spacing={4} align="stretch">
              {/* Аватар */}
              <Box textAlign="center">
                <Image
                  src={avatarUrl}
                  alt="Аватар пользователя"
                  boxSize="120px"
                  borderRadius="full"
                  objectFit="cover"
                  fallbackSrc={`${API_BASE_URL}/avatars/placeholder_avatar.png`}
                  mx="auto"
                  mb={4}
                  cursor="pointer"
                  onClick={() => setAvatarModalOpen(true)}
                  _hover={{ boxShadow: 'md', transform: 'scale(1.05)', transition: '0.2s' }}
                />

                <VStack spacing={2}>
                  <Text fontSize="lg" fontWeight="bold">
                    {user.full_name || 'Не указано'}
                  </Text>
                  <Text fontSize="sm" color="gray.500">
                    @{user.username || 'Не указано'}
                  </Text>
                  <Badge colorScheme="blue">
                    ID: {user.telegram_id}
                  </Badge>
                </VStack>
              </Box>

              {/* Форма */}
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
                    <Text>{user.phone || 'Не указано'}</Text>
                  </HStack>

                  <HStack justify="space-between">
                    <Text fontWeight="bold">Email:</Text>
                    <Text>{user.email || 'Не указано'}</Text>
                  </HStack>

                  <HStack justify="space-between">
                    <Text fontWeight="bold">Язык:</Text>
                    <Text>{user.language_code}</Text>
                  </HStack>

                  <HStack justify="space-between">
                    <Text fontWeight="bold">Успешных броней:</Text>
                    <Badge colorScheme="green">{user.successful_bookings}</Badge>
                  </HStack>

                  <HStack justify="space-between">
                    <Text fontWeight="bold">Приглашено:</Text>
                    <Badge colorScheme="purple">{user.invited_count}</Badge>
                  </HStack>

                  <HStack justify="space-between">
                    <Text fontWeight="bold">Дата регистрации:</Text>
                    <Text>{new Date(user.reg_date || user.first_join_time).toLocaleDateString('ru-RU')}</Text>
                  </HStack>

                  <HStack justify="space-between">
                    <Text fontWeight="bold">Согласие с условиями:</Text>
                    <Badge colorScheme={user.agreed_to_terms ? 'green' : 'red'}>
                      {user.agreed_to_terms ? 'Да' : 'Нет'}
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
              <Button leftIcon={<FiEdit />} colorScheme="purple" onClick={() => setIsEditing(true)}>
                Редактировать
              </Button>
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
                src={avatarUrl}
                alt="Аватар в полном размере"
                boxSize="300px"
                objectFit="contain"
                fallbackSrc={`${API_BASE_URL}/avatars/placeholder_avatar.png`}
                mx="auto"
              />

              <HStack spacing={3}>
                {user.avatar && (
                  <Button
                    leftIcon={<FiTrash2 />}
                    colorScheme="red"
                    variant="outline"
                    onClick={handleAvatarDelete}
                  >
                    Удалить
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