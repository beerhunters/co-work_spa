// sections/Tariffs.jsx
import React from 'react';
import { Box, Card, CardHeader, CardBody, Heading, VStack, HStack, Text, Icon, Badge } from '@chakra-ui/react';
import { FiEye } from 'react-icons/fi';
import { sizes, styles, getStatusColor } from '../styles/styles';

const Tariffs = ({ tariffs, openDetailModal }) => {
  return (
    <Box p={sizes.content.padding} bg="gray.50" minH={sizes.content.minHeight}>
      <Card borderRadius={styles.card.borderRadius} boxShadow={styles.card.boxShadow}>
        <CardHeader>
          <Heading size="md">Тарифы</Heading>
        </CardHeader>
        <CardBody>
          <VStack align="stretch" spacing={2}>
            {tariffs.map(tariff => (
              <Box
                key={tariff.id}
                p={styles.listItem.padding}
                borderRadius={styles.listItem.borderRadius}
                border={styles.listItem.border}
                borderColor={styles.listItem.borderColor}
                bg={styles.listItem.bg}
                cursor={styles.listItem.cursor}
                _hover={styles.listItem.hover}
                transition={styles.listItem.transition}
                onClick={() => openDetailModal(tariff, 'tariff')}
              >
                <HStack justify="space-between">
                  <VStack align="start" spacing={1}>
                    <Text fontWeight="bold">{tariff.name}</Text>
                    <HStack spacing={4}>
                      <Text fontSize="sm" color="gray.600">
                        {tariff.price} ₽
                      </Text>
                      <Badge colorScheme={getStatusColor(tariff.is_active ? 'active' : 'inactive')}>
                        {tariff.is_active ? 'Активен' : 'Неактивен'}
                      </Badge>
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

export default Tariffs;