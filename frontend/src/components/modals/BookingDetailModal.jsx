import React from 'react';
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
  Button
} from '@chakra-ui/react';
import { getStatusColor } from '../../styles/styles';

const BookingDetailModal = ({ isOpen, onClose, booking }) => {
  if (!booking) return null;

  return (
    <Modal isOpen={isOpen} onClose={onClose} size="xl">
      <ModalOverlay />
      <ModalContent>
        <ModalHeader>Бронирование #{booking.id}</ModalHeader>
        <ModalCloseButton />
        <ModalBody>
          <VStack spacing={3} align="stretch">
            <HStack justify="space-between">
              <Text fontWeight="bold">ID пользователя:</Text>
              <Text>{booking.user_id}</Text>
            </HStack>

            <HStack justify="space-between">
              <Text fontWeight="bold">Тариф ID:</Text>
              <Text>{booking.tariff_id}</Text>
            </HStack>

            <HStack justify="space-between">
              <Text fontWeight="bold">Дата визита:</Text>
              <Text>{new Date(booking.visit_date).toLocaleDateString('ru-RU')}</Text>
            </HStack>

            {booking.visit_time && (
              <HStack justify="space-between">
                <Text fontWeight="bold">Время визита:</Text>
                <Text>{booking.visit_time}</Text>
              </HStack>
            )}

            {booking.duration && (
              <HStack justify="space-between">
                <Text fontWeight="bold">Длительность:</Text>
                <Text>{booking.duration} час(ов)</Text>
              </HStack>
            )}

            <HStack justify="space-between">
              <Text fontWeight="bold">Сумма:</Text>
              <Text fontWeight="bold" color="green.500">₽{booking.amount}</Text>
            </HStack>

            {booking.promocode_id && (
              <HStack justify="space-between">
                <Text fontWeight="bold">Промокод ID:</Text>
                <Text>{booking.promocode_id}</Text>
              </HStack>
            )}

            <HStack justify="space-between">
              <Text fontWeight="bold">Статус оплаты:</Text>
              <Badge colorScheme={getStatusColor(booking.paid ? 'paid' : 'unpaid')}>
                {booking.paid ? 'Оплачено' : 'Не оплачено'}
              </Badge>
            </HStack>

            <HStack justify="space-between">
              <Text fontWeight="bold">Подтверждение:</Text>
              <Badge colorScheme={getStatusColor(booking.confirmed ? 'confirmed' : 'pending')}>
                {booking.confirmed ? 'Подтверждено' : 'Ожидает'}
              </Badge>
            </HStack>

            {booking.payment_id && (
              <HStack justify="space-between">
                <Text fontWeight="bold">ID платежа:</Text>
                <Text fontSize="sm">{booking.payment_id}</Text>
              </HStack>
            )}

            {booking.rubitime_id && (
              <HStack justify="space-between">
                <Text fontWeight="bold">Rubitime ID:</Text>
                <Text fontSize="sm">{booking.rubitime_id}</Text>
              </HStack>
            )}

            <HStack justify="space-between">
              <Text fontWeight="bold">Создано:</Text>
              <Text>{new Date(booking.created_at).toLocaleString('ru-RU')}</Text>
            </HStack>
          </VStack>
        </ModalBody>

        <ModalFooter>
          <Button colorScheme="blue" onClick={onClose}>
            Закрыть
          </Button>
        </ModalFooter>
      </ModalContent>
    </Modal>
  );
};

export default BookingDetailModal;