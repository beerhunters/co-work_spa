// sections/Bookings.jsx
import React from 'react';
import { Box, Card, CardHeader, CardBody, Heading, VStack, HStack, Text, Icon, Badge } from '@chakra-ui/react';
import { FiEye } from 'react-icons/fi';
import { sizes, styles, getStatusColor } from '../styles/styles';

const Bookings = ({ bookings, openDetailModal }) => {
  return (
    <Box p={sizes.content.padding} bg="gray.50" minH={sizes.content.minHeight}>
      <Card borderRadius={styles.card.borderRadius} boxShadow={styles.card.boxShadow}>
        <CardHeader>
          <Heading size="md">Бронирования</Heading>
        </CardHeader>
        <CardBody>
          <VStack align="stretch" spacing={2}>
            {bookings.map(booking => (
              <Box
                key={booking.id}
                p={styles.listItem.padding}
                borderRadius={styles.listItem.borderRadius}
                border={styles.listItem.border}
                borderColor={styles.listItem.borderColor}
                bg={styles.listItem.bg}
                cursor={styles.listItem.cursor}
                _hover={styles.listItem.hover}
                transition={styles.listItem.transition}
                onClick={() => openDetailModal(booking, 'booking')}
              >
                <HStack justify="space-between">
                  <VStack align="start" spacing={1}>
                    <Text fontWeight="bold">
                      {new Date(booking.visit_date).toLocaleDateString('ru-RU')}
                    </Text>
                    <HStack spacing={4}>
                      <Badge colorScheme={getStatusColor(booking.paid ? 'paid' : 'unpaid')}>
                        {booking.paid ? 'Оплачено' : 'Не оплачено'}
                      </Badge>
                      <Badge colorScheme={getStatusColor(booking.confirmed ? 'confirmed' : 'pending')}>
                        {booking.confirmed ? 'Подтверждено' : 'Ожидает'}
                      </Badge>
                      <Text fontSize="sm" color="gray.600">
                        {booking.amount} ₽
                      </Text>
                    </HStack>
                  </VStack>
                  <Icon as={FiEye} color="purple.500" />
                </HStack>
              </Box>
            ))}
          </VStack>
        </CardBody>
      </Card>
    </Box>
  );
};

export default Bookings;