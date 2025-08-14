import React from 'react';
import {
  Modal,
  ModalOverlay,
  ModalContent,
  ModalBody,
  ModalCloseButton,
  Image,
  Box,
  Text,
  HStack,
  Button,
  useColorModeValue
} from '@chakra-ui/react';
import { FiDownload, FiMaximize2 } from 'react-icons/fi';

const PhotoModal = ({ isOpen, onClose, photoUrl, ticketId }) => {
  const bgColor = useColorModeValue('white', 'gray.800');

  const handleDownload = () => {
    if (!photoUrl) return;

    // Создаем ссылку для скачивания
    const link = document.createElement('a');
    link.href = photoUrl;
    link.download = `ticket_${ticketId}_photo.jpg`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const handleOpenInNewTab = () => {
    if (photoUrl) {
      window.open(photoUrl, '_blank');
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} size="6xl" isCentered>
      <ModalOverlay bg="blackAlpha.800" />
      <ModalContent bg={bgColor} maxH="90vh" maxW="90vw">
        <ModalCloseButton zIndex={2} />

        {/* Заголовок с кнопками */}
        <Box p={4} borderBottom="1px solid" borderColor="gray.200">
          <HStack justify="space-between" align="center">
            <Text fontSize="lg" fontWeight="semibold">
              Фото к тикету #{ticketId}
            </Text>
            <HStack spacing={2}>
              <Button
                size="sm"
                leftIcon={<FiMaximize2 />}
                variant="outline"
                onClick={handleOpenInNewTab}
              >
                Открыть в новой вкладке
              </Button>
              <Button
                size="sm"
                leftIcon={<FiDownload />}
                colorScheme="blue"
                variant="outline"
                onClick={handleDownload}
              >
                Скачать
              </Button>
            </HStack>
          </HStack>
        </Box>

        <ModalBody p={0} display="flex" alignItems="center" justifyContent="center">
          <Box maxH="calc(90vh - 100px)" maxW="100%" overflow="hidden">
            <Image
              src={photoUrl}
              alt={`Фото к тикету #${ticketId}`}
              maxH="100%"
              maxW="100%"
              objectFit="contain"
              userSelect="none"
            />
          </Box>
        </ModalBody>
      </ModalContent>
    </Modal>
  );
};

export default PhotoModal;