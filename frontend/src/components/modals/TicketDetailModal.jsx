import React, { useState, useEffect } from 'react';
import {
  Modal as ChakraModal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalBody,
  ModalCloseButton,
  VStack,
  HStack,
  Text,
  Badge,
  Button,
  Textarea,
  Select,
  Input,
  useToast,
  Divider,
  Box,
  Image,
  FormControl,
  FormLabel,
  Grid,
  GridItem,
  Card,
  CardBody,
  Alert,
  AlertIcon,
  AlertDescription
} from '@chakra-ui/react';
import { FiEdit, FiSave, FiX, FiImage, FiUser, FiClock } from 'react-icons/fi';
import { getStatusColor } from '../../styles/styles';
import { ticketApi } from '../../utils/api';

const TicketDetailModal = ({ isOpen, onClose, ticket, onUpdate }) => {
  const [isEditing, setIsEditing] = useState(false);
  const [status, setStatus] = useState('');
  const [comment, setComment] = useState('');
  const [responsePhoto, setResponsePhoto] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const toast = useToast();

  useEffect(() => {
    if (ticket) {
      setStatus(ticket.status || 'OPEN');
      setComment(ticket.comment || '');
      setResponsePhoto(null);
    }
  }, [ticket]);

  const getStatusLabel = (status) => {
    const statusLabels = {
      'OPEN': 'Открыта',
      'IN_PROGRESS': 'В работе',
      'CLOSED': 'Закрыта'
    };
    return statusLabels[status] || status;
  };

  const getAvailableStatuses = (currentStatus) => {
    // Если тикет закрыт, возвращаем только "Закрыта"
    if (currentStatus === 'CLOSED') {
      return [{ value: 'CLOSED', label: 'Закрыта' }];
    }

    const transitions = {
      'OPEN': [
        { value: 'OPEN', label: 'Открыта' },
        { value: 'IN_PROGRESS', label: 'В работе' },
        { value: 'CLOSED', label: 'Закрыта' }
      ],
      'IN_PROGRESS': [
        { value: 'IN_PROGRESS', label: 'В работе' },
        { value: 'CLOSED', label: 'Закрыта' }
      ]
    };
    return transitions[currentStatus] || transitions['OPEN'];
  };

  const formatDateTime = (dateString) => {
    try {
      const date = new Date(dateString);
      return date.toLocaleString('ru-RU', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      });
    } catch (error) {
      return 'Неизвестно';
    }
  };

  const handleSave = async () => {
    if (!ticket) return;

    // Валидация: если закрываем тикет, комментарий обязателен
    if (status === 'CLOSED' && !comment.trim() && !ticket.comment) {
      toast({
        title: 'Ошибка',
        description: 'При закрытии тикета необходимо оставить комментарий',
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
      return;
    }

    setIsLoading(true);
    try {
      await ticketApi.update(ticket.id, status, comment, responsePhoto);

      // Получаем обновленные данные тикета
      const updatedTicket = await ticketApi.getById(ticket.id);

      // Обновляем состояние формы с новыми данными
      setStatus(updatedTicket.status);
      setComment(updatedTicket.comment || '');
      setResponsePhoto(null);

      // Передаем обновленные данные родительскому компоненту
      if (onUpdate) {
        await onUpdate(updatedTicket);
      }

      toast({
        title: 'Успешно',
        description: 'Тикет обновлен',
        status: 'success',
        duration: 3000,
        isClosable: true,
      });

      setIsEditing(false);

    } catch (error) {
      console.error('Ошибка при обновлении тикета:', error);

      let errorMessage = 'Не удалось обновить тикет';
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
    setStatus(ticket?.status || 'OPEN');
    setComment(ticket?.comment || '');
    setResponsePhoto(null);
    setIsEditing(false);
  };

  const handlePhotoChange = (e) => {
    const file = e.target.files[0];
    if (file) {
      if (file.size > 10 * 1024 * 1024) { // 10MB
        toast({
          title: 'Ошибка',
          description: 'Размер файла не должен превышать 10MB',
          status: 'error',
          duration: 3000,
          isClosable: true,
        });
        return;
      }
      setResponsePhoto(file);
    }
  };

  if (!ticket) return null;

  const availableStatuses = getAvailableStatuses(ticket.status);

  return (
    <ChakraModal isOpen={isOpen} onClose={onClose} size="2xl">
      <ModalOverlay />
      <ModalContent maxH="90vh" overflowY="auto">
        <ModalHeader bg="gray.50" borderTopRadius="md">
          <HStack justify="space-between" align="center">
            <HStack>
              <Text fontSize="xl" fontWeight="bold">Тикет #{ticket.id}</Text>
              <Badge colorScheme={getStatusColor(ticket.status)} fontSize="sm">
                {getStatusLabel(ticket.status)}
              </Badge>
            </HStack>
          </HStack>
        </ModalHeader>
        <ModalCloseButton />

        <ModalBody p={6}>
          <VStack align="stretch" spacing={6}>

            {/* Информация о пользователе */}
            <Card>
              <CardBody>
                <HStack spacing={3} align="start">
                  <FiUser size={20} />
                  <VStack align="start" spacing={1} flex={1}>
                    <Text fontSize="sm" color="gray.500" fontWeight="medium">Отправитель</Text>
                    <Text fontWeight="semibold" fontSize="lg">
                      {ticket.user?.full_name || 'ФИО не указано'}
                    </Text>
                    <HStack spacing={4} fontSize="sm" color="gray.600">
                      <Text>@{ticket.user?.username || 'username не указан'}</Text>
                      {ticket.user?.phone && <Text>{ticket.user.phone}</Text>}
                      {ticket.user?.email && <Text>{ticket.user.email}</Text>}
                    </HStack>
                  </VStack>
                </HStack>
              </CardBody>
            </Card>

            {/* Описание проблемы */}
            <Card>
              <CardBody>
                <VStack align="start" spacing={3}>
                  <Text fontSize="sm" color="gray.500" fontWeight="medium">Описание проблемы</Text>
                  <Text fontSize="md" lineHeight="1.6">{ticket.description}</Text>

                  {/* Прикрепленное фото пользователя */}
                  {ticket.photo_id && (
                    <Box>
                      <Text fontSize="sm" color="gray.500" mb={2} fontWeight="medium">
                        Прикрепленное фото
                      </Text>
                      <Image
                        src={ticketApi.getPhotoUrl(ticket.id)}
                        alt="Прикрепленное фото"
                        maxH="300px"
                        maxW="100%"
                        borderRadius="md"
                        border="1px solid"
                        borderColor="gray.200"
                        objectFit="contain"
                      />
                    </Box>
                  )}
                </VStack>
              </CardBody>
            </Card>

            {/* Временные метки */}
            <Card>
              <CardBody>
                <Grid templateColumns="1fr 1fr" gap={4}>
                  <GridItem>
                    <HStack spacing={2}>
                      <FiClock size={16} />
                      <VStack align="start" spacing={0}>
                        <Text fontSize="sm" color="gray.500" fontWeight="medium">Создан</Text>
                        <Text fontSize="sm">{formatDateTime(ticket.created_at)}</Text>
                      </VStack>
                    </HStack>
                  </GridItem>
                  <GridItem>
                    <HStack spacing={2}>
                      <FiClock size={16} />
                      <VStack align="start" spacing={0}>
                        <Text fontSize="sm" color="gray.500" fontWeight="medium">Обновлен</Text>
                        <Text fontSize="sm">{formatDateTime(ticket.updated_at)}</Text>
                      </VStack>
                    </HStack>
                  </GridItem>
                </Grid>
              </CardBody>
            </Card>

            <Divider />

            {/* Редактирование или просмотр ответа */}
            {isEditing && ticket.status !== 'CLOSED' ? (
              <Card>
                <CardBody>
                  <VStack align="stretch" spacing={4}>
                    <Text fontSize="lg" fontWeight="semibold">Обработка тикета</Text>

                    <FormControl>
                      <FormLabel>Статус</FormLabel>
                      <Select value={status} onChange={(e) => setStatus(e.target.value)}>
                        {availableStatuses.map(statusOption => (
                          <option key={statusOption.value} value={statusOption.value}>
                            {statusOption.label}
                          </option>
                        ))}
                      </Select>
                    </FormControl>

                    {status === 'CLOSED' && !comment.trim() && !ticket.comment && (
                      <Alert status="warning">
                        <AlertIcon />
                        <AlertDescription>
                          При закрытии тикета необходимо оставить комментарий с решением проблемы.
                        </AlertDescription>
                      </Alert>
                    )}

                    <FormControl>
                      <FormLabel>Комментарий/Ответ пользователю</FormLabel>
                      <Textarea
                        value={comment}
                        onChange={(e) => setComment(e.target.value)}
                        placeholder="Опишите действия, предпринятые для решения проблемы, или оставьте ответ пользователю..."
                        rows={4}
                        resize="vertical"
                      />
                    </FormControl>

                    <FormControl>
                      <FormLabel>Прикрепить фото к ответу (необязательно)</FormLabel>
                      <Input
                        type="file"
                        accept="image/*"
                        onChange={handlePhotoChange}
                        pt={1}
                      />
                      {responsePhoto && (
                        <Text fontSize="sm" color="green.500" mt={1}>
                          ✓ Файл выбран: {responsePhoto.name}
                        </Text>
                      )}
                    </FormControl>

                    <HStack spacing={3} pt={2}>
                      <Button
                        leftIcon={<FiSave />}
                        colorScheme="blue"
                        onClick={handleSave}
                        isLoading={isLoading}
                        loadingText="Сохранение..."
                        size="md"
                      >
                        Сохранить изменения
                      </Button>
                      <Button
                        leftIcon={<FiX />}
                        variant="outline"
                        onClick={handleCancel}
                        isDisabled={isLoading}
                        size="md"
                      >
                        Отмена
                      </Button>
                    </HStack>
                  </VStack>
                </CardBody>
              </Card>
            ) : (
              <Card>
                <CardBody>
                  <VStack align="stretch" spacing={4}>
                    <HStack justify="space-between" align="center">
                      <Text fontSize="lg" fontWeight="semibold">Ответ администратора</Text>
                      {ticket.status !== 'CLOSED' && (
                        <Button
                          leftIcon={<FiEdit />}
                          colorScheme="blue"
                          variant="outline"
                          onClick={() => setIsEditing(true)}
                          size="sm"
                        >
                          Редактировать
                        </Button>
                      )}
                      {ticket.status === 'CLOSED' && (
                        <Badge colorScheme="gray" fontSize="xs">
                          Редактирование недоступно
                        </Badge>
                      )}
                    </HStack>

                    {ticket.comment ? (
                      <Box>
                        <Text fontSize="sm" color="gray.500" mb={2} fontWeight="medium">Комментарий</Text>
                        <Text bg="gray.50" p={3} borderRadius="md" lineHeight="1.6">
                          {ticket.comment}
                        </Text>
                      </Box>
                    ) : (
                      <Text color="gray.500" fontStyle="italic">
                        Комментарий не добавлен
                      </Text>
                    )}

                    {ticket.response_photo_id && (
                      <Box>
                        <Text fontSize="sm" color="gray.500" mb={2} fontWeight="medium">
                          Прикрепленное фото в ответе
                        </Text>
                        <Text fontSize="sm" color="green.600">
                          ✓ Фото было отправлено пользователю
                        </Text>
                      </Box>
                    )}
                  </VStack>
                </CardBody>
              </Card>
            )}
          </VStack>
        </ModalBody>
      </ModalContent>
    </ChakraModal>
  );
};

export default TicketDetailModal;