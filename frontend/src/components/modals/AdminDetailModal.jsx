import React, { useState, useEffect } from 'react';
import {
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalFooter,
  ModalBody,
  ModalCloseButton,
  Button,
  VStack,
  HStack,
  FormControl,
  FormLabel,
  Input,
  Switch,
  Badge,
  Text,
  Divider,
  Alert,
  AlertIcon,
  AlertDescription,
  AlertDialog,
  AlertDialogBody,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogContent,
  AlertDialogOverlay,
  useDisclosure,
  useToast,
  useColorModeValue,
  Box,
  Checkbox,
  CheckboxGroup,
  SimpleGrid,
  Accordion,
  AccordionItem,
  AccordionButton,
  AccordionPanel,
  AccordionIcon,
  FormErrorMessage
} from '@chakra-ui/react';
import { adminApi } from '../../utils/api';
import { getStatusColor } from '../../styles/styles';

const AdminDetailModal = ({ isOpen, onClose, admin, onUpdate, currentAdmin }) => {
  const [isEditing, setIsEditing] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [availablePermissions, setAvailablePermissions] = useState({ permissions: [] });
  const [errors, setErrors] = useState({});

  const [formData, setFormData] = useState({
    login: '',
    password: '',
    permissions: [],
    is_active: true
  });

  const { isOpen: deleteDialogOpen, onOpen: openDeleteDialog, onClose: closeDeleteDialog } = useDisclosure();
  const toast = useToast();
  const cancelRef = React.useRef();
  const bgColor = useColorModeValue('white', 'gray.800');

  // Режим создания нового админа
  const isCreateMode = !admin;

  useEffect(() => {
    if (isOpen) {
      if (admin) {
        setFormData({
          login: admin.login || '',
          password: '',
          permissions: admin.permissions || [],
          is_active: admin.is_active !== undefined ? admin.is_active : true
        });
        setIsEditing(false);
      } else {
        // Режим создания
        setFormData({
          login: '',
          password: '',
          permissions: [],
          is_active: true
        });
        setIsEditing(true);
      }
      setErrors({});
      loadAvailablePermissions();
    }
  }, [isOpen, admin]);

  const loadAvailablePermissions = async () => {
    try {
      const permissions = await adminApi.getAvailablePermissions();
      setAvailablePermissions(permissions);
    } catch (error) {
      console.error('Ошибка загрузки разрешений:', error);
      toast({
        title: 'Ошибка',
        description: 'Не удалось загрузить список разрешений',
        status: 'error',
        duration: 3000,
        isClosable: true,
      });
    }
  };

  const handleSelectAllPermissions = () => {
    const allPermissions = availablePermissions.permissions.map(p =>
      typeof p === 'string' ? p : p.value
    );
    setFormData({...formData, permissions: allPermissions});
    toast({
      title: 'Выбраны все права',
      status: 'success',
      duration: 2000,
      isClosable: true,
    });
  };

  const handleDeselectAllPermissions = () => {
    setFormData({...formData, permissions: []});
    toast({
      title: 'Права сняты',
      status: 'info',
      duration: 2000,
      isClosable: true,
    });
  };

  const getRoleLabel = (role) => {
    const labels = {
      'super_admin': 'Главный администратор',
      'manager': 'Менеджер'
    };
    return labels[role] || role;
  };

  const getRoleColor = (role) => {
    return role === 'super_admin' ? 'purple' : 'blue';
  };

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

  const validateForm = () => {
    const newErrors = {};

    if (!formData.login.trim()) {
      newErrors.login = 'Логин обязателен';
    } else if (formData.login.length < 3) {
      newErrors.login = 'Логин должен содержать минимум 3 символа';
    } else if (!/^[a-zA-Z0-9_-]+$/.test(formData.login)) {
      newErrors.login = 'Логин может содержать только буквы, цифры, дефисы и подчеркивания';
    }

    if (isCreateMode && !formData.password) {
      newErrors.password = 'Пароль обязателен для нового администратора';
    } else if (formData.password && formData.password.length < 6) {
      newErrors.password = 'Пароль должен содержать минимум 6 символов';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSave = async () => {
    if (!validateForm()) {
      return;
    }

    setIsLoading(true);
    try {
      const submitData = {
        login: formData.login.trim(),
        permissions: formData.permissions,
        is_active: formData.is_active
      };

      if (formData.password.trim()) {
        submitData.password = formData.password;
      }

      let result;
      if (isCreateMode) {
        result = await adminApi.create(submitData);
        toast({
          title: 'Администратор создан',
          description: `Администратор ${result.login} успешно создан`,
          status: 'success',
          duration: 3000,
          isClosable: true,
        });
        // После создания закрываем модалку
        handleClose();
      } else {
        result = await adminApi.update(admin.id, submitData);
        toast({
          title: 'Администратор обновлен',
          description: `Администратор ${result.login} успешно обновлен`,
          status: 'success',
          duration: 3000,
          isClosable: true,
        });
        setIsEditing(false);
      }

      // Обновляем данные в родительском компоненте
      if (onUpdate) {
        await onUpdate();
      }

    } catch (error) {
      console.error('Ошибка при сохранении администратора:', error);

      let errorMessage = 'Не удалось сохранить администратора';

      if (error.message) {
        errorMessage = error.message;

        // Показываем ошибку поля, если это ошибка уникальности логина
        if (error.message.includes('уже существует')) {
          setErrors({ login: 'Администратор с таким логином уже существует' });
        }
      }

      toast({
        title: 'Ошибка',
        description: errorMessage,
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleCancel = () => {
    if (isCreateMode) {
      handleClose();
    } else if (isEditing) {
      // Отменяем редактирование - сбрасываем форму
      setFormData({
        login: admin.login || '',
        password: '',
        permissions: admin.permissions || [],
        is_active: admin.is_active !== undefined ? admin.is_active : true
      });
      setErrors({});
      setIsEditing(false);
    } else {
      // Режим просмотра - закрываем окно
      handleClose();
    }
  };

  const handleClose = () => {
    setFormData({
      login: '',
      password: '',
      permissions: [],
      is_active: true
    });
    setErrors({});
    setIsEditing(false);
    onClose();
  };

  const handleDelete = async () => {
    setIsDeleting(true);
    try {
      await adminApi.delete(admin.id);
      toast({
        title: 'Администратор удален',
        description: `Администратор ${admin.login} успешно удален`,
        status: 'success',
        duration: 3000,
        isClosable: true,
      });

      // Обновляем данные в родительском компоненте
      if (onUpdate) {
        await onUpdate();
      }

      // Закрываем все модалки
      closeDeleteDialog();
      handleClose();

    } catch (error) {
      console.error('Ошибка при удалении администратора:', error);
      toast({
        title: 'Ошибка',
        description: error.message || 'Не удалось удалить администратора',
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    } finally {
      setIsDeleting(false);
    }
  };

  const canEdit = () => {
    if (isCreateMode) return true; // Новый админ
    if (admin.role === 'super_admin') return false; // Нельзя редактировать супер админа
    return true;
  };

  const canDelete = () => {
    if (isCreateMode) return false;
    if (admin.role === 'super_admin') return false; // Нельзя удалить супер админа
    if (admin.id === currentAdmin?.id) return false; // Нельзя удалить себя
    return true;
  };

  // Простая группировка разрешений (если нет категорий в API)
  const getPermissionLabel = (permission) => {
    const labels = {
      // Пользователи
      'view_users': 'Просмотр пользователей',
      'edit_users': 'Редактирование пользователей',
      'delete_users': 'Удаление пользователей',
      'ban_users': 'Бан пользователей',
      // Бронирования
      'view_bookings': 'Просмотр бронирований',
      'create_bookings': 'Создание бронирований',
      'edit_bookings': 'Редактирование бронирований',
      'delete_bookings': 'Удаление бронирований',
      'confirm_bookings': 'Подтверждение бронирований',
      // Тарифы
      'view_tariffs': 'Просмотр тарифов',
      'create_tariffs': 'Создание тарифов',
      'edit_tariffs': 'Редактирование тарифов',
      'delete_tariffs': 'Удаление тарифов',
      // Промокоды
      'view_promocodes': 'Просмотр промокодов',
      'create_promocodes': 'Создание промокодов',
      'edit_promocodes': 'Редактирование промокодов',
      'delete_promocodes': 'Удаление промокодов',
      // Тикеты
      'view_tickets': 'Просмотр тикетов',
      'edit_tickets': 'Редактирование тикетов',
      'delete_tickets': 'Удаление тикетов',
      // Уведомления
      'view_notifications': 'Просмотр уведомлений',
      'manage_notifications': 'Управление уведомлениями',
      // Telegram рассылки
      'view_telegram_newsletters': 'Просмотр Telegram рассылок',
      'send_telegram_newsletters': 'Отправка Telegram рассылок',
      'manage_telegram_newsletters': 'Управление Telegram рассылками',
      // Email рассылки
      'view_email_campaigns': 'Просмотр Email рассылок',
      'create_email_campaigns': 'Создание Email рассылок',
      'edit_email_campaigns': 'Редактирование Email рассылок',
      'delete_email_campaigns': 'Удаление Email рассылок',
      'send_email_campaigns': 'Отправка Email рассылок',
      'manage_email_templates': 'Управление Email шаблонами',
      // Администраторы
      'manage_admins': 'Управление администраторами',
      // Дашборд
      'view_dashboard': 'Просмотр дашборда',
      // Логирование
      'view_logs': 'Просмотр логов',
      'manage_logging': 'Управление логированием',
      // Бэкапы
      'manage_backups': 'Управление бэкапами',
      // Подписки на офисы
      'view_office_subscriptions': 'Просмотр подписок на офисы',
      'manage_office_subscriptions': 'Управление подписками на офисы',
      // Системные
      'view_analytics': 'Просмотр аналитики',
      'export_data': 'Экспорт данных',
      'manage_system': 'Управление системой'
    };
    return labels[permission] || permission;
  };

  // Группировка разрешений по категориям
  const groupedPermissions = React.useMemo(() => {
    const permissions = availablePermissions.permissions || [];

    // Если у разрешений есть категории
    if (permissions.length > 0 && permissions[0].category) {
      return permissions.reduce((acc, perm) => {
        if (!acc[perm.category]) {
          acc[perm.category] = [];
        }
        acc[perm.category].push(perm);
        return acc;
      }, {});
    }

    // Если категорий нет, создаем расширенную группировку
    const simplePermissions = permissions.map(p => typeof p === 'string' ? p : p.value || p);

    const categorized = {
      'Пользователи': simplePermissions.filter(p => p.includes('users') && !p.includes('office_subscriptions')),
      'Бронирования': simplePermissions.filter(p => p.includes('bookings')),
      'Тарифы': simplePermissions.filter(p => p.includes('tariffs')),
      'Промокоды': simplePermissions.filter(p => p.includes('promocodes')),
      'Тикеты': simplePermissions.filter(p => p.includes('tickets')),
      'Подписки на офисы': simplePermissions.filter(p => p.includes('office_subscriptions')),
      'Telegram рассылки': simplePermissions.filter(p => p.includes('telegram_newsletters')),
      'Email рассылки': simplePermissions.filter(p => p.includes('email_campaigns') || p.includes('email_templates')),
      'Уведомления': simplePermissions.filter(p => p.includes('notifications')),
      'Администраторы': simplePermissions.filter(p => p.includes('admins')),
      'Дашборд': simplePermissions.filter(p => p.includes('dashboard')),
      'Логирование': simplePermissions.filter(p => p.includes('logs') || p.includes('logging')),
      'Бэкапы': simplePermissions.filter(p => p.includes('backups')),
    };

    // Находим разрешения, которые не попали ни в одну категорию
    const categorizedPermissions = new Set(
      Object.values(categorized).flat()
    );
    const uncategorized = simplePermissions.filter(p => !categorizedPermissions.has(p));

    if (uncategorized.length > 0) {
      categorized['Система'] = uncategorized;
    }

    // Удаляем пустые категории
    return Object.fromEntries(
      Object.entries(categorized).filter(([_, perms]) => perms.length > 0)
    );
  }, [availablePermissions]);

  return (
    <>
      <Modal isOpen={isOpen} onClose={handleClose} size="xl">
        <ModalOverlay />
        <ModalContent maxW="900px" bg={bgColor}>
          <ModalHeader>
            {isCreateMode ? 'Новый администратор' : `Администратор: ${admin.login}`}
          </ModalHeader>
          <ModalCloseButton />

          <ModalBody>
            <VStack spacing={6} align="stretch">
              {/* Информация об админе */}
              {admin && !isEditing && (
                <VStack spacing={4} align="stretch">
                  <HStack justify="space-between">
                    <Text fontSize="lg" fontWeight="bold">Информация</Text>
                    <Badge colorScheme={getRoleColor(admin.role)} fontSize="sm">
                      {getRoleLabel(admin.role)}
                    </Badge>
                  </HStack>

                  <SimpleGrid columns={2} spacing={4}>
                    <Box>
                      <Text fontSize="sm" color="gray.500">Логин</Text>
                      <Text fontWeight="medium">{admin.login}</Text>
                    </Box>
                    <Box>
                      <Text fontSize="sm" color="gray.500">Статус</Text>
                      <Badge colorScheme={getStatusColor(admin.is_active ? 'active' : 'inactive')}>
                        {admin.is_active ? 'Активен' : 'Неактивен'}
                      </Badge>
                    </Box>
                    <Box>
                      <Text fontSize="sm" color="gray.500">Создатель</Text>
                      <Text>{admin.creator_login || 'Система'}</Text>
                    </Box>
                    <Box>
                      <Text fontSize="sm" color="gray.500">Дата создания</Text>
                      <Text fontSize="sm">{formatDateTime(admin.created_at)}</Text>
                    </Box>
                  </SimpleGrid>

                  {/* Разрешения */}
                  {admin.role !== 'super_admin' && (
                    <>
                      <Divider />
                      <Box>
                        <Text fontSize="lg" fontWeight="bold" mb={3}>
                          Разрешения ({admin.permissions?.length || 0})
                        </Text>
                        {admin.permissions && admin.permissions.length > 0 ? (
                          <SimpleGrid columns={2} spacing={2}>
                            {admin.permissions.map(permission => (
                              <Text key={permission} fontSize="sm">
                                • {getPermissionLabel(permission)}
                              </Text>
                            ))}
                          </SimpleGrid>
                        ) : (
                          <Text color="gray.500">Нет разрешений</Text>
                        )}
                      </Box>
                    </>
                  )}

                  {admin.role === 'super_admin' && (
                    <Alert status="info">
                      <AlertIcon />
                      <AlertDescription>
                        Главный администратор имеет все права и не может быть изменен.
                      </AlertDescription>
                    </Alert>
                  )}
                </VStack>
              )}

              {/* Форма редактирования */}
              {(isEditing || isCreateMode) && (
                <VStack spacing={4} align="stretch">
                  <FormControl isInvalid={errors.login}>
                    <FormLabel>Логин</FormLabel>
                    <Input
                      value={formData.login}
                      onChange={(e) => setFormData({...formData, login: e.target.value})}
                      placeholder="Введите логин"
                    />
                    <FormErrorMessage>{errors.login}</FormErrorMessage>
                  </FormControl>

                  <FormControl isInvalid={errors.password}>
                    <FormLabel>
                      {isCreateMode ? 'Пароль' : 'Новый пароль (оставьте пустым, если не хотите менять)'}
                    </FormLabel>
                    <Input
                      type="password"
                      value={formData.password}
                      onChange={(e) => setFormData({...formData, password: e.target.value})}
                      placeholder="Введите пароль"
                    />
                    <FormErrorMessage>{errors.password}</FormErrorMessage>
                  </FormControl>

                  <FormControl>
                    <HStack justify="space-between">
                      <FormLabel mb={0}>Активен</FormLabel>
                      <Switch
                        isChecked={formData.is_active}
                        onChange={(e) => setFormData({...formData, is_active: e.target.checked})}
                      />
                    </HStack>
                  </FormControl>

                  {/* Разрешения */}
                  <FormControl>
                    <HStack justify="space-between" mb={3}>
                      <FormLabel mb={0}>Разрешения</FormLabel>
                      <HStack spacing={2}>
                        <Button
                          size="sm"
                          variant="outline"
                          colorScheme="blue"
                          onClick={handleSelectAllPermissions}
                          isDisabled={!availablePermissions.permissions || availablePermissions.permissions.length === 0}
                        >
                          Выбрать все
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          colorScheme="gray"
                          onClick={handleDeselectAllPermissions}
                          isDisabled={formData.permissions.length === 0}
                        >
                          Снять все
                        </Button>
                      </HStack>
                    </HStack>
                    {Object.keys(groupedPermissions).length > 0 ? (
                      <Accordion allowMultiple>
                        {Object.entries(groupedPermissions).map(([category, permissions]) => (
                          <AccordionItem key={category}>
                            <AccordionButton>
                              <Box flex="1" textAlign="left" fontWeight="medium">
                                {category}
                              </Box>
                              <AccordionIcon />
                            </AccordionButton>
                            <AccordionPanel pb={4}>
                              <CheckboxGroup
                                value={formData.permissions}
                                onChange={(values) => setFormData({...formData, permissions: values})}
                              >
                                <VStack align="start" spacing={2}>
                                  {permissions.map(permission => {
                                    const permValue = typeof permission === 'string' ? permission : permission.value;
                                    const permLabel = typeof permission === 'string' ? getPermissionLabel(permission) : permission.label;
                                    return (
                                      <Checkbox key={permValue} value={permValue}>
                                        {permLabel}
                                      </Checkbox>
                                    );
                                  })}
                                </VStack>
                              </CheckboxGroup>
                            </AccordionPanel>
                          </AccordionItem>
                        ))}
                      </Accordion>
                    ) : (
                      <Text color="gray.500">Загрузка разрешений...</Text>
                    )}
                  </FormControl>
                </VStack>
              )}
            </VStack>
          </ModalBody>

          <ModalFooter>
            <HStack spacing={3}>
              {admin && canDelete() && !isEditing && (
                <Button
                  colorScheme="red"
                  variant="outline"
                  onClick={openDeleteDialog}
                >
                  Удалить
                </Button>
              )}

              <Button variant="ghost" onClick={handleCancel}>
                {isEditing || isCreateMode ? 'Отмена' : 'Закрыть'}
              </Button>

              {canEdit() && (
                <>
                  {isEditing || isCreateMode ? (
                    <Button
                      colorScheme="purple"
                      onClick={handleSave}
                      isLoading={isLoading}
                      loadingText={isCreateMode ? "Создание..." : "Сохранение..."}
                    >
                      {isCreateMode ? 'Создать' : 'Сохранить'}
                    </Button>
                  ) : (
                    <Button
                      colorScheme="purple"
                      onClick={() => setIsEditing(true)}
                    >
                      Редактировать
                    </Button>
                  )}
                </>
              )}
            </HStack>
          </ModalFooter>
        </ModalContent>
      </Modal>

      {/* Диалог подтверждения удаления */}
      <AlertDialog
        isOpen={deleteDialogOpen}
        leastDestructiveRef={cancelRef}
        onClose={closeDeleteDialog}
      >
        <AlertDialogOverlay>
          <AlertDialogContent>
            <AlertDialogHeader fontSize="lg" fontWeight="bold">
              Удалить администратора
            </AlertDialogHeader>

            <AlertDialogBody>
              Вы уверены, что хотите удалить администратора <strong>{admin?.login}</strong>?
              <br />
              Это действие нельзя отменить.
            </AlertDialogBody>

            <AlertDialogFooter>
              <Button ref={cancelRef} onClick={closeDeleteDialog}>
                Отмена
              </Button>
              <Button
                colorScheme="red"
                onClick={handleDelete}
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
    </>
  );
};

export default AdminDetailModal;