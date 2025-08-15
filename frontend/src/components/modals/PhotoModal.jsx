import React from 'react';
import {
  Modal,
  ModalOverlay,
  ModalContent,
  ModalBody,
  ModalCloseButton,
  Image,
  Box,
  useColorModeValue
} from '@chakra-ui/react';

const PhotoModal = ({ isOpen, onClose, photoUrl, ticketId }) => {
  const bgColor = useColorModeValue('white', 'gray.800');

  return (
    <Modal isOpen={isOpen} onClose={onClose} size="full" isCentered>
      <ModalOverlay bg="blackAlpha.800" />
      <ModalContent bg="transparent" boxShadow="none" m={4}>
        <ModalCloseButton
          zIndex={2}
          top={2}
          right={2}
          bg="blackAlpha.600"
          color="white"
          _hover={{ bg: "blackAlpha.800" }}
          size="lg"
        />

        <ModalBody p={0} display="flex" alignItems="center" justifyContent="center" minH="100vh">
          <Box
            maxH="95vh"
            maxW="95vw"
            display="flex"
            alignItems="center"
            justifyContent="center"
          >
            <Image
              src={photoUrl}
              alt={`Фото к тикету #${ticketId}`}
              maxH="95vh"
              maxW="95vw"
              objectFit="contain"
              userSelect="none"
              bg={bgColor}
              borderRadius="md"
              boxShadow="2xl"
            />
          </Box>
        </ModalBody>
      </ModalContent>
    </Modal>
  );
};

export default PhotoModal;