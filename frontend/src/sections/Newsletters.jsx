// sections/Newsletters.jsx
import React from 'react';
import { Box, Card, CardHeader, CardBody, Heading, VStack, HStack, Text, Icon } from '@chakra-ui/react';
import { FiUsers } from 'react-icons/fi';
import { sizes, styles } from '../styles/styles';

const Newsletters = ({ newsletters }) => {
  return (
    <Box p={sizes.content.padding} bg="gray.50" minH={sizes.content.minHeight}>
      <Card borderRadius={styles.card.borderRadius} boxShadow={styles.card.boxShadow}>
        <CardHeader>
          <Heading size="md">История рассылок</Heading>
        </CardHeader>
        <CardBody>
          <VStack align="stretch" spacing={2}>
            {newsletters.map(newsletter => (
              <Box
                key={newsletter.id}
                p={styles.listItem.padding}
                borderRadius={styles.listItem.borderRadius}
                border={styles.listItem.border}
                borderColor={styles.listItem.borderColor}
                bg={styles.listItem.bg}
              >
                <VStack align="start" spacing={2}>
                  <Text>{newsletter.message}</Text>
                  <HStack spacing={4}>
                    <Text fontSize="sm" color="gray.600">
                      <Icon as={FiUsers} mr={1} />
                      Отправлено: {newsletter.recipient_count} пользователям
                    </Text>
                    <Text fontSize="sm" color="gray.600">
                      {new Date(newsletter.created_at).toLocaleString('ru-RU')}
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

export default Newsletters;