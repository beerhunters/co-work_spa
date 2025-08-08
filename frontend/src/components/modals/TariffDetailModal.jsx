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
  Box
} from '@chakra-ui/react';
import { getStatusColor } from '../../styles/styles';

const TariffDetailModal = ({ isOpen, onClose, tariff }) => {
  if (!tariff) return null;

  return (
    <Modal isOpen={isOpen} onClose={onClose} size="xl">
      <ModalOverlay />
      <ModalContent>
        <ModalHeader>Тариф #{tariff.id}</ModalHeader>
        <ModalCloseButton />
        <ModalBody>
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

            {tariff.purpose && (
              <HStack justify="space-between">
                <Text fontWeight="bold">Назначение:</Text>
                <Badge colorScheme="blue">{tariff.purpose}</Badge>
              </HStack>
            )}

            {tariff.service_id && (
              <HStack justify="space-between">
                <Text fontWeight="bold">Service ID:</Text>
                <Text>{tariff.service_id}</Text>
              </HStack>
            )}

            <HStack justify="space-between">
              <Text fontWeight="bold">Статус:</Text>
              <Badge colorScheme={getStatusColor(tariff.is_active ? 'active' : 'inactive')}>
                {tariff.is_active ? 'Активный' : 'Неактивный'}
              </Badge>
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

export default TariffDetailModal;