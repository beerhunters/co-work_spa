// // sections/Users.jsx
// import React from 'react';
// import { Box, Card, CardHeader, CardBody, Heading, VStack, HStack, Text, Icon, Badge } from '@chakra-ui/react';
// import { FiEye, FiPhone, FiMail } from 'react-icons/fi';
// import { sizes, styles } from '../styles/styles';
//
// const Users = ({ users, openDetailModal }) => {
//   return (
//     <Box p={sizes.content.padding} bg="gray.50" minH={sizes.content.minHeight}>
//       <Card borderRadius={styles.card.borderRadius} boxShadow={styles.card.boxShadow}>
//         <CardHeader>
//           <Heading size="md">Список пользователей</Heading>
//         </CardHeader>
//         <CardBody>
//           <VStack align="stretch" spacing={2}>
//             {users.map(user => (
//               <Box
//                 key={user.id}
//                 p={styles.listItem.padding}
//                 borderRadius={styles.listItem.borderRadius}
//                 border={styles.listItem.border}
//                 borderColor={styles.listItem.borderColor}
//                 bg={styles.listItem.bg}
//                 cursor={styles.listItem.cursor}
//                 _hover={styles.listItem.hover}
//                 transition={styles.listItem.transition}
//                 onClick={() => openDetailModal(user, 'user')}
//               >
//                 <HStack justify="space-between">
//                   <VStack align="start" spacing={1}>
//                     <Text fontWeight="bold">{user.full_name || 'Без имени'}</Text>
//                     <HStack spacing={4}>
//                       <Text fontSize="sm" color="gray.600">
//                         <Icon as={FiPhone} mr={1} />
//                         {user.phone || 'Не указан'}
//                       </Text>
//                       <Text fontSize="sm" color="gray.600">
//                         <Icon as={FiMail} mr={1} />
//                         {user.email || 'Не указан'}
//                       </Text>
//                     </HStack>
//                   </VStack>
//                   <Icon as={FiEye} color="purple.500" />
//                 </HStack>
//               </Box>
//             ))}
//           </VStack>
//         </CardBody>
//       </Card>
//     </Box>
//   );
// };
//
// export default Users;
import React from 'react';
import {
  Box,
  Grid,
  Card,
  CardBody,
  Text,
  Avatar,
  HStack,
  VStack,
  Badge,
  useColorModeValue
} from '@chakra-ui/react';
import { userApi } from '../utils/api';

const Users = ({ users, openDetailModal }) => {
  const cardBg = useColorModeValue('white', 'gray.800');
  const borderColor = useColorModeValue('gray.200', 'gray.600');

  const getAvatarUrl = (user) => {
    // Проверяем, есть ли у пользователя аватар в базе данных
    if (user?.avatar) {
      return userApi.getAvatar(user.id);
    }
    return null;
  };

  const handleAvatarError = (e) => {
    // Если изображение не загрузилось, скрываем src чтобы показать fallback
    e.target.src = '';
  };

  return (
    <Box p={6}>
      <Text fontSize="2xl" fontWeight="bold" mb={6}>
        Пользователи ({users.length})
      </Text>

      <Grid
        templateColumns="repeat(auto-fill, minmax(300px, 1fr))"
        gap={4}
      >
        {users.map(user => (
          <Card
            key={user.id}
            bg={cardBg}
            borderWidth="1px"
            borderColor={borderColor}
            _hover={{
              transform: 'translateY(-2px)',
              shadow: 'md',
              cursor: 'pointer'
            }}
            transition="all 0.2s"
            onClick={() => openDetailModal(user, 'user')}
          >
            <CardBody>
              <HStack spacing={4} align="start">
                <Avatar
                  size="lg"
                  src={getAvatarUrl(user)}
                  name={user.full_name || 'Пользователь'}
                  onError={handleAvatarError}
                />

                <VStack align="start" spacing={2} flex={1}>
                  <Text fontSize="lg" fontWeight="semibold">
                    {user.full_name || 'Не указано'}
                  </Text>

                  <Text fontSize="sm" color="gray.500">
                    @{user.username || 'Не указано'}
                  </Text>

                  <HStack wrap="wrap" spacing={2}>
                    <Badge colorScheme="blue" fontSize="xs">
                      ID: {user.telegram_id}
                    </Badge>

                    {user.successful_bookings > 0 && (
                      <Badge colorScheme="green" fontSize="xs">
                        {user.successful_bookings} броней
                      </Badge>
                    )}

                    {user.invited_count > 0 && (
                      <Badge colorScheme="purple" fontSize="xs">
                        +{user.invited_count} реферралов
                      </Badge>
                    )}
                  </HStack>

                  <Text fontSize="xs" color="gray.400">
                    Регистрация: {new Date(user.reg_date || user.first_join_time).toLocaleDateString('ru-RU')}
                  </Text>
                </VStack>
              </HStack>
            </CardBody>
          </Card>
        ))}
      </Grid>

      {users.length === 0 && (
        <Box
          textAlign="center"
          py={10}
          color="gray.500"
        >
          <Text fontSize="lg">Пользователи не найдены</Text>
        </Box>
      )}
    </Box>
  );
};

export default Users;