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

const PromocodeDetailModal = ({ isOpen, onClose, promocode }) => {
  if (!promocode) return null;

  const isExpired = promocode.expiration_date && new Date(promocode.expiration_date) < new Date();

  return (
    <Modal isOpen={isOpen} onClose={onClose} size="xl">
      <ModalOverlay />
      <ModalContent>
        <ModalHeader>Промокод #{promocode.id}</ModalHeader>
        <ModalCloseButton />
        <ModalBody>
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
              <Text fontWeight="bold">Использований:</Text>
              <Badge colorScheme="blue" fontSize="sm">
                {promocode.usage_quantity}
              </Badge>
            </HStack>

            {promocode.expiration_date && (
              <HStack justify="space-between">
                <Text fontWeight="bold">Срок действия:</Text>
                <VStack align="end" spacing={1}>
                  <Text fontSize="sm">
                    {new Date(promocode.expiration_date).toLocaleDateString('ru-RU')}
                  </Text>
                  {isExpired && (
                    <Badge colorScheme="red" fontSize="xs">
                      Истёк
                    </Badge>
                  )}
                </VStack>
              </HStack>
            )}

            <HStack justify="space-between">
              <Text fontWeight="bold">Статус:</Text>
              <Badge colorScheme={getStatusColor(promocode.is_active ? 'active' : 'inactive')}>
                {promocode.is_active ? 'Активный' : 'Неактивный'}
              </Badge>
            </HStack>

            {/* Дополнительная информация о статусе */}
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

export default PromocodeDetailModal;