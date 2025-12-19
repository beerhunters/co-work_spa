import React, { useState, useEffect, useMemo } from 'react';
import {
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalBody,
  ModalCloseButton,
  ModalFooter,
  Button,
  VStack,
  HStack,
  Text,
  Badge,
  useToast,
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
  AlertDialog,
  AlertDialogBody,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogContent,
  AlertDialogOverlay,
  useDisclosure,
  Tag,
  TagLabel,
  TagCloseButton,
  Stack,
  Checkbox,
  Box,
  Divider,
  Icon,
  InputGroup,
  InputLeftElement,
  Radio,
  RadioGroup,
} from '@chakra-ui/react';
import { FiEdit2, FiTrash2, FiX as FiClear, FiBell, FiUsers, FiSearch, FiArrowRight, FiCheck, FiAlertTriangle } from 'react-icons/fi';
import { officeApi } from '../../utils/api';

const OfficeDetailModal = ({ isOpen, onClose, office, users = [], offices = [], onUpdate }) => {
  const [isEditing, setIsEditing] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [formData, setFormData] = useState({});
  const [errors, setErrors] = useState({});
  const [selectedTenants, setSelectedTenants] = useState([]);
  const [selectedReminderTenants, setSelectedReminderTenants] = useState([]);
  const [userSearchQuery, setUserSearchQuery] = useState('');
  const [isUserDropdownOpen, setIsUserDropdownOpen] = useState(false);
  const [isPaymentLoading, setIsPaymentLoading] = useState(false);
  const toast = useToast();

  // Преобразует ISO datetime в формат datetime-local (YYYY-MM-DDTHH:mm)
  const formatDatetimeLocal = (isoString) => {
    if (!isoString) return '';
    const date = new Date(isoString);
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    const hours = String(date.getHours()).padStart(2, '0');
    const minutes = String(date.getMinutes()).padStart(2, '0');
    return `${year}-${month}-${day}T${hours}:${minutes}`;
  };

  const { isOpen: isDeleteOpen, onOpen: onDeleteOpen, onClose: onDeleteClose } = useDisclosure();
  const { isOpen: isClearOpen, onOpen: onClearOpen, onClose: onClearClose } = useDisclosure();
  const { isOpen: isRelocateOpen, onOpen: onRelocateOpen, onClose: onRelocateClose } = useDisclosure();
  const { isOpen: isPaymentConfirmOpen, onOpen: onPaymentConfirmOpen, onClose: onPaymentConfirmClose } = useDisclosure();
  const [selectedTargetOffice, setSelectedTargetOffice] = useState(null);
  const [paymentDateMismatch, setPaymentDateMismatch] = useState(false);
  const cancelRef = React.useRef();

  useEffect(() => {
    if (office && isOpen) {
      // Автоматически определяем тип оплаты по длительности аренды
      const durationMonths = office.duration_months || null;
      const paymentType = durationMonths === 1 ? 'monthly' : durationMonths > 1 ? 'one_time' : null;

      setFormData({
        office_number: office.office_number || '',
        floor: office.floor || 0,
        capacity: office.capacity || 1,
        price_per_month: office.price_per_month || 0,
        duration_months: durationMonths,
        rental_start_date: office.rental_start_date || null,
        rental_end_date: office.rental_end_date || null,
        payment_type: paymentType,
        admin_reminder_enabled: office.admin_reminder_enabled || false,
        admin_reminder_days: office.admin_reminder_days || 5,
        admin_reminder_type: office.admin_reminder_type || 'days_before',
        admin_reminder_datetime: formatDatetimeLocal(office.admin_reminder_datetime),
        tenant_reminder_enabled: office.tenant_reminder_enabled || false,
        tenant_reminder_days: office.tenant_reminder_days || 5,
        tenant_reminder_type: office.tenant_reminder_type || 'days_before',
        tenant_reminder_datetime: formatDatetimeLocal(office.tenant_reminder_datetime),
        tenant_ids: office.tenants ? office.tenants.map(t => t.id) : [],
        tenant_reminder_settings: office.tenant_reminder_settings || [],
        comment: office.comment || '',
        is_active: office.is_active !== undefined ? office.is_active : true,
      });

      setSelectedTenants(office.tenants || []);

      // Установить выбранных для напоминаний
      const reminderIds = (office.tenant_reminder_settings || [])
        .filter(s => s.is_enabled)
        .map(s => s.user_id);
      setSelectedReminderTenants(reminderIds);

      setIsEditing(false);
      setErrors({});
    }
  }, [office, isOpen]);

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
    setSelectedReminderTenants(selectedReminderTenants.filter(id => id !== userId));

    // Обновляем formData одним вызовом, чтобы не терять данные
    setFormData({
      ...formData,
      tenant_ids: formData.tenant_ids.filter(id => id !== userId),
      tenant_reminder_settings: formData.tenant_reminder_settings.filter(s => s.user_id !== userId)
    });
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

  const handleSave = async () => {
    if (!validateForm()) return;

    setIsLoading(true);
    try {
      // Подготавливаем данные для отправки
      const cleanedData = { ...formData };

      // Теперь всегда используем только "days_before", очищаем datetime поля
      cleanedData.admin_reminder_type = 'days_before';
      cleanedData.admin_reminder_datetime = null;
      cleanedData.tenant_reminder_type = 'days_before';
      cleanedData.tenant_reminder_datetime = null;

      console.log('Sending office update:', cleanedData);

      const updatedOffice = await officeApi.update(office.id, cleanedData);

      toast({
        title: 'Успешно',
        description: 'Офис обновлен',
        status: 'success',
        duration: 3000,
      });

      await onUpdate();
      onClose();
    } catch (error) {
      toast({
        title: 'Ошибка',
        description: error.response?.data?.detail || 'Не удалось обновить офис',
        status: 'error',
        duration: 5000,
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleDelete = async () => {
    setIsLoading(true);
    try {
      await officeApi.delete(office.id);

      toast({
        title: 'Успешно',
        description: `Офис "${office.office_number}" удален`,
        status: 'success',
        duration: 3000,
      });

      await onUpdate();
      onDeleteClose();
      onClose();
    } catch (error) {
      toast({
        title: 'Ошибка',
        description: error.response?.data?.detail || 'Не удалось удалить офис',
        status: 'error',
        duration: 5000,
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleClear = async () => {
    setIsLoading(true);
    try {
      await officeApi.clear(office.id);

      toast({
        title: 'Успешно',
        description: `Офис "${office.office_number}" очищен. Сохранены только базовые данные.`,
        status: 'success',
        duration: 3000,
      });

      // Обновляем локальные данные - очищаем всё кроме базовых полей
      office.tenants = [];
      office.duration_months = null;
      office.rental_start_date = null;
      office.rental_end_date = null;
      office.payment_day = null;
      office.payment_type = null;
      office.last_payment_date = null;
      office.next_payment_date = null;
      office.payment_status = null;
      office.payment_notes = null;
      office.admin_reminder_enabled = false;
      office.admin_reminder_days = 5;
      office.tenant_reminder_enabled = false;
      office.tenant_reminder_days = 5;
      office.comment = null;

      await onUpdate();
      onClearClose();
      onClose();
    } catch (error) {
      toast({
        title: 'Ошибка',
        description: error.response?.data?.detail || 'Не удалось очистить офис',
        status: 'error',
        duration: 5000,
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleRelocate = async () => {
    if (!selectedTargetOffice) {
      toast({
        title: 'Ошибка',
        description: 'Выберите целевой офис',
        status: 'error',
        duration: 3000,
      });
      return;
    }

    setIsLoading(true);
    try {
      const result = await officeApi.relocate(office.id, selectedTargetOffice.id);

      toast({
        title: 'Успешно',
        description: result.message || `Постояльцы переселены в офис "${selectedTargetOffice.office_number}"`,
        status: 'success',
        duration: 5000,
      });

      await onUpdate();
      onRelocateClose();
      onClose();
    } catch (error) {
      toast({
        title: 'Ошибка',
        description: error.response?.data?.detail || 'Не удалось переселить постояльцев',
        status: 'error',
        duration: 5000,
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handlePayment = async () => {
    if (!office.rental_start_date) {
      toast({
        title: 'Ошибка',
        description: 'Не указана дата начала аренды',
        status: 'error',
        duration: 3000,
      });
      return;
    }

    // Проверка совпадения дат
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const rentalStart = new Date(office.rental_start_date);
    rentalStart.setHours(0, 0, 0, 0);

    const datesMatch = today.getTime() === rentalStart.getTime();
    setPaymentDateMismatch(!datesMatch);

    // Открыть диалог подтверждения
    onPaymentConfirmOpen();
  };

  const handleConfirmPayment = async (updateStartDate = false) => {
    setIsPaymentLoading(true);
    try {
      await officeApi.recordPayment(office.id, {
        update_rental_start_date: updateStartDate
      });

      toast({
        title: 'Успешно',
        description: 'Платеж записан',
        status: 'success',
        duration: 3000,
      });

      await onUpdate();
      onPaymentConfirmClose();
    } catch (error) {
      toast({
        title: 'Ошибка',
        description: error.response?.data?.detail || 'Не удалось записать платеж',
        status: 'error',
        duration: 5000,
      });
    } finally {
      setIsPaymentLoading(false);
    }
  };

  const handleCancel = () => {
    // Автоматически определяем тип оплаты по длительности аренды
    const durationMonths = office.duration_months || null;
    const paymentType = durationMonths === 1 ? 'monthly' : durationMonths > 1 ? 'one_time' : null;

    setFormData({
      office_number: office.office_number || '',
      floor: office.floor || 0,
      capacity: office.capacity || 1,
      price_per_month: office.price_per_month || 0,
      duration_months: durationMonths,
      rental_start_date: office.rental_start_date || null,
      rental_end_date: office.rental_end_date || null,
      payment_type: paymentType,
      admin_reminder_enabled: office.admin_reminder_enabled || false,
      admin_reminder_days: office.admin_reminder_days || 5,
      admin_reminder_type: office.admin_reminder_type || 'days_before',
      admin_reminder_datetime: formatDatetimeLocal(office.admin_reminder_datetime),
      tenant_reminder_enabled: office.tenant_reminder_enabled || false,
      tenant_reminder_days: office.tenant_reminder_days || 5,
      tenant_reminder_type: office.tenant_reminder_type || 'days_before',
      tenant_reminder_datetime: formatDatetimeLocal(office.tenant_reminder_datetime),
      tenant_ids: office.tenants ? office.tenants.map(t => t.id) : [],
      tenant_reminder_settings: office.tenant_reminder_settings || [],
      comment: office.comment || '',
      is_active: office.is_active !== undefined ? office.is_active : true,
    });
    setSelectedTenants(office.tenants || []);
    const reminderIds = (office.tenant_reminder_settings || [])
      .filter(s => s.is_enabled)
      .map(s => s.user_id);
    setSelectedReminderTenants(reminderIds);
    setErrors({});
    setIsEditing(false);
  };

  if (!office) return null;

  return (
    <>
      <Modal isOpen={isOpen} onClose={onClose} size="xl" scrollBehavior="inside">
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>
            <HStack justify="space-between">
              <HStack>
                <Text>Офис {office.office_number}</Text>
                <Badge colorScheme={office.is_active ? 'green' : 'gray'}>
                  {office.is_active ? 'Активен' : 'Неактивен'}
                </Badge>
              </HStack>
            </HStack>
          </ModalHeader>
          <ModalCloseButton />

          <ModalBody>
            {isEditing ? (
              // Режим редактирования
              <VStack align="stretch" spacing={4}>
                <FormControl isInvalid={errors.office_number} isRequired>
                  <FormLabel>Номер офиса</FormLabel>
                  <Input
                    value={formData.office_number}
                    onChange={(e) => setFormData({...formData, office_number: e.target.value})}
                    maxLength={20}
                  />
                  {errors.office_number && (
                    <FormHelperText color="red.500">{errors.office_number}</FormHelperText>
                  )}
                </FormControl>

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
                  </FormControl>
                </HStack>

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
                </FormControl>

                <FormControl>
                  <FormLabel>Длительность аренды (месяцев)</FormLabel>
                  <NumberInput
                    value={formData.duration_months || ''}
                    onChange={(val) => {
                      const months = val ? parseInt(val) : null;
                      // Автоматически определяем тип оплаты
                      const paymentType = months === 1 ? 'monthly' : months > 1 ? 'one_time' : null;
                      setFormData({...formData, duration_months: months, payment_type: paymentType});
                    }}
                    min={1}
                    max={120}
                  >
                    <NumberInputField placeholder="Например: 6, 12, 24" />
                    <NumberInputStepper>
                      <NumberIncrementStepper />
                      <NumberDecrementStepper />
                    </NumberInputStepper>
                  </NumberInput>
                  <FormHelperText>
                    Скидки: от 6 месяцев -10%, от 12 месяцев -15%.
                    {formData.duration_months && (
                      <Text as="span" color="blue.600" fontWeight="medium">
                        {' '}Тип оплаты: {formData.duration_months === 1 ? 'Ежемесячная' : 'Разовая'}
                      </Text>
                    )}
                  </FormHelperText>
                </FormControl>

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

                <Divider />

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

                <FormControl>
                  <FormLabel>Напоминание администратору</FormLabel>
                  <Checkbox
                    isChecked={formData.admin_reminder_enabled}
                    onChange={(e) => setFormData({...formData, admin_reminder_enabled: e.target.checked})}
                  >
                    Включить напоминание
                  </Checkbox>

                  {formData.admin_reminder_enabled && (
                    <VStack align="stretch" spacing={2} mt={2} ml={6}>
                      <NumberInput
                        value={formData.admin_reminder_days || 5}
                        min={1}
                        max={365}
                        onChange={(valueString) => setFormData({...formData, admin_reminder_days: parseInt(valueString)})}
                      >
                        <NumberInputField placeholder="За сколько дней до окончания аренды" />
                        <NumberInputStepper>
                          <NumberIncrementStepper />
                          <NumberDecrementStepper />
                        </NumberInputStepper>
                      </NumberInput>
                      <FormHelperText>Напоминание будет отправлено за указанное количество дней до окончания аренды</FormHelperText>
                    </VStack>
                  )}
                </FormControl>

                <FormControl mt={4}>
                  <FormLabel>Напоминание арендатору</FormLabel>
                  <Checkbox
                    isChecked={formData.tenant_reminder_enabled}
                    onChange={(e) => setFormData({...formData, tenant_reminder_enabled: e.target.checked})}
                  >
                    Включить напоминание
                  </Checkbox>

                  {formData.tenant_reminder_enabled && (
                    <VStack align="stretch" spacing={2} mt={2} ml={6}>
                      <NumberInput
                        value={formData.tenant_reminder_days || 5}
                        min={1}
                        max={365}
                        onChange={(valueString) => setFormData({...formData, tenant_reminder_days: parseInt(valueString)})}
                      >
                        <NumberInputField placeholder="За сколько дней до окончания аренды" />
                        <NumberInputStepper>
                          <NumberIncrementStepper />
                          <NumberDecrementStepper />
                        </NumberInputStepper>
                      </NumberInput>
                      <FormHelperText>Напоминание будет отправлено за указанное количество дней до окончания аренды</FormHelperText>

                      {selectedTenants.length > 0 && (
                        <Box mt={3}>
                          <Text fontSize="sm" fontWeight="medium" mb={2}>Кому отправлять:</Text>
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
                    </VStack>
                  )}
                </FormControl>

                <Divider />

                <FormControl>
                  <FormLabel>Комментарий</FormLabel>
                  <Textarea
                    value={formData.comment}
                    onChange={(e) => setFormData({...formData, comment: e.target.value})}
                    rows={3}
                  />
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
              </VStack>
            ) : (
              // Режим просмотра
              <VStack align="stretch" spacing={3}>
                <HStack justify="space-between">
                  <Text fontWeight="bold">Номер офиса:</Text>
                  <Text>{office.office_number}</Text>
                </HStack>

                <HStack justify="space-between">
                  <Text fontWeight="bold">Этаж:</Text>
                  <Text>{office.floor}</Text>
                </HStack>

                <HStack justify="space-between">
                  <Text fontWeight="bold">Вместимость:</Text>
                  <Text>{office.capacity} человек</Text>
                </HStack>

                <HStack justify="space-between">
                  <Text fontWeight="bold">Стоимость в месяц:</Text>
                  <Text fontWeight="semibold" color="blue.600">{office.price_per_month} ₽</Text>
                </HStack>

                {office.duration_months && (
                  <>
                    <HStack justify="space-between">
                      <Text fontWeight="bold">Длительность аренды:</Text>
                      <Text>
                        {office.duration_months} {office.duration_months === 1 ? 'месяц' : office.duration_months < 5 ? 'месяца' : 'месяцев'}
                      </Text>
                    </HStack>

                    {office.rental_start_date && (
                      <HStack justify="space-between">
                        <Text fontWeight="bold">Дата начала аренды:</Text>
                        <Text>{new Date(office.rental_start_date).toLocaleDateString('ru-RU')}</Text>
                      </HStack>
                    )}

                    {office.rental_end_date && (
                      <HStack justify="space-between">
                        <Text fontWeight="bold">Дата окончания аренды:</Text>
                        <Text>{new Date(office.rental_end_date).toLocaleDateString('ru-RU')}</Text>
                      </HStack>
                    )}
                  </>
                )}

                <Divider />

                <Box>
                  <HStack mb={2}>
                    <Icon as={FiUsers} />
                    <Text fontWeight="bold">Постояльцы:</Text>
                    <Badge>{office.tenants?.length || 0}/{office.capacity}</Badge>
                  </HStack>
                  {office.tenants && office.tenants.length > 0 ? (
                    <Stack spacing={2}>
                      {office.tenants.map(tenant => (
                        <Tag key={tenant.id} size="md" colorScheme="blue">
                          <TagLabel>{tenant.full_name} (ID: {tenant.telegram_id})</TagLabel>
                        </Tag>
                      ))}
                    </Stack>
                  ) : (
                    <Text color="gray.500" fontSize="sm">Нет постояльцев</Text>
                  )}
                </Box>

                <Divider />

                <Box>
                  <HStack mb={2}>
                    <Icon as={FiBell} />
                    <Text fontWeight="bold">Напоминания:</Text>
                  </HStack>
                  <VStack align="stretch" spacing={1} fontSize="sm">
                    <HStack>
                      <Badge colorScheme={office.admin_reminder_enabled ? 'green' : 'gray'}>
                        Админу
                      </Badge>
                      <Text>
                        {office.admin_reminder_enabled
                          ? `За ${office.admin_reminder_days} дней`
                          : 'Отключено'}
                      </Text>
                    </HStack>
                    <HStack>
                      <Badge colorScheme={office.tenant_reminder_enabled ? 'green' : 'gray'}>
                        Постояльцам
                      </Badge>
                      <Text>
                        {office.tenant_reminder_enabled
                          ? `За ${office.tenant_reminder_days} дней (${office.tenant_reminder_settings?.filter(s => s.is_enabled).length || 0} чел.)`
                          : 'Отключено'}
                      </Text>
                    </HStack>
                  </VStack>
                </Box>

                {/* Информация об оплате */}
                {office.tenants && office.tenants.length > 0 && (office.payment_type || office.next_payment_date) && (
                  <>
                    <Divider />
                    <Box>
                      <Text fontWeight="bold" mb={2}>💰 Информация об оплате</Text>
                      <VStack align="stretch" spacing={2}>
                        {office.payment_type && (
                          <HStack justify="space-between">
                            <Text fontWeight="bold">Тип оплаты:</Text>
                            <Badge colorScheme={office.payment_type === 'one_time' ? 'purple' : 'blue'}>
                              {office.payment_type === 'one_time' ? 'Разовая' : 'Ежемесячная'}
                            </Badge>
                          </HStack>
                        )}

                        {office.payment_status && (
                          <HStack justify="space-between">
                            <Text fontWeight="bold">Статус:</Text>
                            <Badge colorScheme={
                              office.payment_status === 'paid' ? 'green' :
                              office.payment_status === 'overdue' ? 'red' : 'yellow'
                            }>
                              {office.payment_status === 'paid' ? 'Оплачено' :
                               office.payment_status === 'overdue' ? 'Просрочено' : 'Ожидается'}
                            </Badge>
                          </HStack>
                        )}

                        {office.last_payment_date && (
                          <HStack justify="space-between">
                            <Text fontWeight="bold">Последний платеж:</Text>
                            <Text>
                              {new Date(office.last_payment_date).toLocaleDateString('ru-RU')}
                            </Text>
                          </HStack>
                        )}

                        {office.next_payment_date && (
                          <HStack justify="space-between">
                            <Text fontWeight="bold">Следующий платеж:</Text>
                            <Text>
                              {new Date(office.next_payment_date).toLocaleDateString('ru-RU')}
                            </Text>
                          </HStack>
                        )}
                      </VStack>
                    </Box>
                  </>
                )}

                {office.comment && (
                  <>
                    <Divider />
                    <Box>
                      <Text fontWeight="bold" mb={1}>Комментарий:</Text>
                      <Text fontSize="sm" color="gray.600">{office.comment}</Text>
                    </Box>
                  </>
                )}

                <Divider />

                <HStack justify="space-between">
                  <Text fontWeight="bold">Статус:</Text>
                  <Badge colorScheme={office.is_active ? 'green' : 'gray'} fontSize="sm">
                    {office.is_active ? 'Активен' : 'Неактивен'}
                  </Badge>
                </HStack>
              </VStack>
            )}
          </ModalBody>

          <ModalFooter>
            {isEditing ? (
              <HStack spacing={2}>
                <Button variant="outline" onClick={handleCancel}>
                  Отмена
                </Button>
                <Button
                  colorScheme="blue"
                  onClick={handleSave}
                  isLoading={isLoading}
                  leftIcon={<FiEdit2 />}
                >
                  Сохранить
                </Button>
              </HStack>
            ) : (
              <VStack spacing={2} align="stretch" width="100%">
                <HStack spacing={2} justify="flex-start">
                  {/* Кнопка оплаты - показывается если есть постояльцы и дата начала аренды */}
                  {office.tenants && office.tenants.length > 0 && office.rental_start_date && (
                    <Button
                      colorScheme={
                        office.last_payment_date
                          ? (office.payment_status === 'paid' ? 'green' : 'blue')
                          : 'orange'
                      }
                      onClick={handlePayment}
                      isLoading={isPaymentLoading}
                      leftIcon={<FiCheck />}
                      flex="1"
                      variant={office.last_payment_date ? 'solid' : 'outline'}
                    >
                      {office.last_payment_date
                        ? (office.payment_status === 'paid' ? 'Оплачено' : 'Продлить')
                        : 'Оплатить'}
                    </Button>
                  )}
                  {office.tenants && office.tenants.length > 0 && (
                    <Button
                      colorScheme="purple"
                      variant="outline"
                      onClick={onRelocateOpen}
                      leftIcon={<FiArrowRight />}
                      flex="1"
                    >
                      Переселить
                    </Button>
                  )}
                  <Button
                    colorScheme="orange"
                    variant="outline"
                    onClick={onClearOpen}
                    leftIcon={<FiClear />}
                    flex="1"
                  >
                    Очистить офис
                  </Button>
                </HStack>
                <HStack spacing={2}>
                  <Button
                    colorScheme="red"
                    variant="outline"
                    onClick={onDeleteOpen}
                    leftIcon={<FiTrash2 />}
                    flex="1"
                  >
                    Удалить
                  </Button>
                  <Button
                    colorScheme="blue"
                    onClick={() => setIsEditing(true)}
                    leftIcon={<FiEdit2 />}
                    flex="1"
                  >
                    Редактировать
                  </Button>
                </HStack>
              </VStack>
            )}
          </ModalFooter>
        </ModalContent>
      </Modal>

      {/* AlertDialog для удаления */}
      <AlertDialog
        isOpen={isDeleteOpen}
        leastDestructiveRef={cancelRef}
        onClose={onDeleteClose}
      >
        <AlertDialogOverlay>
          <AlertDialogContent>
            <AlertDialogHeader>Удалить офис</AlertDialogHeader>

            <AlertDialogBody>
              Вы уверены, что хотите удалить офис <strong>"{office.office_number}"</strong>?
              Это действие необратимо.
            </AlertDialogBody>

            <AlertDialogFooter>
              <Button ref={cancelRef} onClick={onDeleteClose}>
                Отмена
              </Button>
              <Button
                colorScheme="red"
                onClick={handleDelete}
                ml={3}
                isLoading={isLoading}
              >
                Удалить
              </Button>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialogOverlay>
      </AlertDialog>

      {/* AlertDialog для очистки */}
      <AlertDialog
        isOpen={isClearOpen}
        leastDestructiveRef={cancelRef}
        onClose={onClearClose}
      >
        <AlertDialogOverlay>
          <AlertDialogContent>
            <AlertDialogHeader>Очистить офис</AlertDialogHeader>

            <AlertDialogBody>
              <VStack align="stretch" spacing={2}>
                <Text>
                  Вы уверены, что хотите очистить офис <strong>"{office.office_number}"</strong>?
                </Text>
                <Text fontSize="sm" color="gray.600">
                  Будут удалены:
                </Text>
                <VStack align="stretch" pl={4} fontSize="sm" spacing={1}>
                  <Text>• Все постояльцы</Text>
                  <Text>• Настройки напоминаний</Text>
                  <Text>• Комментарий</Text>
                </VStack>
                <Text fontSize="sm" color="gray.600" mt={2}>
                  Сохранятся: номер офиса, этаж, стоимость, вместимость.
                </Text>
              </VStack>
            </AlertDialogBody>

            <AlertDialogFooter>
              <Button ref={cancelRef} onClick={onClearClose}>
                Отмена
              </Button>
              <Button
                colorScheme="orange"
                onClick={handleClear}
                ml={3}
                isLoading={isLoading}
              >
                Очистить
              </Button>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialogOverlay>
      </AlertDialog>

      {/* AlertDialog для переселения */}
      <AlertDialog
        isOpen={isRelocateOpen}
        leastDestructiveRef={cancelRef}
        onClose={onRelocateClose}
      >
        <AlertDialogOverlay>
          <AlertDialogContent>
            <AlertDialogHeader>Переселить постояльцев</AlertDialogHeader>

            <AlertDialogBody>
              <VStack align="stretch" spacing={3}>
                <Text>
                  Выберите офис, в который хотите переселить постояльцев из офиса <strong>"{office.office_number}"</strong>:
                </Text>

                {office.tenants && office.tenants.length > 0 && (
                  <Box>
                    <Text fontSize="sm" fontWeight="medium" mb={2}>Переселяются:</Text>
                    <Stack spacing={1}>
                      {office.tenants.map(tenant => (
                        <Tag key={tenant.id} size="sm" colorScheme="blue">
                          {tenant.full_name}
                        </Tag>
                      ))}
                    </Stack>
                  </Box>
                )}

                <FormControl>
                  <FormLabel>Целевой офис</FormLabel>
                  <Select
                    placeholder="Выберите офис"
                    value={selectedTargetOffice?.id || ''}
                    onChange={(e) => {
                      const targetId = parseInt(e.target.value);
                      const target = offices.find(o => o.id === targetId);
                      setSelectedTargetOffice(target);
                    }}
                  >
                    {offices
                      .filter(o => o.id !== office.id && o.is_active)
                      .map(o => {
                        const currentCount = o.tenants?.length || 0;
                        const relocatingCount = office.tenants?.length || 0;
                        const canFit = currentCount + relocatingCount <= o.capacity;

                        return (
                          <option
                            key={o.id}
                            value={o.id}
                            disabled={!canFit}
                          >
                            {o.office_number} - {currentCount}/{o.capacity}
                            {canFit ? ' (достаточно места)' : ' (не вмещает)'}
                          </option>
                        );
                      })}
                  </Select>
                  <FormHelperText>
                    Будут перенесены все постояльцы, информация о платеже и настройки напоминаний
                  </FormHelperText>
                </FormControl>

                {selectedTargetOffice && (
                  <Box p={3} bg="blue.50" borderRadius="md" fontSize="sm">
                    <Text fontWeight="medium" mb={1}>Целевой офис: {selectedTargetOffice.office_number}</Text>
                    <Text>Этаж: {selectedTargetOffice.floor}</Text>
                    <Text>
                      Вместимость: {(selectedTargetOffice.tenants?.length || 0) + (office.tenants?.length || 0)}/{selectedTargetOffice.capacity}
                      после переселения
                    </Text>
                  </Box>
                )}
              </VStack>
            </AlertDialogBody>

            <AlertDialogFooter>
              <Button ref={cancelRef} onClick={onRelocateClose}>
                Отмена
              </Button>
              <Button
                colorScheme="purple"
                onClick={handleRelocate}
                ml={3}
                isLoading={isLoading}
                isDisabled={!selectedTargetOffice}
              >
                Переселить
              </Button>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialogOverlay>
      </AlertDialog>

      {/* AlertDialog для подтверждения оплаты */}
      <AlertDialog
        isOpen={isPaymentConfirmOpen}
        leastDestructiveRef={cancelRef}
        onClose={onPaymentConfirmClose}
      >
        <AlertDialogOverlay>
          <AlertDialogContent>
            <AlertDialogHeader>Подтверждение оплаты</AlertDialogHeader>

            <AlertDialogBody>
              <VStack align="stretch" spacing={3}>
                <Box>
                  <Text fontWeight="medium" mb={2}>Информация:</Text>
                  <VStack align="stretch" spacing={1} fontSize="sm">
                    <HStack justify="space-between">
                      <Text>Дата оплаты (сегодня):</Text>
                      <Text fontWeight="bold">{new Date().toLocaleDateString('ru-RU')}</Text>
                    </HStack>
                    <HStack justify="space-between">
                      <Text>Дата начала аренды:</Text>
                      <Text fontWeight="bold">
                        {office.rental_start_date
                          ? new Date(office.rental_start_date).toLocaleDateString('ru-RU')
                          : 'Не указана'}
                      </Text>
                    </HStack>
                  </VStack>
                </Box>

                {paymentDateMismatch ? (
                  <Box p={3} bg="orange.50" borderRadius="md" borderWidth="1px" borderColor="orange.200">
                    <HStack mb={2}>
                      <Icon as={FiAlertTriangle} color="orange.500" />
                      <Text fontWeight="bold" color="orange.700">Внимание!</Text>
                    </HStack>
                    <Text fontSize="sm" color="orange.700">
                      Дата оплаты не совпадает с датой начала аренды.
                      Вы можете подтвердить оплату с текущими датами или обновить дату начала аренды.
                    </Text>
                  </Box>
                ) : (
                  <Box p={3} bg="green.50" borderRadius="md" borderWidth="1px" borderColor="green.200">
                    <HStack>
                      <Icon as={FiCheck} color="green.500" />
                      <Text fontSize="sm" color="green.700">Даты совпадают ✓</Text>
                    </HStack>
                  </Box>
                )}
              </VStack>
            </AlertDialogBody>

            <AlertDialogFooter>
              {/* Используем VStack для вертикального выравнивания */}
              <VStack width="100%" spacing={3}>

                {/* Кнопка обновления даты (если есть несовпадение) */}
                {paymentDateMismatch && (
                  <Button
                    width="100%"
                    colorScheme="blue"
                    onClick={() => handleConfirmPayment(true)}
                    isLoading={isPaymentLoading}
                  >
                    Обновить дату начала аренды
                  </Button>
                )}

                {/* Кнопка подтверждения */}
                <Button
                  width="100%"
                  colorScheme="green"
                  onClick={() => handleConfirmPayment(false)}
                  isLoading={isPaymentLoading}
                >
                  Подтвердить оплату
                </Button>

                {/* Кнопка отмены */}
                <Button
                  width="100%"
                  ref={cancelRef}
                  onClick={onPaymentConfirmClose}
                >
                  Отмена
                </Button>
              </VStack>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialogOverlay>
      </AlertDialog>
    </>
  );
};

export default OfficeDetailModal;
