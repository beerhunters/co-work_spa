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
  Badge,
  ModalFooter,
  Button,
  Input,
  NumberInput,
  NumberInputField,
  NumberInputStepper,
  NumberIncrementStepper,
  NumberDecrementStepper,
  Switch,
  FormControl,
  FormLabel,
  FormHelperText,
  useToast,
  Alert,
  AlertIcon,
  AlertDescription,
  Divider,
  AlertDialog,
  AlertDialogBody,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogContent,
  AlertDialogOverlay,
  useDisclosure
} from '@chakra-ui/react';
import { FiEdit, FiSave, FiX, FiTrash2 } from 'react-icons/fi';
import { getStatusColor } from '../../styles/styles';
import { formatLocalDate } from '../../utils/dateUtils';
import { promocodeApi } from '../../utils/api';

const PromocodeDetailModal = ({ isOpen, onClose, promocode, onUpdate }) => {
  const [isEditing, setIsEditing] = useState(false);
  const [formData, setFormData] = useState({
    name: '',
    discount: 0,
    usage_quantity: 0,
    expiration_date: '',
    is_active: true
  });
  const [isLoading, setIsLoading] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [errors, setErrors] = useState({});
  const { isOpen: deleteDialogOpen, onOpen: openDeleteDialog, onClose: closeDeleteDialog } = useDisclosure();
  const toast = useToast();
  const cancelRef = React.useRef();

  useEffect(() => {
    if (promocode) {
      setFormData({
        name: promocode.name || '',
        discount: promocode.discount || 0,
        usage_quantity: promocode.usage_quantity || 0,
        expiration_date: promocode.expiration_date
          ? formatLocalDate(new Date(promocode.expiration_date))
          : '',
        is_active: promocode.is_active ?? true
      });
    }
    setErrors({});
    setIsEditing(false);
  }, [promocode, isOpen]);

  if (!promocode) return null;

  const isExpired = promocode.expiration_date && new Date(promocode.expiration_date) < new Date();

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

  const handleSave = async () => {
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

      await promocodeApi.update(promocode.id, submitData);

      toast({
        title: 'Успешно',
        description: 'Промокод обновлен',
        status: 'success',
        duration: 3000,
        isClosable: true,
      });

      // Обновляем данные промокода
      Object.assign(promocode, submitData);

      setIsEditing(false);
      await onUpdate();

    } catch (error) {
      console.error('Ошибка при обновлении промокода:', error);

      let errorMessage = 'Не удалось обновить промокод';
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

  const handleCancel = () => {
    setFormData({
      name: promocode.name || '',
      discount: promocode.discount || 0,
      usage_quantity: promocode.usage_quantity || 0,
      expiration_date: promocode.expiration_date
        ? formatLocalDate(new Date(promocode.expiration_date))
        : '',
      is_active: promocode.is_active ?? true
    });
    setErrors({});
    setIsEditing(false);
  };

  const handleDelete = async () => {
    setIsDeleting(true);
    try {
      await promocodeApi.delete(promocode.id);
      toast({
        title: 'Успешно',
        description: `Промокод "${promocode.name}" удален`,
        status: 'success',
        duration: 3000,
        isClosable: true,
      });
      await onUpdate();
      onClose();
    } catch (error) {
      console.error('Ошибка при удалении промокода:', error);

      let errorMessage = 'Не удалось удалить промокод';
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
      setIsDeleting(false);
      closeDeleteDialog();
    }
  };

  const formatDate = (dateString) => {
    if (!dateString) return 'Бессрочный';
    try {
      return new Date(dateString).toLocaleDateString('ru-RU');
    } catch {
      return 'Некорректная дата';
    }
  };

  return (
    <>
      <Modal isOpen={isOpen} onClose={onClose} size="xl">
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>
            <HStack justify="space-between">
              <Text>Промокод #{promocode.id}</Text>
            </HStack>
          </ModalHeader>
          <ModalCloseButton />

          <ModalBody>
            {isEditing ? (
              <VStack spacing={4} align="stretch">
                <Alert status="info">
                  <AlertIcon />
                  <AlertDescription>
                    Редактирование промокода. Будьте осторожны при изменении активных промокодов.
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
                    {errors.usage_quantity || 'Если 0 - промокод будет недоступен. Показывает оставшиеся использования'}
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
                        {formData.is_active ? 'Промокод доступен для использования' : 'Промокод отключен'}
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
            ) : (
              <VStack spacing={3} align="stretch">
                <HStack justify="space-between">
                  <Text fontWeight="bold">Название:</Text>
                  <Text fontSize="lg" fontWeight="semibold" fontFamily="mono">
                    {promocode.name}
                  </Text>
                </HStack>

                <HStack justify="space-between">
                  <Text fontWeight="bold">Скидка:</Text>
                  <Text fontSize="lg" fontWeight="bold" color="green.500">
                    {promocode.discount}%
                  </Text>
                </HStack>

                <HStack justify="space-between">
                  <Text fontWeight="bold">Оставшиеся использования:</Text>
                  <VStack align="end" spacing={1}>
                    <Badge colorScheme={promocode.usage_quantity > 0 ? "green" : "red"} fontSize="sm">
                      {promocode.usage_quantity || 0}
                    </Badge>
                    {promocode.usage_quantity === 0 && (
                      <Text fontSize="xs" color="red.500">
                        Исчерпан
                      </Text>
                    )}
                  </VStack>
                </HStack>

                <HStack justify="space-between">
                  <Text fontWeight="bold">Срок действия:</Text>
                  <VStack align="end" spacing={1}>
                    <Text fontSize="sm">
                      {formatDate(promocode.expiration_date)}
                    </Text>
                    {isExpired && (
                      <Badge colorScheme="red" fontSize="xs">
                        Истёк
                      </Badge>
                    )}
                  </VStack>
                </HStack>

                <HStack justify="space-between">
                  <Text fontWeight="bold">Статус:</Text>
                  <Badge colorScheme={getStatusColor(promocode.is_active ? 'active' : 'inactive')}>
                    {promocode.is_active ? 'Активный' : 'Неактивный'}
                  </Badge>
                </HStack>

                {/* Предупреждения */}
                {!promocode.is_active && (
                  <Text fontSize="sm" color="gray.500" fontStyle="italic">
                    Промокод отключён администратором
                  </Text>
                )}

                {isExpired && promocode.is_active && (
                  <Text fontSize="sm" color="red.500" fontStyle="italic">
                    Промокод истёк по сроку действия
                  </Text>
                )}

                {promocode.usage_quantity === 0 && promocode.is_active && !isExpired && (
                  <Text fontSize="sm" color="orange.500" fontStyle="italic">
                    Промокод исчерпан - использования закончились
                  </Text>
                )}
              </VStack>
            )}
          </ModalBody>

          <ModalFooter>
            {isEditing ? (
              <HStack spacing={3}>
                <Button
                  leftIcon={<FiX />}
                  variant="outline"
                  onClick={handleCancel}
                  isDisabled={isLoading}
                >
                  Отмена
                </Button>
                <Button
                  leftIcon={<FiSave />}
                  colorScheme="blue"
                  onClick={handleSave}
                  isLoading={isLoading}
                  loadingText="Сохранение..."
                >
                  Сохранить
                </Button>
              </HStack>
            ) : (
              <HStack spacing={3}>
                <Button
                  leftIcon={<FiTrash2 />}
                  colorScheme="red"
                  variant="outline"
                  onClick={openDeleteDialog}
                >
                  Удалить
                </Button>
                <Button
                  leftIcon={<FiEdit />}
                  colorScheme="blue"
                  onClick={() => setIsEditing(true)}
                >
                  Редактировать
                </Button>
                <Button onClick={onClose}>
                  Закрыть
                </Button>
              </HStack>
            )}
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
              Удалить промокод
            </AlertDialogHeader>

            <AlertDialogBody>
              Вы уверены, что хотите удалить промокод <strong>"{promocode.name}"</strong>?
              <br />
              <br />
              <Text fontSize="sm" color="gray.600">
                Это действие нельзя отменить. Промокод имеет {promocode.usage_quantity || 0} оставшихся использований.
              </Text>
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

export default PromocodeDetailModal;