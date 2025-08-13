import React, { useState } from 'react';
import {
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalBody,
  ModalFooter,
  Button,
  Text,
  VStack,
  HStack,
  Icon,
  useColorModeValue,
  Alert,
  AlertIcon,
  Box
} from '@chakra-ui/react';
import { FiBell, FiVolume2 } from 'react-icons/fi';
import notificationManager from '../utils/notifications';

const NotificationPermissionModal = ({ isOpen, onClose, onPermissionGranted }) => {
  const [isLoading, setIsLoading] = useState(false);
  const [permissionDenied, setPermissionDenied] = useState(false);

  const handleRequestPermission = async () => {
    setIsLoading(true);
    setPermissionDenied(false);

    try {
      const granted = await notificationManager.requestPermission();

      if (granted) {
        onPermissionGranted?.();
        onClose();
      } else {
        setPermissionDenied(true);
      }
    } catch (error) {
      console.error('Ошибка при запросе разрешения:', error);
      setPermissionDenied(true);
    } finally {
      setIsLoading(false);
    }
  };

  const handleTestSound = () => {
    notificationManager.playSound('success');
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} isCentered size="md">
      <ModalOverlay />
      <ModalContent>
        <ModalHeader>
          <HStack>
            <Icon as={FiBell} color="purple.500" />
            <Text>Включить уведомления</Text>
          </HStack>
        </ModalHeader>

        <ModalBody>
          <VStack spacing={4} align="stretch">
            <Text>
              Разрешите уведомления, чтобы получать важные сообщения о новых
              бронированиях, обращениях и пользователях даже когда вкладка неактивна.
            </Text>

            <Box p={4} bg={useColorModeValue('gray.50', 'gray.700')} rounded="md">
              <VStack spacing={3}>
                <Text fontSize="sm" fontWeight="bold">Что вы получите:</Text>
                <VStack spacing={2} align="start" fontSize="sm">
                  <Text>🎫 Уведомления о новых обращениях</Text>
                  <Text>📅 Сообщения о бронированиях</Text>
                  <Text>👤 Информация о новых пользователях</Text>
                  <Text>🔊 Звуковые сигналы для важных событий</Text>
                </VStack>
              </VStack>
            </Box>

            {permissionDenied && (
              <Alert status="warning" rounded="md">
                <AlertIcon />
                <VStack align="start" spacing={1}>
                  <Text fontSize="sm" fontWeight="bold">
                    Разрешение отклонено
                  </Text>
                  <Text fontSize="xs">
                    Вы можете включить уведомления в настройках браузера:
                    нажмите на иконку замка в адресной строке.
                  </Text>
                </VStack>
              </Alert>
            )}

            <HStack justify="center">
              <Button
                size="sm"
                variant="outline"
                leftIcon={<FiVolume2 />}
                onClick={handleTestSound}
              >
                Тест звука
              </Button>
            </HStack>
          </VStack>
        </ModalBody>

        <ModalFooter>
          <HStack>
            <Button variant="ghost" onClick={onClose}>
              Не сейчас
            </Button>
            <Button
              colorScheme="purple"
              isLoading={isLoading}
              loadingText="Запрос..."
              onClick={handleRequestPermission}
            >
              Разрешить уведомления
            </Button>
          </HStack>
        </ModalFooter>
      </ModalContent>
    </Modal>
  );
};

export default NotificationPermissionModal;