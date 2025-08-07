// components/DetailModal.jsx
import React from 'react';
import {
  Modal, ModalOverlay, ModalContent, ModalHeader, ModalBody, ModalFooter,
  ModalCloseButton, Button, VStack, HStack, Text, Box, Icon, Badge
} from '@chakra-ui/react';
import {
  FiUser, FiPhone, FiMail, FiInfo, FiCalendar, FiShoppingBag, FiUsers,
  FiClock, FiTag, FiDollarSign, FiCheck, FiImage, FiMessageCircle, FiPercent
} from 'react-icons/fi';
import { styles, getStatusColor } from '../styles/styles';

const DetailModal = ({ isOpen, onClose, selectedItem }) => {
  if (!selectedItem) return null;

  const renderUserDetails = () => (
    <VStack align="stretch" spacing={4}>
      <HStack>
        <Icon as={FiUser} />
        <Text fontWeight="bold">Полное имя:</Text>
        <Text>{selectedItem.full_name || 'Не указано'}</Text>
      </HStack>
      <HStack>
        <Icon as={FiPhone} />
        <Text fontWeight="bold">Телефон:</Text>
        <Text>{selectedItem.phone || 'Не указано'}</Text>
      </HStack>
      <HStack>
        <Icon as={FiMail} />
        <Text fontWeight="bold">Email:</Text>
        <Text>{selectedItem.email || 'Не указано'}</Text>
      </HStack>
      <HStack>
        <Icon as={FiInfo} />
        <Text fontWeight="bold">Telegram ID:</Text>
        <Text>{selectedItem.telegram_id}</Text>
      </HStack>
      <HStack>
        <Icon as={FiCalendar} />
        <Text fontWeight="bold">Дата регистрации:</Text>
        <Text>{new Date(selectedItem.reg_date || selectedItem.first_join_time).toLocaleDateString('ru-RU')}</Text>
      </HStack>
      <HStack>
        <Icon as={FiShoppingBag} />
        <Text fontWeight="bold">Успешных бронирований:</Text>
        <Text>{selectedItem.successful_bookings}</Text>
      </HStack>
      <HStack>
        <Icon as={FiUsers} />
        <Text fontWeight="bold">Приглашено пользователей:</Text>
        <Text>{selectedItem.invited_count}</Text>
      </HStack>
    </VStack>
  );

  const renderBookingDetails = () => (
    <VStack align="stretch" spacing={4}>
      <HStack>
        <Icon as={FiCalendar} />
        <Text fontWeight="bold">Дата визита:</Text>
        <Text>{new Date(selectedItem.visit_date).toLocaleDateString('ru-RU')}</Text>
      </HStack>
      <HStack>
        <Icon as={FiClock} />
        <Text fontWeight="bold">Время:</Text>
        <Text>{selectedItem.visit_time || 'Весь день'}</Text>
      </HStack>
      <HStack>
        <Icon as={FiTag} />
        <Text fontWeight="bold">Тариф ID:</Text>
        <Text>{selectedItem.tariff_id}</Text>
      </HStack>
      <HStack>
        <Icon as={FiDollarSign} />
        <Text fontWeight="bold">Сумма:</Text>
        <Text>{selectedItem.amount} ₽</Text>
      </HStack>
      <HStack>
        <Icon as={FiCheck} />
        <Text fontWeight="bold">Оплачено:</Text>
        <Badge colorScheme={getStatusColor(selectedItem.paid ? 'paid' : 'unpaid')}>
          {selectedItem.paid ? 'Да' : 'Нет'}
        </Badge>
      </HStack>
      <HStack>
        <Icon as={FiCheck} />
        <Text fontWeight="bold">Подтверждено:</Text>
        <Badge colorScheme={getStatusColor(selectedItem.confirmed ? 'confirmed' : 'pending')}>
          {selectedItem.confirmed ? 'Да' : 'Ожидает'}
        </Badge>
      </HStack>
      {selectedItem.duration && (
        <HStack>
          <Icon as={FiClock} />
          <Text fontWeight="bold">Длительность:</Text>
          <Text>{selectedItem.duration} час(ов)</Text>
        </HStack>
      )}
    </VStack>
  );

  const renderTicketDetails = () => (
    <VStack align="stretch" spacing={4}>
      <Box>
        <HStack mb={2}>
          <Icon as={FiInfo} />
          <Text fontWeight="bold">Описание:</Text>
        </HStack>
        <Text pl={6}>{selectedItem.description}</Text>
      </Box>
      <HStack>
        <Icon as={FiUser} />
        <Text fontWeight="bold">Пользователь ID:</Text>
        <Text>{selectedItem.user_id}</Text>
      </HStack>
      <HStack>
        <Icon as={FiCheck} />
        <Text fontWeight="bold">Статус:</Text>
        <Badge colorScheme={getStatusColor(selectedItem.status)}>
          {selectedItem.status === 'OPEN' ? 'Открыта' :
           selectedItem.status === 'IN_PROGRESS' ? 'В работе' : 'Закрыта'}
        </Badge>
      </HStack>
      <HStack>
        <Icon as={FiCalendar} />
        <Text fontWeight="bold">Создана:</Text>
        <Text>{new Date(selectedItem.created_at).toLocaleString('ru-RU')}</Text>
      </HStack>
      {selectedItem.photo_id && (
        <HStack>
          <Icon as={FiImage} />
          <Text fontWeight="bold">Фото прикреплено:</Text>
          <Badge colorScheme="blue">Да</Badge>
        </HStack>
      )}
      {selectedItem.comment && (
        <Box>
          <HStack mb={2}>
            <Icon as={FiMessageCircle} />
            <Text fontWeight="bold">Комментарий:</Text>
          </HStack>
          <Text pl={6}>{selectedItem.comment}</Text>
        </Box>
      )}
    </VStack>
  );

  const renderTariffDetails = () => (
    <VStack align="stretch" spacing={4}>
      <HStack>
        <Icon as={FiTag} />
        <Text fontWeight="bold">Название:</Text>
        <Text>{selectedItem.name}</Text>
      </HStack>
      <Box>
        <HStack mb={2}>
          <Icon as={FiInfo} />
          <Text fontWeight="bold">Описание:</Text>
        </HStack>
        <Text pl={6}>{selectedItem.description}</Text>
      </Box>
      <HStack>
        <Icon as={FiDollarSign} />
        <Text fontWeight="bold">Цена:</Text>
        <Text>{selectedItem.price} ₽</Text>
      </HStack>
      <HStack>
        <Icon as={FiCheck} />
        <Text fontWeight="bold">Активен:</Text>
        <Badge colorScheme={getStatusColor(selectedItem.is_active ? 'active' : 'inactive')}>
          {selectedItem.is_active ? 'Да' : 'Нет'}
        </Badge>
      </HStack>
      {selectedItem.purpose && (
        <HStack>
          <Icon as={FiInfo} />
          <Text fontWeight="bold">Назначение:</Text>
          <Text>{selectedItem.purpose}</Text>
        </HStack>
      )}
    </VStack>
  );

  const renderPromocodeDetails = () => (
    <VStack align="stretch" spacing={4}>
      <HStack>
        <Icon as={FiPercent} />
        <Text fontWeight="bold">Название:</Text>
        <Text>{selectedItem.name}</Text>
      </HStack>
      <HStack>
        <Icon as={FiPercent} />
        <Text fontWeight="bold">Скидка:</Text>
        <Text>{selectedItem.discount}%</Text>
      </HStack>
      <HStack>
        <Icon as={FiUsers} />
        <Text fontWeight="bold">Использовано раз:</Text>
        <Text>{selectedItem.usage_quantity}</Text>
      </HStack>
      <HStack>
        <Icon as={FiCheck} />
        <Text fontWeight="bold">Активен:</Text>
        <Badge colorScheme={getStatusColor(selectedItem.is_active ? 'active' : 'inactive')}>
          {selectedItem.is_active ? 'Да' : 'Нет'}
        </Badge>
      </HStack>
      {selectedItem.expiration_date && (
        <HStack>
          <Icon as={FiCalendar} />
          <Text fontWeight="bold">Срок действия до:</Text>
          <Text>{new Date(selectedItem.expiration_date).toLocaleDateString('ru-RU')}</Text>
        </HStack>
      )}
    </VStack>
  );

  const renderContent = () => {
    switch (selectedItem.type) {
      case 'user':
        return renderUserDetails();
      case 'booking':
        return renderBookingDetails();
      case 'ticket':
        return renderTicketDetails();
      case 'tariff':
        return renderTariffDetails();
      case 'promocode':
        return renderPromocodeDetails();
      default:
        return null;
    }
  };

  const getModalTitle = () => {
    const titles = {
      'user': 'Информация о пользователе',
      'booking': 'Информация о бронировании',
      'ticket': 'Информация о заявке',
      'tariff': 'Информация о тарифе',
      'promocode': 'Информация о промокоде'
    };
    return titles[selectedItem.type] || 'Детали';
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} size={styles.modal.size}>
      <ModalOverlay />
      <ModalContent borderRadius={styles.modal.borderRadius}>
        <ModalHeader>{getModalTitle()}</ModalHeader>
        <ModalCloseButton />
        <ModalBody pb={6}>
          {renderContent()}
        </ModalBody>
        <ModalFooter>
          <Button colorScheme="purple" onClick={onClose}>
            Закрыть
          </Button>
        </ModalFooter>
      </ModalContent>
    </Modal>
  );
};

export default DetailModal;