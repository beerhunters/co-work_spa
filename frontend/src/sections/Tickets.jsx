import React from 'react';
import {
  Box,
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  Badge,
  Text,
  useColorModeValue,
  VStack,
  HStack,
  Icon
} from '@chakra-ui/react';
import { FiImage, FiMessageSquare } from 'react-icons/fi';
import { getStatusColor } from '../styles/styles';

const Tickets = ({ tickets, openDetailModal }) => {
  const tableBg = useColorModeValue('white', 'gray.800');
  const borderColor = useColorModeValue('gray.200', 'gray.600');

  const getStatusLabel = (status) => {
    const statusLabels = {
      'OPEN': 'Открыта',
      'IN_PROGRESS': 'В работе',
      'CLOSED': 'Закрыта'
    };
    return statusLabels[status] || status;
  };

  return (
    <VStack align="stretch" spacing={6}>
      <Text fontSize="2xl" fontWeight="bold">
        Тикеты поддержки
      </Text>

      <Box bg={tableBg} borderRadius="lg" overflow="hidden" boxShadow="sm">
        <Table variant="simple">
          <Thead bg={useColorModeValue('gray.50', 'gray.700')}>
            <Tr>
              <Th>ID</Th>
              <Th>Пользователь</Th>
              <Th>Описание</Th>
              <Th>Статус</Th>
              <Th>Дата создания</Th>
              <Th>Файлы</Th>
            </Tr>
          </Thead>
          <Tbody>
            {tickets.map(ticket => (
              <Tr
                key={ticket.id}
                cursor="pointer"
                _hover={{
                  bg: useColorModeValue('gray.50', 'gray.700'),
                  transform: 'translateY(-1px)',
                  boxShadow: 'md'
                }}
                transition="all 0.2s"
                onClick={() => openDetailModal(ticket, 'ticket')}
              >
                <Td fontWeight="semibold">#{ticket.id}</Td>
                <Td>
                  <VStack align="start" spacing={0}>
                    <Text fontWeight="medium">
                      {ticket.user?.full_name || 'Неизвестно'}
                    </Text>
                    <Text fontSize="sm" color="gray.500">
                      @{ticket.user?.username || 'Неизвестно'}
                    </Text>
                  </VStack>
                </Td>
                <Td>
                  <Text noOfLines={2} maxW="300px">
                    {ticket.description.length > 100
                      ? `${ticket.description.substring(0, 100)}...`
                      : ticket.description
                    }
                  </Text>
                </Td>
                <Td>
                  <Badge colorScheme={getStatusColor(ticket.status)}>
                    {getStatusLabel(ticket.status)}
                  </Badge>
                </Td>
                <Td>
                  <Text fontSize="sm">
                    {new Date(ticket.created_at).toLocaleDateString('ru-RU')}
                  </Text>
                </Td>
                <Td>
                  <HStack spacing={2}>
                    {ticket.photo_id && (
                      <Icon
                        as={FiImage}
                        color="blue.500"
                        title="Есть прикрепленное фото от пользователя"
                      />
                    )}
                    {ticket.comment && (
                      <Icon
                        as={FiMessageSquare}
                        color="green.500"
                        title="Есть комментарий администратора"
                      />
                    )}
                    {ticket.response_photo_id && (
                      <Icon
                        as={FiImage}
                        color="purple.500"
                        title="Есть фото в ответе администратора"
                      />
                    )}
                  </HStack>
                </Td>
              </Tr>
            ))}
          </Tbody>
        </Table>

        {tickets.length === 0 && (
          <Box textAlign="center" py={8}>
            <Text color="gray.500">Тикетов пока нет</Text>
          </Box>
        )}
      </Box>
    </VStack>
  );
};

export default Tickets;