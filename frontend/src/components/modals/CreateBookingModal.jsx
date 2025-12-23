import React, { useState, useEffect, useMemo } from 'react';
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
  ModalFooter,
  Button,
  Input,
  FormControl,
  FormLabel,
  FormHelperText,
  Select,
  NumberInput,
  NumberInputField,
  NumberInputStepper,
  NumberIncrementStepper,
  NumberDecrementStepper,
  Checkbox,
  useToast,
  Alert,
  AlertIcon,
  AlertDescription,
  Divider,
  Box,
  InputGroup,
  InputLeftElement,
  Icon
} from '@chakra-ui/react';
import { FiSave, FiX, FiDollarSign, FiSearch, FiUser } from 'react-icons/fi';
import { bookingApi } from '../../utils/api';
import { formatLocalDate } from '../../utils/dateUtils';

const CreateBookingModal = ({ isOpen, onClose, onSuccess, tariffs, users }) => {
  const [formData, setFormData] = useState({
    user_id: '',
    tariff_id: '',
    visit_date: '',
    visit_time: '',
    duration: 1,
    months: 1, // Для месячных тарифов
    promocode_id: null,
    amount: 0,
    paid: true,  // По умолчанию оплачено для бронирований администратора
    confirmed: true  // По умолчанию подтверждено для бронирований администратора
  });

  const [selectedTariff, setSelectedTariff] = useState(null);
  const [calculatedAmount, setCalculatedAmount] = useState(0);
  const [isCalculating, setIsCalculating] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [errors, setErrors] = useState({});

  // State для поиска пользователя
  const [userSearchQuery, setUserSearchQuery] = useState('');
  const [isUserDropdownOpen, setIsUserDropdownOpen] = useState(false);
  const [selectedUser, setSelectedUser] = useState(null);

  const toast = useToast();

  // Сброс формы
  const resetForm = () => {
    setFormData({
      user_id: '',
      tariff_id: '',
      visit_date: '',
      visit_time: '',
      duration: 1,
      months: 1,
      promocode_id: null,
      amount: 0,
      paid: true,  // По умолчанию оплачено для бронирований администратора
      confirmed: true  // По умолчанию подтверждено для бронирований администратора
    });
    setSelectedTariff(null);
    setCalculatedAmount(0);
    setErrors({});
    setUserSearchQuery('');
    setIsUserDropdownOpen(false);
    setSelectedUser(null);
  };

  // Сброс при открытии/закрытии модального окна
  useEffect(() => {
    if (isOpen) {
      resetForm();
    }
  }, [isOpen]);

  // Обработчик изменения поля
  const handleFieldChange = (field, value) => {
    setFormData(prev => ({ ...prev, [field]: value }));

    // Очистка ошибки для этого поля
    if (errors[field]) {
      setErrors(prev => {
        const newErrors = { ...prev };
        delete newErrors[field];
        return newErrors;
      });
    }
  };

  // Обработчик выбора тарифа
  const handleTariffChange = (tariffId) => {
    const tariff = tariffs.find(t => t.id === parseInt(tariffId));
    setSelectedTariff(tariff);
    handleFieldChange('tariff_id', tariffId);

    // Сбросить время и длительность если не meeting_room и не почасовой тариф
    const isHourlyTariff = tariff && (
      tariff.purpose === 'meeting_room' ||
      tariff.purpose === 'coworking' ||
      tariff.name.toLowerCase().includes('час')
    );

    if (tariff && !isHourlyTariff) {
      setFormData(prev => ({
        ...prev,
        tariff_id: tariffId,
        visit_time: '',
        duration: 1
      }));
    }
  };

  // Обработчик изменения длительности
  const handleDurationChange = (value) => {
    const duration = parseInt(value) || 1;
    handleFieldChange('duration', duration);
  };

  // Обработчик выбора пользователя из списка
  const handleSelectUser = (user) => {
    setSelectedUser(user);
    handleFieldChange('user_id', user.telegram_id);
    setUserSearchQuery(`${user.full_name || user.username}${user.phone ? ` (${user.phone})` : ''}`);
    setIsUserDropdownOpen(false);
  };

  // Обработчик изменения поискового запроса
  const handleUserSearchChange = (e) => {
    const value = e.target.value;
    setUserSearchQuery(value);
    setIsUserDropdownOpen(value.trim().length > 0);

    // Если очистили поле - сбросить выбор
    if (!value.trim()) {
      setSelectedUser(null);
      handleFieldChange('user_id', '');
    }
  };

  // Фильтрация пользователей по поисковому запросу
  const filteredUsers = useMemo(() => {
    if (!users || users.length === 0) return [];

    if (!userSearchQuery.trim()) {
      return users;
    }

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

  // Расчет суммы
  const calculateAmount = () => {
    if (!selectedTariff) return;

    setIsCalculating(true);

    try {
      const tariffName = selectedTariff.name.toLowerCase();
      let finalAmount = selectedTariff.price;
      let discount = 0;

      // Определяем тип тарифа и рассчитываем стоимость
      if (tariffName.includes('3 час')) {
        // Тариф "3 часа" - фиксированная стоимость
        finalAmount = selectedTariff.price;

      } else if (tariffName.includes('тестовый день') || tariffName.includes('опенспейс на день')) {
        // Дневные тарифы - фиксированная стоимость
        finalAmount = selectedTariff.price;

      } else if (tariffName.includes('месяц')) {
        // Месячные тарифы - расчет с учетом количества месяцев и скидок
        const months = parseInt(formData.months) || 1;
        finalAmount = selectedTariff.price * months;

        // Применяем скидки
        if (months >= 12) {
          discount = 15; // Скидка 15% с 12 месяцев
        } else if (months >= 6) {
          discount = 10; // Скидка 10% с 6 месяцев
        }

        if (discount > 0) {
          finalAmount = finalAmount * (1 - discount / 100);
        }

      } else if (selectedTariff.purpose === 'meeting_room') {
        // Переговорные - умножаем на duration (часы)
        const duration = parseInt(formData.duration) || 1;
        finalAmount = selectedTariff.price * duration;
      }

      setCalculatedAmount(finalAmount);
      setFormData(prev => ({ ...prev, amount: finalAmount }));
    } catch (error) {
      console.error('Error calculating amount:', error);
    } finally {
      setIsCalculating(false);
    }
  };

  // Вызывать расчет при изменении tariff_id, duration или months
  useEffect(() => {
    if (formData.tariff_id) {
      calculateAmount();
    }
  }, [formData.tariff_id, formData.duration, formData.months]);

  // Автоматическая установка начальной длительности для тарифа "3 часа"
  useEffect(() => {
    if (selectedTariff && selectedTariff.name.toLowerCase().includes('3 час')) {
      // Устанавливаем только если длительность еще не была изменена пользователем
      setFormData(prev => {
        // Сбрасываем на 3 часа только при смене тарифа
        if (prev.tariff_id !== selectedTariff.id) {
          return { ...prev, duration: 3 };
        }
        return prev;
      });
    }
  }, [selectedTariff?.id]);

  // Закрытие dropdown при клике вне области
  useEffect(() => {
    const handleClickOutside = (event) => {
      const target = event.target;
      // Проверяем что клик не по элементам dropdown
      if (!target.closest('[data-user-dropdown]')) {
        setIsUserDropdownOpen(false);
      }
    };

    if (isUserDropdownOpen) {
      document.addEventListener('mousedown', handleClickOutside);
      return () => {
        document.removeEventListener('mousedown', handleClickOutside);
      };
    }
  }, [isUserDropdownOpen]);

  // Валидация формы
  const validate = () => {
    const newErrors = {};

    if (!formData.user_id) {
      newErrors.user_id = 'Выберите пользователя';
    }

    if (!formData.tariff_id) {
      newErrors.tariff_id = 'Выберите тариф';
    }

    if (!formData.visit_date) {
      newErrors.visit_date = 'Укажите дату посещения';
    }

    // Для почасовых тарифов и переговорных требуется время
    const tariffName = selectedTariff?.name.toLowerCase() || '';
    const requiresTime = selectedTariff?.purpose === 'meeting_room' || tariffName.includes('час');
    const requiresDuration = selectedTariff?.purpose === 'meeting_room';

    if (requiresTime && !formData.visit_time) {
      newErrors.visit_time = 'Укажите время начала';
    }

    if (requiresDuration && (!formData.duration || formData.duration < 1)) {
      newErrors.duration = 'Укажите длительность (минимум 1 час)';
    }

    if (formData.amount <= 0) {
      newErrors.amount = 'Сумма должна быть больше 0';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  // Пересчет суммы по требованию
  const handleRecalculate = () => {
    calculateAmount();
    toast({
      title: 'Сумма пересчитана',
      status: 'success',
      duration: 2000,
      isClosable: true,
    });
  };

  // Сохранение бронирования
  const handleSave = async () => {
    if (!validate()) {
      toast({
        title: 'Ошибка валидации',
        description: 'Проверьте заполнение всех полей',
        status: 'error',
        duration: 3000,
        isClosable: true,
      });
      return;
    }

    setIsSaving(true);
    try {
      // Подготовка данных для API
      const bookingData = {
        user_id: parseInt(formData.user_id),
        tariff_id: parseInt(formData.tariff_id),
        visit_date: formData.visit_date,
        visit_time: formData.visit_time || null,
        duration: formData.duration || null,
        amount: parseFloat(formData.amount),
        paid: formData.paid,
        confirmed: formData.confirmed,
        promocode_id: formData.promocode_id || null
      };

      console.log('Создание бронирования с данными:', bookingData);

      // Создание через API
      const result = await bookingApi.create(bookingData);

      toast({
        title: 'Успешно',
        description: 'Бронирование создано',
        status: 'success',
        duration: 3000,
        isClosable: true,
      });

      // Вызов callback успеха и закрытие модального окна
      if (onSuccess) {
        onSuccess(result);
      }
      onClose();
      resetForm();
    } catch (error) {
      console.error('Ошибка при создании бронирования:', error);

      let errorMessage = 'Не удалось создать бронирование';
      if (error.response?.data?.detail) {
        errorMessage = error.response.data.detail;
      } else if (error.message) {
        errorMessage = error.message;
      }

      toast({
        title: 'Ошибка',
        description: errorMessage,
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    } finally {
      setIsSaving(false);
    }
  };

  // Создание бронирования без оплаты (бесплатно)
  const handleSaveWithoutPayment = async () => {
    // Валидация полей
    const newErrors = {};

    if (!formData.user_id) {
      newErrors.user_id = 'Выберите пользователя';
    }
    if (!formData.tariff_id) {
      newErrors.tariff_id = 'Выберите тариф';
    }
    if (!formData.visit_date) {
      newErrors.visit_date = 'Укажите дату посещения';
    }

    // Для почасовых тарифов требуется время и длительность
    const isHourlyTariff = selectedTariff?.purpose === 'meeting_room' ||
                           selectedTariff?.purpose === 'coworking' ||
                           selectedTariff?.name.toLowerCase().includes('час');

    if (isHourlyTariff) {
      if (!formData.visit_time) {
        newErrors.visit_time = 'Укажите время начала';
      }
      if (!formData.duration || formData.duration < 1) {
        newErrors.duration = 'Укажите длительность (минимум 1 час)';
      }
    }

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      toast({
        title: 'Ошибка валидации',
        description: 'Проверьте заполнение всех полей',
        status: 'error',
        duration: 3000,
        isClosable: true,
      });
      return;
    }

    setIsSaving(true);
    try {
      // Подготовка данных для бесплатной брони
      const bookingData = {
        user_id: parseInt(formData.user_id),
        tariff_id: parseInt(formData.tariff_id),
        visit_date: formData.visit_date,
        visit_time: formData.visit_time || null,
        duration: formData.duration || null,
        amount: 0,  // Бесплатно
        paid: true,  // Считается оплаченным
        confirmed: true,  // Подтверждено
        promocode_id: null
      };

      console.log('Создание бесплатного бронирования:', bookingData);

      const result = await bookingApi.create(bookingData);

      toast({
        title: 'Успешно',
        description: 'Бесплатное бронирование создано',
        status: 'success',
        duration: 3000,
        isClosable: true,
      });

      if (onSuccess) {
        onSuccess(result);
      }
      onClose();
      resetForm();
    } catch (error) {
      console.error('Ошибка при создании бесплатного бронирования:', error);

      let errorMessage = 'Не удалось создать бронирование';
      if (error.response?.data?.detail) {
        errorMessage = error.response.data.detail;
      } else if (error.message) {
        errorMessage = error.message;
      }

      toast({
        title: 'Ошибка',
        description: errorMessage,
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    } finally {
      setIsSaving(false);
    }
  };

  // Отмена
  const handleCancel = () => {
    resetForm();
    onClose();
  };

  // Получить минимальную дату (сегодня)
  const getMinDate = () => {
    return formatLocalDate(new Date());
  };

  // Расчет процента скидки
  const getDiscountPercent = () => {
    const isHourlyTariff = selectedTariff?.purpose === 'meeting_room' ||
                           selectedTariff?.purpose === 'coworking' ||
                           selectedTariff?.name.toLowerCase().includes('час');

    if (isHourlyTariff && formData.duration >= 3) {
      return 10;
    }
    return 0;
  };

  return (
    <Modal isOpen={isOpen} onClose={handleCancel} size="xl">
      <ModalOverlay />
      <ModalContent>
        <ModalHeader>Создать бронирование</ModalHeader>
        <ModalCloseButton />

        <ModalBody>
          <VStack spacing={4} align="stretch">
            <Alert status="info">
              <AlertIcon />
              <AlertDescription>
                Создание нового бронирования от имени администратора
              </AlertDescription>
            </Alert>

            {/* Выбор пользователя */}
            <FormControl isRequired isInvalid={errors.user_id}>
              <FormLabel>Пользователь</FormLabel>

              <Box position="relative" data-user-dropdown>
                <InputGroup>
                  <InputLeftElement pointerEvents="none">
                    <Icon as={selectedUser ? FiUser : FiSearch} color="gray.400" />
                  </InputLeftElement>
                  <Input
                    placeholder="Начните вводить ФИО, телефон или email"
                    value={userSearchQuery}
                    onChange={handleUserSearchChange}
                    onFocus={() => {
                      if (userSearchQuery.trim().length > 0 || !selectedUser) {
                        setIsUserDropdownOpen(true);
                      }
                    }}
                    bg={selectedUser ? 'green.50' : 'white'}
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
                    {filteredUsers.slice(0, 50).map(user => (
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

                    {filteredUsers.length > 50 && (
                      <Box px={4} py={2} bg="gray.50" fontSize="sm" color="gray.600">
                        Показано 50 из {filteredUsers.length}. Уточните запрос для поиска.
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

              {/* Helper text */}
              <FormHelperText>
                {errors.user_id ? (
                  <Text color="red.500">{errors.user_id}</Text>
                ) : (
                  selectedUser ? (
                    <Text color="green.500">✓ Выбран: {selectedUser.full_name || selectedUser.username}</Text>
                  ) : (
                    <Text color="gray.500">Введите имя, фамилию, телефон или email для поиска</Text>
                  )
                )}
              </FormHelperText>
            </FormControl>

            {/* Выбор тарифа */}
            <FormControl isRequired isInvalid={errors.tariff_id}>
              <FormLabel>Тариф</FormLabel>
              <Select
                placeholder="Выберите тариф"
                value={formData.tariff_id}
                onChange={(e) => handleTariffChange(e.target.value)}
              >
                {(() => {
                  if (!tariffs) return null;

                  const activeTariffs = tariffs.filter(t => t.is_active);

                  // Группируем тарифы по категориям
                  const hourlyTariffs = activeTariffs.filter(t =>
                    t.name.toLowerCase().includes('час') && !t.name.toLowerCase().includes('месяц')
                  );
                  const dailyTariffs = activeTariffs.filter(t =>
                    t.name.toLowerCase().includes('день') || t.name.toLowerCase().includes('тестовый')
                  );
                  const monthlyTariffs = activeTariffs.filter(t =>
                    t.name.toLowerCase().includes('месяц')
                  );
                  const meetingRoomTariffs = activeTariffs.filter(t =>
                    t.purpose === 'meeting_room'
                  );

                  return (
                    <>
                      {hourlyTariffs.length > 0 && (
                        <optgroup label="Почасовые тарифы">
                          {hourlyTariffs.map(tariff => (
                            <option key={tariff.id} value={tariff.id}>
                              {tariff.name} - {tariff.price} ₽
                            </option>
                          ))}
                        </optgroup>
                      )}

                      {dailyTariffs.length > 0 && (
                        <optgroup label="Дневные тарифы">
                          {dailyTariffs.map(tariff => (
                            <option key={tariff.id} value={tariff.id}>
                              {tariff.name} - {tariff.price} ₽
                            </option>
                          ))}
                        </optgroup>
                      )}

                      {monthlyTariffs.length > 0 && (
                        <optgroup label="Месячные тарифы">
                          {monthlyTariffs.map(tariff => (
                            <option key={tariff.id} value={tariff.id}>
                              {tariff.name} - {tariff.price} ₽/мес
                            </option>
                          ))}
                        </optgroup>
                      )}

                      {meetingRoomTariffs.length > 0 && (
                        <optgroup label="Переговорные">
                          {meetingRoomTariffs.map(tariff => (
                            <option key={tariff.id} value={tariff.id}>
                              {tariff.name} - {tariff.price} ₽/час
                            </option>
                          ))}
                        </optgroup>
                      )}
                    </>
                  );
                })()}
              </Select>
              {errors.tariff_id && (
                <FormHelperText color="red.500">{errors.tariff_id}</FormHelperText>
              )}
            </FormControl>

            {/* Дата посещения */}
            <FormControl isRequired isInvalid={errors.visit_date}>
              <FormLabel>
                {selectedTariff?.name.toLowerCase().includes('месяц')
                  ? 'Дата начала аренды'
                  : 'Дата посещения'}
              </FormLabel>
              <Input
                type="date"
                value={formData.visit_date}
                onChange={(e) => handleFieldChange('visit_date', e.target.value)}
                min={getMinDate()}
              />
              {errors.visit_date && (
                <FormHelperText color="red.500">{errors.visit_date}</FormHelperText>
              )}
            </FormControl>

            {/* Количество месяцев - для месячных тарифов */}
            {selectedTariff?.name.toLowerCase().includes('месяц') && (
              <FormControl isRequired>
                <FormLabel>Срок аренды (месяцев)</FormLabel>
                <NumberInput
                  min={1}
                  max={24}
                  value={formData.months}
                  onChange={(valueString) => handleFieldChange('months', parseInt(valueString) || 1)}
                >
                  <NumberInputField />
                  <NumberInputStepper>
                    <NumberIncrementStepper />
                    <NumberDecrementStepper />
                  </NumberInputStepper>
                </NumberInput>
                <FormHelperText>
                  {formData.months >= 12 && (
                    <Text color="green.500">✓ Применяется скидка 15% (от 12 месяцев)</Text>
                  )}
                  {formData.months >= 6 && formData.months < 12 && (
                    <Text color="green.500">✓ Применяется скидка 10% (от 6 месяцев)</Text>
                  )}
                  {formData.months < 6 && (
                    <Text color="gray.500">Скидка 10% с 6 месяцев, 15% с 12 месяцев</Text>
                  )}
                </FormHelperText>
              </FormControl>
            )}

            {/* Время посещения - для почасовых тарифов и переговорных */}
            {(selectedTariff?.purpose === 'meeting_room' ||
              selectedTariff?.name.toLowerCase().includes('3 час')) && (
              <FormControl isRequired isInvalid={errors.visit_time}>
                <FormLabel>Время начала</FormLabel>
                <Input
                  type="time"
                  value={formData.visit_time}
                  onChange={(e) => handleFieldChange('visit_time', e.target.value)}
                />
                <FormHelperText>
                  {selectedTariff?.name.includes('3 час')
                    ? 'Автоматически бронируется на 3 часа'
                    : 'Укажите время начала посещения'}
                </FormHelperText>
                {errors.visit_time && (
                  <FormHelperText color="red.500">{errors.visit_time}</FormHelperText>
                )}
              </FormControl>
            )}

            {/* Длительность - только для переговорных (meeting_room) */}
            {selectedTariff?.purpose === 'meeting_room' && (
              <FormControl isRequired isInvalid={errors.duration}>
                <FormLabel>Длительность (часов)</FormLabel>
                <NumberInput
                  min={1}
                  max={24}
                  value={formData.duration}
                  onChange={(valueString) => handleDurationChange(parseInt(valueString) || 1)}
                >
                  <NumberInputField />
                  <NumberInputStepper>
                    <NumberIncrementStepper />
                    <NumberDecrementStepper />
                  </NumberInputStepper>
                </NumberInput>
                <FormHelperText>
                  Укажите количество часов бронирования
                </FormHelperText>
                {errors.duration && (
                  <FormHelperText color="red.500">{errors.duration}</FormHelperText>
                )}
              </FormControl>
            )}

            {/* Сумма к оплате */}
            <FormControl>
              <FormLabel>Сумма к оплате</FormLabel>
              <HStack>
                <Input
                  value={`${calculatedAmount.toFixed(2)} ₽`}
                  isReadOnly
                  bg="gray.50"
                  fontWeight="bold"
                />
                {/* Кнопка "Пересчитать" не показываем для тарифов "3 часа", "Тестовый день", "Опенспейс на день" */}
                {selectedTariff &&
                 !selectedTariff.name.toLowerCase().includes('3 час') &&
                 !selectedTariff.name.toLowerCase().includes('тестовый день') &&
                 !selectedTariff.name.toLowerCase().includes('опенспейс на день') && (
                  <Button
                    size="sm"
                    onClick={handleRecalculate}
                    isLoading={isCalculating}
                    leftIcon={<FiDollarSign />}
                  >
                    Пересчитать
                  </Button>
                )}
              </HStack>

              {/* Breakdown суммы */}
              {selectedTariff && (
                <Box mt={2} p={2} bg="gray.50" borderRadius="md" fontSize="sm">
                  <VStack align="stretch" spacing={1}>
                    <HStack justify="space-between">
                      <Text>Базовая цена:</Text>
                      <Text>
                        {selectedTariff.price} ₽
                        {((selectedTariff.purpose === 'meeting_room' ||
                           selectedTariff.purpose === 'coworking') &&
                           !selectedTariff.name.toLowerCase().includes('3 час') &&
                           formData.duration > 1)
                          ? ` × ${formData.duration} ч = ${(selectedTariff.price * formData.duration).toFixed(2)} ₽`
                          : ''
                        }
                      </Text>
                    </HStack>
                    {/* Скидку не показываем для тарифов "3 часа", "Тестовый день", "Опенспейс на день" */}
                    {getDiscountPercent() > 0 &&
                     !selectedTariff.name.toLowerCase().includes('3 час') &&
                     !selectedTariff.name.toLowerCase().includes('тестовый день') &&
                     !selectedTariff.name.toLowerCase().includes('опенспейс на день') && (
                      <HStack justify="space-between" color="green.500">
                        <Text>Скидка ({getDiscountPercent()}%):</Text>
                        <Text>
                          -{((selectedTariff.price * formData.duration * getDiscountPercent()) / 100).toFixed(2)} ₽
                        </Text>
                      </HStack>
                    )}
                    <Divider />
                    <HStack justify="space-between" fontWeight="bold">
                      <Text>Итого:</Text>
                      <Text>{calculatedAmount.toFixed(2)} ₽</Text>
                    </HStack>
                  </VStack>
                </Box>
              )}
            </FormControl>

            {/* Статусы */}
            <FormControl>
              <FormLabel>Статус бронирования</FormLabel>
              <VStack align="stretch" spacing={2}>
                <Checkbox
                  isChecked={formData.confirmed}
                  onChange={(e) => handleFieldChange('confirmed', e.target.checked)}
                >
                  Подтверждено
                </Checkbox>
                <Checkbox
                  isChecked={formData.paid}
                  onChange={(e) => handleFieldChange('paid', e.target.checked)}
                >
                  Оплачено
                </Checkbox>
              </VStack>
            </FormControl>
          </VStack>
        </ModalBody>

        <ModalFooter>
          <HStack spacing={3} width="100%">
            <Button
              leftIcon={<FiX />}
              variant="outline"
              onClick={handleCancel}
              isDisabled={isSaving}
            >
              Отмена
            </Button>

            {/* Кнопка "Без оплаты" для всех тарифов */}
            {selectedTariff && (
              <Button
                leftIcon={<FiSave />}
                colorScheme="purple"
                variant="outline"
                onClick={handleSaveWithoutPayment}
                isLoading={isSaving}
                loadingText="Создание..."
              >
                Без оплаты
              </Button>
            )}

            <Button
              leftIcon={<FiSave />}
              colorScheme="green"
              onClick={handleSave}
              isLoading={isSaving}
              loadingText="Сохранение..."
              ml="auto"
            >
              Создать бронирование
            </Button>
          </HStack>
        </ModalFooter>
      </ModalContent>
    </Modal>
  );
};

export default CreateBookingModal;
