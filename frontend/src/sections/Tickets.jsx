// sections/Tickets.jsx
import React from 'react';
import { Box, Card, CardHeader, CardBody, Heading, VStack, HStack, Text, Icon, Badge } from '@chakra-ui/react';
import { FiEye } from 'react-icons/fi';
import { sizes, styles, getStatusColor } from '../styles/styles';

const Tickets = ({ tickets, openDetailModal }) => {
  const getStatusLabel = (status) => {
    const labels = {
      'OPEN': 'Открыта',
      'IN_PROGRESS': 'В работе',
      'CLOSED': 'Закрыта'
    };
    return labels[status] || status;
  };

  return (
    <Box p={sizes.content.padding} bg="gray.50" minH={sizes.content.minHeight}>
      <Card borderRadius={styles.card.borderRadius} boxShadow={styles.card.boxShadow}>
        <CardHeader>
          <Heading size="md">Заявки</Heading>
        </CardHeader>
        <CardBody>
          <VStack align="stretch" spacing={2}>
            {tickets.map(ticket => (
              <Box
                key={ticket.id}
                p={styles.listItem.padding}
                borderRadius={styles.listItem.borderRadius}
                border={styles.listItem.border}
                borderColor={styles.listItem.borderColor}
                bg={styles.listItem.bg}
                cursor={styles.listItem.cursor}
                _hover={styles.listItem.hover}
                transition={styles.listItem.transition}
                onClick={() => openDetailModal(ticket, 'ticket')}
              >
                <HStack justify="space-between">
                  <VStack align="start" spacing={1}>
                    <Text fontWeight="bold" noOfLines={1}>
                      {ticket.description}
                    </Text>
                    <HStack spacing={4}>
                      <Badge colorScheme={getStatusColor(ticket.status)}>
                        {getStatusLabel(ticket.status)}
                      </Badge>
                      <Text fontSize="sm" color="gray.600">
                        {new Date(ticket.created_at).toLocaleDateString('ru-RU')}
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

export default Tickets;