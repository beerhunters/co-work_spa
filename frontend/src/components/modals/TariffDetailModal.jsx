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
  Box,
  Input,
  NumberInput,
  NumberInputField,
  NumberInputStepper,
  NumberIncrementStepper,
  NumberDecrementStepper,
  Textarea,
  Switch,
  Select,
  FormControl,
  FormLabel,
  FormHelperText,
  useToast,
  Alert,
  AlertIcon,
  AlertDescription,
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
import { tariffApi } from '../../utils/api';

const TariffDetailModal = ({ isOpen, onClose, tariff, onUpdate }) => {
  const [isEditing, setIsEditing] = useState(false);
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
  const [isDeleting, setIsDeleting] = useState(false);
  const [errors, setErrors] = useState({});
  const { isOpen: deleteDialogOpen, onOpen: openDeleteDialog, onClose: closeDeleteDialog } = useDisclosure();
  const toast = useToast();
  const cancelRef = React.useRef();

  useEffect(() => {
    if (tariff) {
      setFormData({
        name: tariff.name || '',
        description: tariff.description || '',
        price: tariff.price || 0,
        purpose: tariff.purpose || 'coworking',
        service_id: tariff.service_id || null,
        is_active: tariff.is_active ?? true,
        color: tariff.color || '#3182CE'
      });
    }
    setErrors({});
    setIsEditing(false);
  }, [tariff, isOpen]);

  if (!tariff) return null;

  const getPurposeLabel = (purpose) => {
    const labels = {
      'coworking': 'Опенспейс',
      'meeting_room': 'Переговорная'
    };
    return labels[purpose] || purpose;
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

  const handleSave = async () => {
    if (!validateForm()) {
      return;
    }

    setIsLoading(true);
    try {
      const submitData = {
        ...formData,
        service_id: formData.service_id || null
      };

      await tariffApi.update(tariff.id, submitData);

      toast({
        title: 'Успешно',
        description: 'Тариф обновлен',
        status: 'success',
        duration: 3000,
        isClosable: true,
      });

      // Обновляем данные тарифа
      Object.assign(tariff, submitData);

      setIsEditing(false);
      await onUpdate();

    } catch (error) {
      console.error('Ошибка при обновлении тарифа:', error);

      let errorMessage = 'Не удалось обновить тариф';
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

  const handleCancel = () => {
    setFormData({
      name: tariff.name || '',
      description: tariff.description || '',
      price: tariff.price || 0,
      purpose: tariff.purpose || 'coworking',
      service_id: tariff.service_id || null,
      is_active: tariff.is_active ?? true,
      color: tariff.color || '#3182CE'
    });
    setErrors({});
    setIsEditing(false);
  };

  const handleDelete = async () => {
    setIsDeleting(true);
    try {
      await tariffApi.delete(tariff.id);
      toast({
        title: 'Успешно',
        description: `Тариф "${tariff.name}" удален`,
        status: 'success',
        duration: 3000,
        isClosable: true,
      });
      await onUpdate();
      onClose();
    } catch (error) {
      console.error('Ошибка при удалении тарифа:', error);

      let errorMessage = 'Не удалось удалить тариф';
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

  return (
    <>
      <Modal isOpen={isOpen} onClose={onClose} size="xl">
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>
            <HStack justify="space-between">
              <Text>Тариф #{tariff.id}</Text>
            </HStack>
          </ModalHeader>
          <ModalCloseButton />

          <ModalBody>
            {isEditing ? (
              <VStack spacing={4} align="stretch">
                <Alert status="info">
                  <AlertIcon />
                  <AlertDescription>
                    Редактирование тарифа. Изменения повлияют на доступность для пользователей.
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
                        {formData.is_active ? 'Тариф доступен для выбора' : 'Тариф скрыт от пользователей'}
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
                  <Text fontSize="lg" fontWeight="semibold">{tariff.name}</Text>
                </HStack>

                <VStack align="stretch" spacing={2}>
                  <Text fontWeight="bold">Описание:</Text>
                  <Box p={3} bg="gray.50" borderRadius="md" borderLeft="4px solid" borderLeftColor="purple.400">
                    <Text>{tariff.description}</Text>
                  </Box>
                </VStack>

                <HStack justify="space-between">
                  <Text fontWeight="bold">Цена:</Text>
                  <Text fontSize="lg" fontWeight="bold" color="green.500">₽{tariff.price}</Text>
                </HStack>

                <HStack justify="space-between">
                  <Text fontWeight="bold">Назначение:</Text>
                  <Badge colorScheme="blue">{getPurposeLabel(tariff.purpose)}</Badge>
                </HStack>

                {tariff.service_id && (
                  <HStack justify="space-between">
                    <Text fontWeight="bold">Service ID:</Text>
                    <Text fontFamily="mono">{tariff.service_id}</Text>
                  </HStack>
                )}

                <HStack justify="space-between">
                  <Text fontWeight="bold">Статус:</Text>
                  <Badge colorScheme={getStatusColor(tariff.is_active ? 'active' : 'inactive')}>
                    {tariff.is_active ? 'Активный' : 'Неактивный'}
                  </Badge>
                </HStack>

                <Box>
                  <Text fontWeight="bold" mb={2}>Цвет тарифа:</Text>
                  <HStack spacing={3}>
                    <Box
                      w="40px"
                      h="40px"
                      bg={tariff.color || '#3182CE'}
                      borderRadius="md"
                      border="2px solid"
                      borderColor="gray.200"
                    />
                    <Text fontSize="sm" fontWeight="medium">
                      {(tariff.color || '#3182CE').toUpperCase()}
                    </Text>
                  </HStack>
                </Box>

                {/* Информационные сообщения */}
                {!tariff.is_active && (
                  <Text fontSize="sm" color="gray.500" fontStyle="italic">
                    Тариф отключен и недоступен для пользователей
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
              Удалить тариф
            </AlertDialogHeader>

            <AlertDialogBody>
              Вы уверены, что хотите удалить тариф <strong>"{tariff.name}"</strong>?
              <br />
              <br />
              <Text fontSize="sm" color="gray.600">
                Это действие нельзя отменить. Все связанные бронирования останутся, но пользователи не смогут выбрать этот тариф.
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

export default TariffDetailModal;