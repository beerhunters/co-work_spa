import React, { useState } from 'react';
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
  Switch,
  FormHelperText,
  useToast,
  Alert,
  AlertIcon,
  AlertDescription
} from '@chakra-ui/react';
import { FiEye, FiPlus, FiSave, FiX } from 'react-icons/fi';
import { sizes, styles, getStatusColor } from '../styles/styles';
import { promocodeApi } from '../utils/api';

const CreatePromocodeModal = ({ isOpen, onClose, onUpdate }) => {
  const [formData, setFormData] = useState({
    name: '',
    discount: 10,
    usage_quantity: 100, // По умолчанию 100 использований
    expiration_date: '',
    is_active: true
  });
  const [isLoading, setIsLoading] = useState(false);
  const [errors, setErrors] = useState({});
  const toast = useToast();

  const resetForm = () => {
    setFormData({
      name: '',
      discount: 10,
      usage_quantity: 100, // По умолчанию 100 использований
      expiration_date: '',
      is_active: true
    });
    setErrors({});
  };

  const validateForm = () => {
    const newErrors = {};

    if (!formData.name.trim()) {
      newErrors.name = 'Название промокода обязательно';
    } else if (formData.name.length < 3) {
      newErrors.name = 'Название должно содержать минимум 3 символа';
    } else if (formData.name.length > 20) {
      newErrors.name = 'Название не должно превышать 20 символов';
    } else if (!/^[A-Za-z0-9_-]+$/.test(formData.name)) {
      newErrors.name = 'Название может содержать только буквы, цифры, дефис и подчеркивание';
    }

    if (formData.discount < 1 || formData.discount > 100) {
      newErrors.discount = 'Скидка должна быть от 1% до 100%';
    }

    if (formData.usage_quantity < 0) {
      newErrors.usage_quantity = 'Количество использований не может быть отрицательным';
    }

    if (formData.expiration_date) {
      const expirationDate = new Date(formData.expiration_date);
      const today = new Date();
      today.setHours(0, 0, 0, 0);

      if (expirationDate < today) {
        newErrors.expiration_date = 'Дата истечения не может быть в прошлом';
      }
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
        name: formData.name.toUpperCase(),
        expiration_date: formData.expiration_date || null
      };

      await promocodeApi.create(submitData);

      toast({
        title: 'Успешно',
        description: 'Промокод создан',
        status: 'success',
        duration: 3000,
        isClosable: true,
      });

      await onUpdate();
      resetForm();
      onClose();
    } catch (error) {
      console.error('Ошибка при создании промокода:', error);

      let errorMessage = 'Не удалось создать промокод';
      if (error.response?.data?.detail) {
        if (error.response.data.detail.includes('UNIQUE constraint failed')) {
          errorMessage = 'Промокод с таким названием уже существует';
        } else {
          errorMessage = error.response.data.detail;
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
            <Text>Создание промокода</Text>
          </HStack>
        </ModalHeader>
        <ModalCloseButton />

        <ModalBody>
          <VStack align="stretch" spacing={4}>
            <Alert status="info" borderRadius="md">
              <AlertIcon />
              <AlertDescription>
                Создайте новый промокод для предоставления скидок пользователям.
              </AlertDescription>
            </Alert>

            <FormControl isInvalid={errors.name}>
              <FormLabel>Название промокода</FormLabel>
              <Input
                value={formData.name}
                onChange={(e) => setFormData({...formData, name: e.target.value.toUpperCase()})}
                placeholder="Например: WINTER2025"
                maxLength={20}
              />
              <FormHelperText>
                {errors.name || 'Только латинские буквы, цифры, дефис и подчеркивание'}
              </FormHelperText>
            </FormControl>

            <FormControl isInvalid={errors.discount}>
              <FormLabel>Размер скидки (%)</FormLabel>
              <NumberInput
                value={formData.discount}
                onChange={(valueString, valueNumber) =>
                  setFormData({...formData, discount: valueNumber || 0})}
                min={1}
                max={100}
              >
                <NumberInputField />
                <NumberInputStepper>
                  <NumberIncrementStepper />
                  <NumberDecrementStepper />
                </NumberInputStepper>
              </NumberInput>
              <FormHelperText>
                {errors.discount || 'От 1% до 100%'}
              </FormHelperText>
            </FormControl>

            <FormControl isInvalid={errors.usage_quantity}>
              <FormLabel>Количество использований</FormLabel>
              <NumberInput
                value={formData.usage_quantity}
                onChange={(valueString, valueNumber) =>
                  setFormData({...formData, usage_quantity: valueNumber || 0})}
                min={0}
              >
                <NumberInputField />
                <NumberInputStepper>
                  <NumberIncrementStepper />
                  <NumberDecrementStepper />
                </NumberInputStepper>
              </NumberInput>
              <FormHelperText>
                {errors.usage_quantity || 'Если 0 - промокод будет недоступен сразу после создания'}
              </FormHelperText>
            </FormControl>

            <FormControl isInvalid={errors.expiration_date}>
              <FormLabel>Дата истечения (необязательно)</FormLabel>
              <Input
                type="date"
                value={formData.expiration_date}
                onChange={(e) => setFormData({...formData, expiration_date: e.target.value})}
              />
              <FormHelperText>
                {errors.expiration_date || 'Оставьте пустым для бессрочного промокода'}
              </FormHelperText>
            </FormControl>

            <FormControl>
              <HStack justify="space-between">
                <VStack align="start" spacing={0}>
                  <FormLabel mb={0}>Активный промокод</FormLabel>
                  <Text fontSize="sm" color="gray.600">
                    {formData.is_active ? 'Промокод будет доступен для использования' : 'Промокод будет отключен'}
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
              Создать промокод
            </Button>
          </HStack>
        </ModalFooter>
      </ModalContent>
    </Modal>
  );
};

const Promocodes = ({ promocodes, openDetailModal, onUpdate }) => {
  const { isOpen, onOpen, onClose } = useDisclosure();

  const formatDate = (dateString) => {
    if (!dateString) return 'Бессрочный';
    try {
      return new Date(dateString).toLocaleDateString('ru-RU');
    } catch {
      return 'Некорректная дата';
    }
  };

  const isExpired = (dateString) => {
    if (!dateString) return false;
    try {
      return new Date(dateString) < new Date();
    } catch {
      return false;
    }
  };

  return (
    <>
      <Box p={sizes.content.padding} bg="gray.50" minH={sizes.content.minHeight}>
        <Card borderRadius={styles.card.borderRadius} boxShadow={styles.card.boxShadow}>
          <CardHeader>
            <HStack justify="space-between">
              <Heading size="md">Промокоды</Heading>
              <Button
                leftIcon={<FiPlus />}
                colorScheme="blue"
                onClick={onOpen}
                size="sm"
              >
                Добавить промокод
              </Button>
            </HStack>
          </CardHeader>
          <CardBody>
            <VStack align="stretch" spacing={2}>
              {promocodes.length === 0 ? (
                <Box textAlign="center" py={8}>
                  <Text color="gray.500" mb={4}>Промокодов пока нет</Text>
                  <Button
                    leftIcon={<FiPlus />}
                    colorScheme="blue"
                    variant="outline"
                    onClick={onOpen}
                  >
                    Создать первый промокод
                  </Button>
                </Box>
              ) : (
                promocodes.map(promocode => {
                  const expired = isExpired(promocode.expiration_date);
                  const isActive = promocode.is_active && !expired && promocode.usage_quantity > 0;

                  return (
                    <Box
                      key={promocode.id}
                      p={styles.listItem.padding}
                      borderRadius={styles.listItem.borderRadius}
                      border={styles.listItem.border}
                      borderColor={styles.listItem.borderColor}
                      bg={styles.listItem.bg}
                      cursor={styles.listItem.cursor}
                      _hover={styles.listItem.hover}
                      transition={styles.listItem.transition}
                      onClick={() => openDetailModal(promocode, 'promocode')}
                    >
                      <HStack justify="space-between">
                        <VStack align="start" spacing={1}>
                          <HStack spacing={3}>
                            <Text fontWeight="bold" fontSize="lg">{promocode.name}</Text>
                            <Badge colorScheme={getStatusColor(isActive ? 'active' : 'inactive')}>
                              {isActive ? 'Активен' : expired ? 'Истёк' : promocode.usage_quantity === 0 ? 'Исчерпан' : 'Неактивен'}
                            </Badge>
                          </HStack>
                          <HStack spacing={4} fontSize="sm" color="gray.600">
                            <Text>Скидка: <strong>{promocode.discount}%</strong></Text>
                            <Text>Использований: <strong>{promocode.usage_quantity || 0}</strong></Text>
                            <Text>Срок: <strong>{formatDate(promocode.expiration_date)}</strong></Text>
                          </HStack>
                        </VStack>
                        <Icon as={FiEye} color="purple.500" />
                      </HStack>
                    </Box>
                  );
                })
              )}
            </VStack>
          </CardBody>
        </Card>
      </Box>

      <CreatePromocodeModal
        isOpen={isOpen}
        onClose={onClose}
        onUpdate={onUpdate}
      />
    </>
  );
};

export default Promocodes;