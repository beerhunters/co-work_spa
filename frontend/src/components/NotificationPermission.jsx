import React, { useState, useEffect } from 'react';
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
  Box,
  Badge,
  Code
} from '@chakra-ui/react';
import { FiBell, FiVolume2, FiCheck, FiX } from 'react-icons/fi';
import notificationManager from '../utils/notifications';

const NotificationPermissionModal = ({ isOpen, onClose, onPermissionGranted }) => {
  const [isLoading, setIsLoading] = useState(false);
  const [permissionDenied, setPermissionDenied] = useState(false);
  const [status, setStatus] = useState(null);

  useEffect(() => {
    if (isOpen) {
      const currentStatus = notificationManager.getStatus();
      setStatus(currentStatus);
      console.log('📊 Статус при открытии модального окна:', currentStatus);
    }
  }, [isOpen]);

  const handleRequestPermission = async () => {
    console.log('🔔 Запрос разрешения через модальное окно...');
    setIsLoading(true);
    setPermissionDenied(false);

    try {
      const granted = await notificationManager.requestPermission();
      console.log('📊 Результат запроса разрешения:', granted);

      if (granted) {
        // Сразу тестируем уведомление
        setTimeout(() => {
          notificationManager.showNotification('Уведомления включены! 🎉', {
            body: 'Теперь вы будете получать важные уведомления',
            soundType: 'success',
            autoClose: 5000
          });
        }, 500);

        onPermissionGranted?.();
        onClose();
      } else {
        setPermissionDenied(true);
      }
    } catch (error) {
      console.error('❌ Ошибка при запросе разрешения:', error);
      setPermissionDenied(true);
    } finally {
      setIsLoading(false);
    }
  };

  const handleTestSound = () => {
    console.log('🔊 Тест звука из модального окна');
    notificationManager.playSound('success');
  };

  const handleTestNotification = () => {
    console.log('🔔 Тест уведомления из модального окна');
    notificationManager.showNotification('Тестовое уведомление', {
      body: 'Если вы видите это уведомление, значит все работает правильно!',
      soundType: 'message',
      autoClose: 5000
    });
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

            {/* Диагностическая информация */}
            {status && (
              <Box p={3} bg={useColorModeValue('blue.50', 'blue.900')} rounded="md">
                <Text fontSize="sm" fontWeight="bold" mb={2}>Диагностика:</Text>
                <VStack spacing={1} align="start" fontSize="xs">
                  <HStack>
                    <Icon as={status.isSupported ? FiCheck : FiX} color={status.isSupported ? 'green.500' : 'red.500'} />
                    <Text>Поддержка браузера: {status.isSupported ? 'Да' : 'Нет'}</Text>
                  </HStack>
                  <HStack>
                    <Icon as={status.audioContext ? FiCheck : FiX} color={status.audioContext ? 'green.500' : 'red.500'} />
                    <Text>Аудио контекст: {status.audioContext ? 'Да' : 'Нет'}</Text>
                  </HStack>
                  <HStack>
                    <Badge colorScheme={
                      status.permission === 'granted' ? 'green' :
                      status.permission === 'denied' ? 'red' : 'yellow'
                    }>
                      Разрешение: {status.permission}
                    </Badge>
                  </HStack>
                </VStack>
              </Box>
            )}

            <Box p={4} bg={useColorModeValue('gray.50', 'gray.700')} rounded="md">
              <VStack spacing={3}>
                <Text fontSize="sm" fontWeight="bold">Что вы получите:</Text>
                <VStack spacing={2} align="start" fontSize="sm">
                  <Text>🎫 Уведомления о новых обращениях</Text>
                  <Text>📅 Сообщения о бронированиях</Text>
                  <Text>👤 Информация о новых пользователях</Text>
                  <Text>🔊 Громкие звуковые сигналы</Text>
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
                    Включите уведомления в настройках браузера:
                    нажмите на иконку замка/щита в адресной строке → Уведомления → Разрешить
                  </Text>
                </VStack>
              </Alert>
            )}

            <VStack spacing={2}>
              <HStack spacing={2} w="full">
                <Button
                  size="sm"
                  variant="outline"
                  leftIcon={<Icon as={FiVolume2} boxSize={4} />}  // ← Обернули в Icon
                  onClick={handleTestSound}
                  flex="1"
                >
                  Тест звука
                </Button>
                {status?.permission === 'granted' && (
                  <Button
                    size="sm"
                    variant="outline"
                    leftIcon={<Icon as={FiBell} boxSize={4} />}  // ← Обернули в Icon
                    onClick={handleTestNotification}
                    flex="1"
                  >
                    Тест уведомления
                  </Button>
                )}
              </HStack>

              {status?.permission === 'granted' && (
                <Text fontSize="xs" color="green.500" textAlign="center">
                  ✅ Уведомления уже разрешены! Можете протестировать выше.
                </Text>
              )}
            </VStack>
          </VStack>
        </ModalBody>

        <ModalFooter>
          <HStack>
            <Button variant="ghost" onClick={onClose}>
              {status?.permission === 'granted' ? 'Закрыть' : 'Не сейчас'}
            </Button>
            {status?.permission !== 'granted' && (
              <Button
                colorScheme="purple"
                isLoading={isLoading}
                loadingText="Запрос..."
                onClick={handleRequestPermission}
              >
                Разрешить уведомления
              </Button>
            )}
          </HStack>
        </ModalFooter>
      </ModalContent>
    </Modal>
  );
};

export default NotificationPermissionModal;