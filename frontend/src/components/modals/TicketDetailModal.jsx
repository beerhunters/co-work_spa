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
  Button,
  Image,
  Box
} from '@chakra-ui/react';
import { getStatusColor } from '../../styles/styles';

const TicketDetailModal = ({ isOpen, onClose, ticket }) => {
  const getStatusLabel = (status) => {
    const statusLabels = {
      'OPEN': 'Открыта',
      'IN_PROGRESS': 'В работе',
      'CLOSED': 'Закрыта'
    };
    return statusLabels[status] || status;
  };

  if (!ticket) return null;

  return (
    <Modal isOpen={isOpen} onClose={onClose} size="xl">
      <ModalOverlay />
      <ModalContent>
        <ModalHeader>Тикет #{ticket.id}</ModalHeader>
        <ModalCloseButton />
        <ModalBody>
          <VStack spacing={3} align="stretch">
            <HStack justify="space-between">
              <Text fontWeight="bold">ID пользователя:</Text>
              <Text>{ticket.user_id}</Text>
            </HStack>

            <VStack align="stretch" spacing={2}>
              <Text fontWeight="bold">Описание:</Text>
              <Box p={3} bg="gray.50" borderRadius="md" borderLeft="4px solid" borderLeftColor="blue.400">
                <Text>{ticket.description}</Text>
              </Box>
            </VStack>

            {ticket.photo_id && (
              <VStack align="stretch" spacing={2}>
                <Text fontWeight="bold">Прикреплённое фото:</Text>
                <Box>
                  <Image
                    src={`https://api.telegram.org/file/bot${process.env.BOT_TOKEN}/${ticket.photo_id}`}
                    alt="Фото к тикету"
                    maxHeight="200px"
                    objectFit="cover"
                    borderRadius="md"
                    fallback={
                      <Box
                        height="100px"
                        bg="gray.100"
                        display="flex"
                        alignItems="center"
                        justifyContent="center"
                        borderRadius="md"
                      >
                        <Text color="gray.500">Изображение недоступно</Text>
                      </Box>
                    }
                  />
                </Box>
              </VStack>
            )}

            <HStack justify="space-between">
              <Text fontWeight="bold">Статус:</Text>
              <Badge colorScheme={getStatusColor(ticket.status)}>
                {getStatusLabel(ticket.status)}
              </Badge>
            </HStack>

            {ticket.comment && (
              <VStack align="stretch" spacing={2}>
                <Text fontWeight="bold">Комментарий администратора:</Text>
                <Box p={3} bg="yellow.50" borderRadius="md" borderLeft="4px solid" borderLeftColor="yellow.400">
                  <Text>{ticket.comment}</Text>
                </Box>
              </VStack>
            )}

            <HStack justify="space-between">
              <Text fontWeight="bold">Создан:</Text>
              <Text>{new Date(ticket.created_at).toLocaleString('ru-RU')}</Text>
            </HStack>

            <HStack justify="space-between">
              <Text fontWeight="bold">Обновлён:</Text>
              <Text>{new Date(ticket.updated_at).toLocaleString('ru-RU')}</Text>
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

export default TicketDetailModal;