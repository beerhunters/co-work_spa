import React, { useState, useMemo } from 'react';
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
  Alert,
  AlertIcon,
  AlertDescription,
  Divider,
  SimpleGrid,
  Stat,
  StatLabel,
  StatNumber,
  StatHelpText,
  Spinner,
  Flex
} from '@chakra-ui/react';
import { FiEye, FiPlus, FiSave, FiX, FiTag, FiCheckCircle, FiXCircle, FiCreditCard } from 'react-icons/fi';
import { sizes, styles, getStatusColor, colors, spacing, typography } from '../styles/styles';
import { tariffApi } from '../utils/api';
import { ListSkeleton } from '../components/LoadingSkeletons';

const CreateTariffModal = ({ isOpen, onClose, onUpdate }) => {
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    price: 0,
    purpose: 'coworking',
    service_id: null,
    is_active: true,
    color: '#3182CE'
  });
  const [isLoading, setIsLoading] = useState(false);
  const [errors, setErrors] = useState({});
  const toast = useToast();

  const resetForm = () => {
    setFormData({
      name: '',
      description: '',
      price: 0,
      purpose: 'coworking',
      service_id: null,
      is_active: true,
      color: '#3182CE'
    });
    setErrors({});
  };

  const validateForm = () => {
    const newErrors = {};

    if (!formData.name.trim()) {
      newErrors.name = 'Название тарифа обязательно';
    } else if (formData.name.length < 3) {
      newErrors.name = 'Название должно содержать минимум 3 символа';
    } else if (formData.name.length > 64) {
      newErrors.name = 'Название не должно превышать 64 символа';
    }

    if (!formData.description.trim()) {
      newErrors.description = 'Описание тарифа обязательно';
    } else if (formData.description.length > 255) {
      newErrors.description = 'Описание не должно превышать 255 символов';
    }

    if (formData.price < 0) {
      newErrors.price = 'Цена не может быть отрицательной';
    }

    if (formData.service_id && formData.service_id < 1) {
      newErrors.service_id = 'Service ID должен быть положительным числом';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async () => {
    if (!validateForm()) {
      return;
    }

    setIsLoading(true);
    try {
      const submitData = {
        ...formData,
        service_id: formData.service_id || null
      };

      await tariffApi.create(submitData);

      toast({
        title: 'Успешно',
        description: 'Тариф создан',
        status: 'success',
        duration: 3000,
        isClosable: true,
      });

      await onUpdate();
      resetForm();
      onClose();
    } catch (error) {
      console.error('Ошибка при создании тарифа:', error);

      let errorMessage = 'Не удалось создать тариф';
      if (error.response?.data?.detail) {
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
      setIsLoading(false);
    }
  };

  const handleClose = () => {
    resetForm();
    onClose();
  };

  return (
    <Modal isOpen={isOpen} onClose={handleClose} size="lg">
      <ModalOverlay />
      <ModalContent>
        <ModalHeader>
          <HStack>
            <FiPlus />
            <Text>Создание тарифа</Text>
          </HStack>
        </ModalHeader>
        <ModalCloseButton />

        <ModalBody>
          <VStack align="stretch" spacing={4}>
            <Alert status="info" borderRadius="md">
              <AlertIcon />
              <AlertDescription>
                Создайте новый тариф для предоставления услуг пользователям.
              </AlertDescription>
            </Alert>

            <FormControl isInvalid={errors.name}>
              <FormLabel>Название тарифа</FormLabel>
              <Input
                value={formData.name}
                onChange={(e) => setFormData({...formData, name: e.target.value})}
                placeholder="Например: Рабочее место на день"
                maxLength={64}
              />
              <FormHelperText>
                {errors.name || 'Краткое и понятное название тарифа'}
              </FormHelperText>
            </FormControl>

            <FormControl isInvalid={errors.description}>
              <FormLabel>Описание</FormLabel>
              <Textarea
                value={formData.description}
                onChange={(e) => setFormData({...formData, description: e.target.value})}
                placeholder="Подробное описание того, что включает тариф..."
                rows={3}
                maxLength={255}
                resize="vertical"
              />
              <FormHelperText>
                {errors.description || `${formData.description.length}/255 символов`}
              </FormHelperText>
            </FormControl>

            <HStack spacing={4}>
              <FormControl isInvalid={errors.price}>
                <FormLabel>Цена (₽)</FormLabel>
                <NumberInput
                  value={formData.price}
                  onChange={(valueString, valueNumber) =>
                    setFormData({...formData, price: valueNumber || 0})}
                  min={0}
                  step={50}
                >
                  <NumberInputField />
                  <NumberInputStepper>
                    <NumberIncrementStepper />
                    <NumberDecrementStepper />
                  </NumberInputStepper>
                </NumberInput>
                <FormHelperText>
                  {errors.price || 'Стоимость в рублях'}
                </FormHelperText>
              </FormControl>

              <FormControl>
                <FormLabel>Назначение</FormLabel>
                <Select
                  value={formData.purpose}
                  onChange={(e) => setFormData({...formData, purpose: e.target.value})}
                >
                  <option value="coworking">Опенспейс</option>
                  <option value="meeting_room">Переговорная</option>
                </Select>
                <FormHelperText>
                  Тип предоставляемой услуги
                </FormHelperText>
              </FormControl>
            </HStack>

            <FormControl isInvalid={errors.service_id}>
              <FormLabel>Service ID (необязательно)</FormLabel>
              <NumberInput
                value={formData.service_id || ''}
                onChange={(valueString, valueNumber) =>
                  setFormData({...formData, service_id: valueNumber || null})}
                min={1}
              >
                <NumberInputField />
                <NumberInputStepper>
                  <NumberIncrementStepper />
                  <NumberDecrementStepper />
                </NumberInputStepper>
              </NumberInput>
              <FormHelperText>
                {errors.service_id || 'ID услуги в внешней системе (например, Rubitime)'}
              </FormHelperText>
            </FormControl>

            <FormControl>
              <FormLabel>Цвет тарифа</FormLabel>
              <HStack spacing={3}>
                <Input
                  type="color"
                  value={formData.color}
                  onChange={(e) => setFormData({...formData, color: e.target.value})}
                  w="80px"
                  h="40px"
                  cursor="pointer"
                />
                <Box
                  w="40px"
                  h="40px"
                  bg={formData.color}
                  borderRadius="md"
                  border="2px solid"
                  borderColor="gray.200"
                />
                <VStack align="start" spacing={0} flex={1}>
                  <Text fontSize="sm" fontWeight="medium">{formData.color.toUpperCase()}</Text>
                  <Text fontSize="xs" color="gray.600">
                    Цвет отображается в календаре бронирований
                  </Text>
                </VStack>
              </HStack>
            </FormControl>

            <FormControl>
              <HStack justify="space-between">
                <VStack align="start" spacing={0}>
                  <FormLabel mb={0}>Активный тариф</FormLabel>
                  <Text fontSize="sm" color="gray.600">
                    {formData.is_active ? 'Тариф будет доступен для выбора' : 'Тариф будет скрыт от пользователей'}
                  </Text>
                </VStack>
                <Switch
                  isChecked={formData.is_active}
                  onChange={(e) => setFormData({...formData, is_active: e.target.checked})}
                  colorScheme="green"
                  size="lg"
                />
              </HStack>
            </FormControl>
          </VStack>
        </ModalBody>

        <ModalFooter>
          <HStack spacing={3}>
            <Button
              leftIcon={<FiX />}
              variant="outline"
              onClick={handleClose}
              isDisabled={isLoading}
            >
              Отмена
            </Button>
            <Button
              leftIcon={<FiSave />}
              colorScheme="blue"
              onClick={handleSubmit}
              isLoading={isLoading}
              loadingText="Создание..."
            >
              Создать тариф
            </Button>
          </HStack>
        </ModalFooter>
      </ModalContent>
    </Modal>
  );
};

const Tariffs = ({ tariffs, openDetailModal, onUpdate, isLoading = false }) => {
  const { isOpen, onOpen, onClose } = useDisclosure();

  const getPurposeLabel = (purpose) => {
    const labels = {
      'coworking': 'Опенспейс',
      'meeting_room': 'Переговорная'
    };
    return labels[purpose] || purpose;
  };

  const stats = useMemo(() => {
    return {
      total: tariffs.length,
      active: tariffs.filter(t => t.is_active).length,
      inactive: tariffs.filter(t => !t.is_active).length,
      coworking: tariffs.filter(t => t.purpose === 'coworking').length,
      meetingRooms: tariffs.filter(t => t.purpose === 'meeting_room').length,
      avgPrice: tariffs.length > 0 ? Math.round(tariffs.reduce((sum, t) => sum + t.price, 0) / tariffs.length) : 0
    };
  }, [tariffs]);

  if (isLoading && tariffs.length === 0) {
    return (
      <Box p={6} bg="gray.50" minH={sizes.content.minHeight}>
        <Flex justify="center" align="center" h="400px" direction="column" gap={4}>
          <Spinner size="xl" color="purple.500" thickness="4px" />
          <Text color="gray.500">Загрузка тарифов...</Text>
        </Flex>
      </Box>
    );
  }

  return (
    <>
      <Box p={6} bg="gray.50" minH={sizes.content.minHeight}>
        <VStack align="stretch" spacing={6}>
          {/* Header */}
          <Box>
            <Heading size="lg" mb={2}>
              <Icon as={FiTag} color="purple.500" mr={3} />
              Тарифы
            </Heading>
            <Text color="gray.600">
              Управление тарифами и ценообразованием услуг
            </Text>
          </Box>

          {/* Statistics Cards */}
          <SimpleGrid columns={{ base: 1, md: 2, lg: 5 }} spacing={4}>
            <Card>
              <CardBody>
                <Stat>
                  <StatLabel>Всего тарифов</StatLabel>
                  <StatNumber>{stats.total}</StatNumber>
                  <StatHelpText>
                    <Icon as={FiTag} mr={1} />
                    Общее количество
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
                    Доступны для выбора
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
                    Скрыты от пользователей
                  </StatHelpText>
                </Stat>
              </CardBody>
            </Card>

            <Card>
              <CardBody>
                <Stat>
                  <StatLabel>Опенспейс</StatLabel>
                  <StatNumber color="blue.500">{stats.coworking}</StatNumber>
                  <StatHelpText>
                    <Icon as={FiTag} mr={1} />
                    Коворкинг
                  </StatHelpText>
                </Stat>
              </CardBody>
            </Card>

            <Card>
              <CardBody>
                <Stat>
                  <StatLabel>Средняя цена</StatLabel>
                  <StatNumber color="purple.500">{stats.avgPrice} ₽</StatNumber>
                  <StatHelpText>
                    <Icon as={FiCreditCard} mr={1} />
                    По всем тарифам
                  </StatHelpText>
                </Stat>
              </CardBody>
            </Card>
          </SimpleGrid>

          <Divider />

          {/* Tariffs Card */}
          <Card bg={colors.background.card} borderRadius={styles.card.borderRadius} boxShadow="lg">
            <CardHeader>
              <HStack justify="flex-end">
                <Button
                  leftIcon={<FiPlus />}
                  colorScheme="blue"
                  onClick={onOpen}
                  size="sm"
                >
                  Добавить тариф
                </Button>
              </HStack>
            </CardHeader>
            <CardBody>
              <VStack align="stretch" spacing={2}>
                {isLoading ? (
                  <ListSkeleton items={5} />
                ) : tariffs.length === 0 ? (
                  <Flex direction="column" align="center" justify="center" py={12} gap={4}>
                    <Icon as={FiTag} boxSize={16} color="gray.300" />
                    <VStack spacing={2}>
                      <Text fontSize="lg" fontWeight="medium" color="gray.600">
                        Тарифов пока нет
                      </Text>
                      <Text fontSize="sm" color="gray.500">
                        Создайте первый тариф для предоставления услуг
                      </Text>
                    </VStack>
                    <Button
                      leftIcon={<FiPlus />}
                      colorScheme="blue"
                      variant="outline"
                      onClick={onOpen}
                      mt={2}
                    >
                      Создать первый тариф
                    </Button>
                  </Flex>
                ) : (
                  tariffs.map(tariff => (
                    <Box
                      key={tariff.id}
                      p={styles.listItem.padding}
                      borderRadius={styles.listItem.borderRadius}
                      border={styles.listItem.border}
                      borderColor={styles.listItem.borderColor}
                      bg={styles.listItem.bg}
                      cursor={styles.listItem.cursor}
                      _hover={styles.listItem.hover}
                      transition={styles.listItem.transition}
                      onClick={() => openDetailModal(tariff, 'tariff')}
                    >
                      <HStack justify="space-between">
                        <VStack align="start" spacing={1}>
                          <HStack spacing={3}>
                            <Text fontWeight="bold" fontSize="lg">{tariff.name}</Text>
                            <Badge colorScheme={getStatusColor(tariff.is_active ? 'active' : 'inactive')}>
                              {tariff.is_active ? 'Активен' : 'Неактивен'}
                            </Badge>
                          </HStack>
                          <HStack spacing={4} fontSize="sm" color="gray.600">
                            <Text>Цена: <strong>{tariff.price} ₽</strong></Text>
                            <Text>Тип: <strong>{getPurposeLabel(tariff.purpose)}</strong></Text>
                            {tariff.service_id && (
                              <Text>Service ID: <strong>{tariff.service_id}</strong></Text>
                            )}
                          </HStack>
                          <Text fontSize="sm" color="gray.500" noOfLines={1}>
                            {tariff.description}
                          </Text>
                        </VStack>
                        <Icon as={FiEye} color="purple.500" />
                      </HStack>
                    </Box>
                  ))
                )}
              </VStack>
            </CardBody>
          </Card>
        </VStack>
      </Box>

      <CreateTariffModal
        isOpen={isOpen}
        onClose={onClose}
        onUpdate={onUpdate}
      />
    </>
  );
};

export default Tariffs;