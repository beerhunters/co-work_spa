// sections/Notifications.jsx
import React from 'react';
import { Box, Card, CardHeader, CardBody, Heading, VStack, HStack, Text, Badge } from '@chakra-ui/react';
import { sizes, styles, colors, getStatusColor } from '../styles/styles';

const Notifications = ({ notifications }) => {
  return (
    <Box p={sizes.content.padding} bg="gray.50" minH={sizes.content.minHeight}>
      <Card borderRadius={styles.card.borderRadius} boxShadow={styles.card.boxShadow}>
        <CardHeader>
          <Heading size="md">Уведомления</Heading>
        </CardHeader>
        <CardBody>
          <VStack align="stretch" spacing={2}>
            {notifications.map(notification => (
              <Box
                key={notification.id}
                p={styles.listItem.padding}
                borderRadius={styles.listItem.borderRadius}
                border={styles.listItem.border}
                borderColor={styles.listItem.borderColor}
                bg={notification.is_read ? colors.notification.readBg : colors.notification.unreadBg}
                transition={styles.listItem.transition}
              >
                <VStack align="start" spacing={2}>
                  <Text>{notification.message}</Text>
                  <HStack spacing={4}>
                    <Badge colorScheme={getStatusColor(notification.is_read ? 'read' : 'unread')}>
                      {notification.is_read ? 'Прочитано' : 'Новое'}
                    </Badge>
                    <Text fontSize="sm" color="gray.600">
                      {new Date(notification.created_at).toLocaleString('ru-RU')}
                    </Text>
                  </HStack>
                </VStack>
              </Box>
            ))}
          </VStack>
        </CardBody>
      </Card>
    </Box>
  );
};

export default Notifications;