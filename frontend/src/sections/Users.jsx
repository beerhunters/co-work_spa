// sections/Users.jsx
import React from 'react';
import { Box, Card, CardHeader, CardBody, Heading, VStack, HStack, Text, Icon, Badge } from '@chakra-ui/react';
import { FiEye, FiPhone, FiMail } from 'react-icons/fi';
import { sizes, styles } from '../styles/styles';

const Users = ({ users, openDetailModal }) => {
  return (
    <Box p={sizes.content.padding} bg="gray.50" minH={sizes.content.minHeight}>
      <Card borderRadius={styles.card.borderRadius} boxShadow={styles.card.boxShadow}>
        <CardHeader>
          <Heading size="md">Список пользователей</Heading>
        </CardHeader>
        <CardBody>
          <VStack align="stretch" spacing={2}>
            {users.map(user => (
              <Box
                key={user.id}
                p={styles.listItem.padding}
                borderRadius={styles.listItem.borderRadius}
                border={styles.listItem.border}
                borderColor={styles.listItem.borderColor}
                bg={styles.listItem.bg}
                cursor={styles.listItem.cursor}
                _hover={styles.listItem.hover}
                transition={styles.listItem.transition}
                onClick={() => openDetailModal(user, 'user')}
              >
                <HStack justify="space-between">
                  <VStack align="start" spacing={1}>
                    <Text fontWeight="bold">{user.full_name || 'Без имени'}</Text>
                    <HStack spacing={4}>
                      <Text fontSize="sm" color="gray.600">
                        <Icon as={FiPhone} mr={1} />
                        {user.phone || 'Не указан'}
                      </Text>
                      <Text fontSize="sm" color="gray.600">
                        <Icon as={FiMail} mr={1} />
                        {user.email || 'Не указан'}
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

export default Users;