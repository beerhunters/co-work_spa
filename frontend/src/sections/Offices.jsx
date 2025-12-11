import React, { useState, useEffect, useMemo } from 'react';
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
  Badge,
  Button,
  useDisclosure,
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalBody,
  ModalCloseButton,
  ModalFooter,
  FormControl,
  FormLabel,
  Input,
  NumberInput,
  NumberInputField,
  NumberInputStepper,
  NumberIncrementStepper,
  NumberDecrementStepper,
  Textarea,
  Switch,
  Select,
  FormHelperText,
  useToast,
  Checkbox,
  Stack,
  Tag,
  TagLabel,
  TagCloseButton,
  Divider,
  InputGroup,
  InputLeftElement,
  ButtonGroup,
  IconButton,
  SimpleGrid,
} from '@chakra-ui/react';
import { FiEye, FiPlus, FiUsers, FiBell, FiSearch } from 'react-icons/fi';
import { BsList, BsGrid3X3Gap } from 'react-icons/bs';
import { sizes, styles, getStatusColor, colors } from '../styles/styles';
import { officeApi } from '../utils/api';
import { ListSkeleton } from '../components/LoadingSkeletons';

const CreateOfficeModal = ({ isOpen, onClose, onUpdate, users = [] }) => {
  const [formData, setFormData] = useState({
    office_number: '',
    floor: 0,
    capacity: 1,
    price_per_month: 0,
    duration_months: null,
    rental_start_date: null,
    rental_end_date: null,
    payment_day: null,
    admin_reminder_enabled: false,
    admin_reminder_days: 5,
    admin_reminder_type: 'days_before',
    admin_reminder_datetime: null,
    tenant_reminder_enabled: false,
    tenant_reminder_days: 5,
    tenant_reminder_type: 'days_before',
    tenant_reminder_datetime: null,
    tenant_ids: [],
    tenant_reminder_settings: [],
    comment: '',
    is_active: true
  });
  const [isLoading, setIsLoading] = useState(false);
  const [errors, setErrors] = useState({});
  const [selectedTenants, setSelectedTenants] = useState([]);
  const [selectedReminderTenants, setSelectedReminderTenants] = useState([]);
  const [userSearchQuery, setUserSearchQuery] = useState('');
  const [isUserDropdownOpen, setIsUserDropdownOpen] = useState(false);
  const toast = useToast();

  const resetForm = () => {
    setFormData({
      office_number: '',
      floor: 0,
      capacity: 1,
      price_per_month: 0,
      duration_months: null,
      rental_start_date: null,
      rental_end_date: null,
      payment_day: null,
      admin_reminder_enabled: false,
      admin_reminder_days: 5,
      admin_reminder_type: 'days_before',
      admin_reminder_datetime: null,
      tenant_reminder_enabled: false,
      tenant_reminder_days: 5,
      tenant_reminder_type: 'days_before',
      tenant_reminder_datetime: null,
      tenant_ids: [],
      tenant_reminder_settings: [],
      comment: '',
      is_active: true
    });
    setSelectedTenants([]);
    setSelectedReminderTenants([]);
    setUserSearchQuery('');
    setIsUserDropdownOpen(false);
    setErrors({});
  };

  const validateForm = () => {
    const newErrors = {};

    if (!formData.office_number.trim()) {
      newErrors.office_number = 'Номер офиса обязателен';
    }

    if (formData.floor < 0) {
      newErrors.floor = 'Этаж не может быть отрицательным';
    }

    if (formData.capacity < 1) {
      newErrors.capacity = 'Вместимость должна быть минимум 1';
    }

    if (formData.price_per_month <= 0) {
      newErrors.price_per_month = 'Стоимость должна быть больше 0';
    }

    if (formData.payment_day && (formData.payment_day < 1 || formData.payment_day > 31)) {
      newErrors.payment_day = 'День платежа должен быть от 1 до 31';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleAddTenant = (e) => {
    const userId = parseInt(e.target.value);
    if (userId && !selectedTenants.find(t => t.id === userId)) {
      const user = users.find(u => u.id === userId);
      if (user) {
        setSelectedTenants([...selectedTenants, user]);
        setFormData({
          ...formData,
          tenant_ids: [...formData.tenant_ids, userId]
        });
      }
    }
    e.target.value = '';
  };

  const handleRemoveTenant = (userId) => {
    setSelectedTenants(selectedTenants.filter(t => t.id !== userId));
    setFormData({
      ...formData,
      tenant_ids: formData.tenant_ids.filter(id => id !== userId)
    });
    // Также удаляем из напоминаний
    setSelectedReminderTenants(selectedReminderTenants.filter(id => id !== userId));
    setFormData({
      ...formData,
      tenant_reminder_settings: formData.tenant_reminder_settings.filter(s => s.user_id !== userId)
    });
  };

  const handleToggleReminderTenant = (userId) => {
    const isSelected = selectedReminderTenants.includes(userId);

    if (isSelected) {
      setSelectedReminderTenants(selectedReminderTenants.filter(id => id !== userId));
      setFormData({
        ...formData,
        tenant_reminder_settings: formData.tenant_reminder_settings.filter(s => s.user_id !== userId)
      });
    } else {
      setSelectedReminderTenants([...selectedReminderTenants, userId]);
      setFormData({
        ...formData,
        tenant_reminder_settings: [
          ...formData.tenant_reminder_settings,
          { user_id: userId, is_enabled: true }
        ]
      });
    }
  };

  // Фильтрация пользователей для поиска
  const filteredUsers = useMemo(() => {
    if (!users || users.length === 0) return [];
    if (!userSearchQuery.trim()) return users;

    const query = userSearchQuery.toLowerCase().trim();

    return users.filter(user => {
      const fullName = (user.full_name || '').toLowerCase();
      const username = (user.username || '').toLowerCase();
      const phone = (user.phone || '').toLowerCase();
      const email = (user.email || '').toLowerCase();

      return (
        fullName.includes(query) ||
        username.includes(query) ||
        phone.includes(query) ||
        email.includes(query)
      );
    });
  }, [users, userSearchQuery]);

  const handleUserSearchChange = (e) => {
    const value = e.target.value;
    setUserSearchQuery(value);
    setIsUserDropdownOpen(true);
  };

  const handleSelectUser = (user) => {
    // Проверка, не добавлен ли уже
    if (selectedTenants.find(t => t.id === user.id)) {
      return;
    }

    // Добавляем к постояльцам
    handleAddTenant({ target: { value: user.id } });

    // Очищаем поиск
    setUserSearchQuery('');
    setIsUserDropdownOpen(false);
  };

  // Закрытие dropdown при клике вне его
  useEffect(() => {
    const handleClickOutside = (event) => {
      const dropdown = event.target.closest('[data-user-dropdown]');
      if (!dropdown && isUserDropdownOpen) {
        setIsUserDropdownOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [isUserDropdownOpen]);

  const handleSubmit = async () => {
    if (!validateForm()) return;

    setIsLoading(true);
    try {
      // Очищаем datetime поля, если выбран тип "days_before"
      const cleanedData = { ...formData };
      if (cleanedData.admin_reminder_type === 'days_before') {
        cleanedData.admin_reminder_datetime = null;
      } else if (cleanedData.admin_reminder_datetime) {
        // Преобразуем datetime-local формат в ISO формат
        cleanedData.admin_reminder_datetime = new Date(cleanedData.admin_reminder_datetime).toISOString();
      }

      if (cleanedData.tenant_reminder_type === 'days_before') {
        cleanedData.tenant_reminder_datetime = null;
      } else if (cleanedData.tenant_reminder_datetime) {
        // Преобразуем datetime-local формат в ISO формат
        cleanedData.tenant_reminder_datetime = new Date(cleanedData.tenant_reminder_datetime).toISOString();
      }

      // Преобразуем пустые строки в null для datetime полей
      if (cleanedData.admin_reminder_datetime === '') {
        cleanedData.admin_reminder_datetime = null;
      }
      if (cleanedData.tenant_reminder_datetime === '') {
        cleanedData.tenant_reminder_datetime = null;
      }

      await officeApi.create(cleanedData);

      toast({
        title: 'Успешно',
        description: 'Офис создан',
        status: 'success',
        duration: 3000,
      });

      await onUpdate();
      resetForm();
      onClose();
    } catch (error) {
      toast({
        title: 'Ошибка',
        description: error.response?.data?.detail || 'Не удалось создать офис',
        status: 'error',
        duration: 5000,
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleClose = () => {
    resetForm();
    onClose();
  };

  return (
    <Modal isOpen={isOpen} onClose={handleClose} size="xl" scrollBehavior="inside">
      <ModalOverlay />
      <ModalContent>
        <ModalHeader>Создание офиса</ModalHeader>
        <ModalCloseButton />

        <ModalBody>
          <VStack align="stretch" spacing={4}>
            {/* Номер офиса */}
            <FormControl isInvalid={errors.office_number} isRequired>
              <FormLabel>Номер офиса</FormLabel>
              <Input
                value={formData.office_number}
                onChange={(e) => setFormData({...formData, office_number: e.target.value})}
                placeholder="Например: 101, A-205"
                maxLength={20}
              />
              <FormHelperText color={errors.office_number ? 'red.500' : 'gray.600'}>
                {errors.office_number || 'Уникальный номер офиса'}
              </FormHelperText>
            </FormControl>

            {/* Этаж и вместимость */}
            <HStack spacing={4}>
              <FormControl isInvalid={errors.floor} isRequired>
                <FormLabel>Этаж</FormLabel>
                <NumberInput
                  value={formData.floor}
                  onChange={(val) => setFormData({...formData, floor: parseInt(val) || 0})}
                  min={0}
                >
                  <NumberInputField />
                  <NumberInputStepper>
                    <NumberIncrementStepper />
                    <NumberDecrementStepper />
                  </NumberInputStepper>
                </NumberInput>
                <FormHelperText color={errors.floor ? 'red.500' : 'gray.600'}>
                  {errors.floor || 'На каком этаже'}
                </FormHelperText>
              </FormControl>

              <FormControl isInvalid={errors.capacity} isRequired>
                <FormLabel>Вместимость</FormLabel>
                <NumberInput
                  value={formData.capacity}
                  onChange={(val) => setFormData({...formData, capacity: parseInt(val) || 1})}
                  min={1}
                >
                  <NumberInputField />
                  <NumberInputStepper>
                    <NumberIncrementStepper />
                    <NumberDecrementStepper />
                  </NumberInputStepper>
                </NumberInput>
                <FormHelperText color={errors.capacity ? 'red.500' : 'gray.600'}>
                  {errors.capacity || 'Макс. кол-во человек'}
                </FormHelperText>
              </FormControl>
            </HStack>

            {/* Стоимость */}
            <FormControl isInvalid={errors.price_per_month} isRequired>
              <FormLabel>Стоимость в месяц (₽)</FormLabel>
              <NumberInput
                value={formData.price_per_month}
                onChange={(val) => setFormData({...formData, price_per_month: parseFloat(val) || 0})}
                min={0}
              >
                <NumberInputField />
                <NumberInputStepper>
                  <NumberIncrementStepper />
                  <NumberDecrementStepper />
                </NumberInputStepper>
              </NumberInput>
              <FormHelperText color={errors.price_per_month ? 'red.500' : 'gray.600'}>
                {errors.price_per_month || 'Цена аренды'}
              </FormHelperText>
            </FormControl>

            {/* Длительность аренды */}
            <FormControl>
              <FormLabel>Длительность аренды (месяцев)</FormLabel>
              <NumberInput
                value={formData.duration_months || ''}
                onChange={(val) => setFormData({...formData, duration_months: val ? parseInt(val) : null})}
                min={1}
                max={120}
              >
                <NumberInputField placeholder="Например: 6, 12, 24" />
                <NumberInputStepper>
                  <NumberIncrementStepper />
                  <NumberDecrementStepper />
                </NumberInputStepper>
              </NumberInput>
              <FormHelperText>Скидки: от 6 месяцев -10%, от 12 месяцев -15%</FormHelperText>
            </FormControl>

            {/* Дата начала аренды */}
            {formData.duration_months && (
              <FormControl>
                <FormLabel>Дата начала аренды</FormLabel>
                <Input
                  type="date"
                  value={formData.rental_start_date ? new Date(formData.rental_start_date).toISOString().split('T')[0] : ''}
                  onChange={(e) => setFormData({...formData, rental_start_date: e.target.value ? new Date(e.target.value).toISOString() : null})}
                />
              </FormControl>
            )}

            {/* Расчет стоимости с учетом скидок */}
            {formData.duration_months && formData.price_per_month && (
              <Box p={4} bg="blue.50" borderRadius="md">
                <VStack align="start" spacing={2}>
                  <HStack justify="space-between" width="100%">
                    <Text fontWeight="medium">Базовая стоимость:</Text>
                    <Text>{formData.price_per_month.toLocaleString()} ₽/мес</Text>
                  </HStack>

                  {formData.duration_months >= 6 && (
                    <>
                      <HStack justify="space-between" width="100%">
                        <Text fontWeight="medium" color="green.600">
                          Скидка {formData.duration_months >= 12 ? '15%' : '10%'}:
                        </Text>
                        <Text color="green.600">
                          -{(formData.price_per_month * (formData.duration_months >= 12 ? 0.15 : 0.10)).toLocaleString()} ₽/мес
                        </Text>
                      </HStack>

                      <Divider />
                    </>
                  )}

                  <HStack justify="space-between" width="100%">
                    <Text fontWeight="bold" fontSize="lg">Итоговая стоимость:</Text>
                    <Text fontWeight="bold" fontSize="lg" color="blue.600">
                      {(formData.price_per_month * (1 - (formData.duration_months >= 12 ? 0.15 : formData.duration_months >= 6 ? 0.10 : 0))).toLocaleString()} ₽/мес
                    </Text>
                  </HStack>

                  <Text fontSize="sm" color="gray.600">
                    За {formData.duration_months} {formData.duration_months === 1 ? 'месяц' : formData.duration_months < 5 ? 'месяца' : 'месяцев'}: {' '}
                    {(formData.price_per_month * (1 - (formData.duration_months >= 12 ? 0.15 : formData.duration_months >= 6 ? 0.10 : 0)) * formData.duration_months).toLocaleString()} ₽
                  </Text>
                </VStack>
              </Box>
            )}

            {/* День платежа - показывать только если есть постояльцы */}
            {selectedTenants.length > 0 && (
              <FormControl isInvalid={errors.payment_day}>
                <FormLabel>День платежа</FormLabel>
                <NumberInput
                  value={formData.payment_day || ''}
                  onChange={(val) => setFormData({...formData, payment_day: val ? parseInt(val) : null})}
                  min={1}
                  max={31}
                >
                  <NumberInputField placeholder="1-31" />
                  <NumberInputStepper>
                    <NumberIncrementStepper />
                    <NumberDecrementStepper />
                  </NumberInputStepper>
                </NumberInput>
                <FormHelperText color={errors.payment_day ? 'red.500' : 'gray.600'}>
                  {errors.payment_day || 'Число месяца для ежемесячного платежа'}
                </FormHelperText>
              </FormControl>
            )}

            <Divider />

            {/* Постояльцы */}
            <FormControl>
              <FormLabel>Постояльцы офиса</FormLabel>

              <Box position="relative" data-user-dropdown>
                <InputGroup>
                  <InputLeftElement pointerEvents="none">
                    <Icon as={FiSearch} color="gray.400" />
                  </InputLeftElement>
                  <Input
                    placeholder="Начните вводить ФИО, телефон или email"
                    value={userSearchQuery}
                    onChange={handleUserSearchChange}
                    onFocus={() => {
                      if (userSearchQuery.trim().length > 0 || filteredUsers.length > 0) {
                        setIsUserDropdownOpen(true);
                      }
                    }}
                  />
                </InputGroup>

                {/* Выпадающий список отфильтрованных пользователей */}
                {isUserDropdownOpen && filteredUsers.length > 0 && (
                  <Box
                    position="absolute"
                    top="100%"
                    left={0}
                    right={0}
                    mt={1}
                    maxH="300px"
                    overflowY="auto"
                    bg="white"
                    borderWidth="1px"
                    borderColor="gray.200"
                    borderRadius="md"
                    boxShadow="lg"
                    zIndex={1000}
                  >
                    {filteredUsers
                      .filter(u => !selectedTenants.find(t => t.id === u.id))
                      .slice(0, 50)
                      .map(user => (
                        <Box
                          key={user.id}
                          px={4}
                          py={3}
                          cursor="pointer"
                          _hover={{ bg: 'blue.50' }}
                          onClick={() => handleSelectUser(user)}
                          borderBottomWidth="1px"
                          borderBottomColor="gray.100"
                        >
                          <Text fontWeight="medium">
                            {user.full_name || user.username}
                          </Text>
                          {user.phone && (
                            <Text fontSize="sm" color="gray.600">
                              {user.phone}
                            </Text>
                          )}
                          {user.email && !user.phone && (
                            <Text fontSize="sm" color="gray.600">
                              {user.email}
                            </Text>
                          )}
                        </Box>
                      ))}

                    {filteredUsers.filter(u => !selectedTenants.find(t => t.id === u.id)).length > 50 && (
                      <Box px={4} py={2} bg="gray.50" fontSize="sm" color="gray.600">
                        Показано 50 из {filteredUsers.filter(u => !selectedTenants.find(t => t.id === u.id)).length}. Уточните запрос для поиска.
                      </Box>
                    )}
                  </Box>
                )}

                {/* Сообщение если ничего не найдено */}
                {isUserDropdownOpen && userSearchQuery.trim() && filteredUsers.length === 0 && (
                  <Box
                    position="absolute"
                    top="100%"
                    left={0}
                    right={0}
                    mt={1}
                    p={4}
                    bg="white"
                    borderWidth="1px"
                    borderColor="gray.200"
                    borderRadius="md"
                    boxShadow="lg"
                    zIndex={1000}
                  >
                    <Text fontSize="sm" color="gray.500">
                      Пользователь не найден. Попробуйте другой запрос.
                    </Text>
                  </Box>
                )}
              </Box>

              <FormHelperText>Введите имя, фамилию, телефон или email для поиска</FormHelperText>

              {/* Отображение выбранных постояльцев */}
              {selectedTenants.length > 0 && (
                <Stack direction="row" spacing={2} mt={2} flexWrap="wrap">
                  {selectedTenants.map(tenant => (
                    <Tag key={tenant.id} size="md" colorScheme="blue" borderRadius="full">
                      <TagLabel>{tenant.full_name}</TagLabel>
                      <TagCloseButton onClick={() => handleRemoveTenant(tenant.id)} />
                    </Tag>
                  ))}
                </Stack>
              )}
            </FormControl>

            <Divider />

            {/* Напоминание администратору */}
            <FormControl>
              <HStack justify="space-between">
                <FormLabel mb={0}>Напоминание администратору</FormLabel>
                <Switch
                  isChecked={formData.admin_reminder_enabled}
                  onChange={(e) => setFormData({...formData, admin_reminder_enabled: e.target.checked})}
                />
              </HStack>
              {formData.admin_reminder_enabled && (
                <NumberInput
                  value={formData.admin_reminder_days}
                  onChange={(val) => setFormData({...formData, admin_reminder_days: parseInt(val) || 5})}
                  min={1}
                  max={30}
                  mt={2}
                >
                  <NumberInputField />
                  <NumberInputStepper>
                    <NumberIncrementStepper />
                    <NumberDecrementStepper />
                  </NumberInputStepper>
                </NumberInput>
              )}
              <FormHelperText>
                {formData.admin_reminder_enabled
                  ? `Напоминание отправится за ${formData.admin_reminder_days} дней до даты платежа`
                  : 'Включите для получения напоминаний о выставлении счета'}
              </FormHelperText>
            </FormControl>

            {/* Напоминание постояльцам */}
            <FormControl>
              <HStack justify="space-between">
                <FormLabel mb={0}>Напоминание постояльцам</FormLabel>
                <Switch
                  isChecked={formData.tenant_reminder_enabled}
                  onChange={(e) => setFormData({...formData, tenant_reminder_enabled: e.target.checked})}
                />
              </HStack>
              {formData.tenant_reminder_enabled && (
                <>
                  <NumberInput
                    value={formData.tenant_reminder_days}
                    onChange={(val) => setFormData({...formData, tenant_reminder_days: parseInt(val) || 5})}
                    min={1}
                    max={30}
                    mt={2}
                  >
                    <NumberInputField />
                    <NumberInputStepper>
                      <NumberIncrementStepper />
                      <NumberDecrementStepper />
                    </NumberInputStepper>
                  </NumberInput>

                  {selectedTenants.length > 0 && (
                    <Box mt={3}>
                      <Text fontSize="sm" fontWeight="medium" mb={2}>Кому отправлять напоминания:</Text>
                      <Stack spacing={2}>
                        {selectedTenants.map(tenant => (
                          <Checkbox
                            key={tenant.id}
                            isChecked={selectedReminderTenants.includes(tenant.id)}
                            onChange={() => handleToggleReminderTenant(tenant.id)}
                          >
                            {tenant.full_name}
                          </Checkbox>
                        ))}
                      </Stack>
                    </Box>
                  )}
                </>
              )}
              <FormHelperText>
                {formData.tenant_reminder_enabled
                  ? `Напоминание отправится за ${formData.tenant_reminder_days} дней до даты платежа`
                  : 'Включите для отправки напоминаний об оплате постояльцам'}
              </FormHelperText>
            </FormControl>

            <Divider />

            {/* Комментарий */}
            <FormControl>
              <FormLabel>Комментарий</FormLabel>
              <Textarea
                value={formData.comment}
                onChange={(e) => setFormData({...formData, comment: e.target.value})}
                placeholder="Дополнительная информация об офисе"
                rows={3}
              />
              <FormHelperText>Необязательное поле</FormHelperText>
            </FormControl>

            {/* Активность */}
            <FormControl>
              <HStack justify="space-between">
                <FormLabel mb={0}>Активен</FormLabel>
                <Switch
                  isChecked={formData.is_active}
                  onChange={(e) => setFormData({...formData, is_active: e.target.checked})}
                />
              </HStack>
              <FormHelperText>Неактивные офисы не отображаются в общем списке</FormHelperText>
            </FormControl>
          </VStack>
        </ModalBody>

        <ModalFooter>
          <Button variant="outline" mr={3} onClick={handleClose}>
            Отмена
          </Button>
          <Button
            colorScheme="blue"
            onClick={handleSubmit}
            isLoading={isLoading}
            leftIcon={<FiPlus />}
          >
            Создать офис
          </Button>
        </ModalFooter>
      </ModalContent>
    </Modal>
  );
};

const Offices = ({ offices = [], users = [], openDetailModal, onUpdate, isLoading = false }) => {
  const { isOpen, onOpen, onClose } = useDisclosure();

  // Состояние для переключения между списком и сеткой
  const [viewMode, setViewMode] = useState(() => {
    return localStorage.getItem('officesViewMode') || 'list';
  });

  const handleViewModeChange = (mode) => {
    setViewMode(mode);
    localStorage.setItem('officesViewMode', mode);
  };

  const EmptyState = () => (
    <Box textAlign="center" py={10}>
      <Text color="gray.500" fontSize="lg">
        Офисов пока нет
      </Text>
      <Text color="gray.400" fontSize="sm" mt={2}>
        Создайте первый офис, нажав кнопку "Добавить офис"
      </Text>
    </Box>
  );

  return (
    <>
      <Box p={sizes.content.padding} bg="gray.50" minH={sizes.content.minHeight}>
        <Card bg={colors.background.card}>
          <CardHeader>
            <HStack justify="space-between">
              <Heading size="md">Офисы</Heading>
              <HStack spacing={3}>
                <ButtonGroup size="sm" isAttached variant="outline">
                  <IconButton
                    icon={<BsList />}
                    aria-label="Список"
                    onClick={() => handleViewModeChange('list')}
                    colorScheme={viewMode === 'list' ? 'blue' : 'gray'}
                    isActive={viewMode === 'list'}
                  />
                  <IconButton
                    icon={<BsGrid3X3Gap />}
                    aria-label="Сетка"
                    onClick={() => handleViewModeChange('grid')}
                    colorScheme={viewMode === 'grid' ? 'blue' : 'gray'}
                    isActive={viewMode === 'grid'}
                  />
                </ButtonGroup>
                <Button
                  leftIcon={<FiPlus />}
                  colorScheme="blue"
                  onClick={onOpen}
                  size="sm"
                >
                  Добавить офис
                </Button>
              </HStack>
            </HStack>
          </CardHeader>

          <CardBody>
            {isLoading ? (
              <ListSkeleton items={5} />
            ) : offices.length === 0 ? (
              <EmptyState />
            ) : viewMode === 'list' ? (
              <VStack align="stretch" spacing={2}>
                {offices.map(office => (
                  <Box
                    key={office.id}
                    p={styles.listItem.padding}
                    borderRadius={styles.listItem.borderRadius}
                    bg={styles.listItem.bg}
                    border={styles.listItem.border}
                    cursor="pointer"
                    onClick={() => openDetailModal(office, 'office')}
                    transition={styles.listItem.transition}
                    _hover={{
                      bg: styles.listItem.hoverBg,
                      transform: 'translateY(-2px)',
                      boxShadow: 'sm',
                    }}
                  >
                    <HStack justify="space-between">
                      <VStack align="start" spacing={1} flex={1}>
                        <HStack spacing={3}>
                          <Text fontWeight="bold" fontSize="lg">
                            Офис {office.office_number}
                          </Text>
                          <Badge colorScheme={office.is_active ? 'green' : 'gray'}>
                            {office.is_active ? 'Активен' : 'Неактивен'}
                          </Badge>
                          {office.tenants && office.tenants.length > 0 && (
                            <Badge colorScheme="blue">
                              <HStack spacing={1}>
                                <Icon as={FiUsers} boxSize={3} />
                                <Text>{office.tenants.length}/{office.capacity}</Text>
                              </HStack>
                            </Badge>
                          )}
                          {(office.admin_reminder_enabled || office.tenant_reminder_enabled) && (
                            <Badge colorScheme="orange">
                              <Icon as={FiBell} boxSize={3} />
                            </Badge>
                          )}
                        </HStack>
                        <HStack spacing={4} fontSize="sm" color="gray.600">
                          <Text>Этаж: {office.floor}</Text>
                          <Text>•</Text>
                          <Text>Вместимость: {office.capacity}</Text>
                          <Text>•</Text>
                          <Text fontWeight="medium">{office.price_per_month} ₽/мес</Text>
                          {office.payment_day && (
                            <>
                              <Text>•</Text>
                              <Text>Платеж: {office.payment_day} число</Text>
                            </>
                          )}
                          {office.duration_months && (
                            <>
                              <Text>•</Text>
                              <Text>
                                Аренда: {office.duration_months} {office.duration_months === 1 ? 'мес' : office.duration_months < 5 ? 'мес' : 'мес'}
                                {office.duration_months >= 6 && (
                                  <Badge ml={2} colorScheme="green">
                                    -{office.duration_months >= 12 ? '15%' : '10%'}
                                  </Badge>
                                )}
                              </Text>
                            </>
                          )}
                        </HStack>
                        {office.tenants && office.tenants.length > 0 && (
                          <HStack spacing={2} mt={1}>
                            {office.tenants.slice(0, 3).map(tenant => (
                              <Tag key={tenant.id} size="sm" colorScheme="blue">
                                {tenant.full_name}
                              </Tag>
                            ))}
                            {office.tenants.length > 3 && (
                              <Tag size="sm" colorScheme="gray">
                                +{office.tenants.length - 3}
                              </Tag>
                            )}
                          </HStack>
                        )}
                      </VStack>
                      <Icon as={FiEye} color="blue.500" boxSize={5} />
                    </HStack>
                  </Box>
                ))}
              </VStack>
            ) : (
              <SimpleGrid columns={{ base: 1, md: 2, lg: 3, xl: 4 }} spacing={4}>
                {offices.map(office => (
                  <Box
                    key={office.id}
                    p={4}
                    borderRadius="lg"
                    bg="white"
                    border="1px solid"
                    borderColor="gray.200"
                    cursor="pointer"
                    onClick={() => openDetailModal(office, 'office')}
                    transition="all 0.2s"
                    _hover={{
                      bg: 'gray.50',
                      transform: 'translateY(-2px)',
                      boxShadow: 'md',
                    }}
                  >
                    <VStack align="start" spacing={3}>
                      <HStack justify="space-between" width="100%">
                        <Text fontWeight="bold" fontSize="lg">
                          Офис {office.office_number}
                        </Text>
                        <Icon as={FiEye} color="blue.500" boxSize={4} />
                      </HStack>

                      <HStack spacing={2} flexWrap="wrap">
                        <Badge colorScheme={office.is_active ? 'green' : 'gray'}>
                          {office.is_active ? 'Активен' : 'Неактивен'}
                        </Badge>
                        {office.tenants && office.tenants.length > 0 && (
                          <Badge colorScheme="blue">
                            <HStack spacing={1}>
                              <Icon as={FiUsers} boxSize={3} />
                              <Text>{office.tenants.length}/{office.capacity}</Text>
                            </HStack>
                          </Badge>
                        )}
                        {(office.admin_reminder_enabled || office.tenant_reminder_enabled) && (
                          <Badge colorScheme="orange">
                            <Icon as={FiBell} boxSize={3} />
                          </Badge>
                        )}
                      </HStack>

                      <VStack align="start" spacing={1} fontSize="sm" color="gray.600" width="100%">
                        <Text>Этаж: {office.floor}</Text>
                        <Text>Вместимость: {office.capacity}</Text>
                        <Text fontWeight="medium" color="blue.600" fontSize="md">
                          {office.price_per_month} ₽/мес
                        </Text>
                        {office.payment_day && (
                          <Text>Платеж: {office.payment_day} число</Text>
                        )}
                        {office.duration_months && (
                          <HStack>
                            <Text>
                              Аренда: {office.duration_months} мес
                            </Text>
                            {office.duration_months >= 6 && (
                              <Badge colorScheme="green">
                                -{office.duration_months >= 12 ? '15%' : '10%'}
                              </Badge>
                            )}
                          </HStack>
                        )}
                      </VStack>

                      {office.tenants && office.tenants.length > 0 && (
                        <VStack align="start" spacing={1} width="100%">
                          {office.tenants.slice(0, 2).map(tenant => (
                            <Tag key={tenant.id} size="sm" colorScheme="blue" width="100%">
                              {tenant.full_name}
                            </Tag>
                          ))}
                          {office.tenants.length > 2 && (
                            <Tag size="sm" colorScheme="gray">
                              +{office.tenants.length - 2} еще
                            </Tag>
                          )}
                        </VStack>
                      )}
                    </VStack>
                  </Box>
                ))}
              </SimpleGrid>
            )}
          </CardBody>
        </Card>
      </Box>

      <CreateOfficeModal
        isOpen={isOpen}
        onClose={onClose}
        onUpdate={onUpdate}
        users={users}
      />
    </>
  );
};

export default Offices;
