// sections/Dashboard.jsx
import React, { useEffect } from 'react';
import {
  Box, VStack, SimpleGrid, Card, CardBody, CardHeader, Flex, Heading,
  Text, HStack, Icon, Stat, StatLabel, StatNumber, StatHelpText
} from '@chakra-ui/react';
import { FiUsers, FiShoppingBag, FiMessageCircle, FiTrendingUp } from 'react-icons/fi';
import Chart from 'chart.js/auto';
import { colors, sizes, styles } from '../styles/styles';

const Dashboard = ({
  stats,
  users,
  chartRef,
  chartInstanceRef,
  section
}) => {

  // Инициализация графика при заходе на вкладку "dashboard"
  useEffect(() => {
    if (
      chartRef.current &&
      users.length > 0 &&
      !chartInstanceRef.current &&
      section === 'dashboard'
    ) {
      const userRegistrationCounts = users.reduce((acc, u) => {
        if (u.reg_date || u.first_join_time) {
          const date = new Date(u.reg_date || u.first_join_time);
          const day = date.getDay() === 0 ? 6 : date.getDay() - 1;
          acc[day]++;
        }
        return acc;
      }, Array(7).fill(0));

      const ctx = chartRef.current.getContext('2d');

      chartInstanceRef.current = new Chart(ctx, {
        type: 'line',
        data: {
          labels: ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'],
          datasets: [{
            label: 'Регистрации пользователей',
            data: userRegistrationCounts,
            borderColor: colors.chart.borderColor,
            backgroundColor: colors.chart.backgroundColor,
            tension: 0.4,
            borderWidth: 3,
            pointBackgroundColor: colors.chart.pointColor,
            pointBorderColor: '#fff',
            pointBorderWidth: 2,
            pointRadius: 5,
            pointHoverRadius: 7,
          }]
        },
        options: styles.chart.options
      });
    }
  }, [users, chartRef, chartInstanceRef, section]);

  // Очистка графика при размонтировании
  useEffect(() => {
    return () => {
      if (chartInstanceRef.current) {
        chartInstanceRef.current.destroy();
        chartInstanceRef.current = null;
      }
    };
  }, []);

  return (
    <Box p={sizes.content.padding} bg="gray.50" minH={sizes.content.minHeight}>
      <VStack spacing={8} align="stretch">
        {/* Статистические карточки */}
        <SimpleGrid columns={{ base: 1, md: 3 }} spacing={6}>
          <Card
            bgGradient={colors.stats.users.gradient}
            color="white"
            boxShadow={styles.card.boxShadow}
            borderRadius={styles.card.borderRadius}
            transition={styles.card.transition}
            _hover={{
              transform: styles.card.hoverTransform,
              boxShadow: styles.card.hoverShadow
            }}
          >
            <CardBody p={6}>
              <Stat>
                <StatLabel fontSize="sm" fontWeight="medium" opacity={0.9}>
                  Всего пользователей
                </StatLabel>
                <StatNumber fontSize="3xl" fontWeight="bold" my={2}>
                  {stats.total_users}
                </StatNumber>
                <StatHelpText opacity={0.9}>
                  <HStack spacing={1}>
                    <Icon as={FiUsers} />
                    <Text>Активные пользователи</Text>
                  </HStack>
                </StatHelpText>
              </Stat>
            </CardBody>
          </Card>

          <Card
            bgGradient={colors.stats.bookings.gradient}
            color="white"
            boxShadow={styles.card.boxShadow}
            borderRadius={styles.card.borderRadius}
            transition={styles.card.transition}
            _hover={{
              transform: styles.card.hoverTransform,
              boxShadow: styles.card.hoverShadow
            }}
          >
            <CardBody p={6}>
              <Stat>
                <StatLabel fontSize="sm" fontWeight="medium" opacity={0.9}>
                  Всего бронирований
                </StatLabel>
                <StatNumber fontSize="3xl" fontWeight="bold" my={2}>
                  {stats.total_bookings}
                </StatNumber>
                <StatHelpText opacity={0.9}>
                  <HStack spacing={1}>
                    <Icon as={FiShoppingBag} />
                    <Text>Все бронирования</Text>
                  </HStack>
                </StatHelpText>
              </Stat>
            </CardBody>
          </Card>

          <Card
            bgGradient={colors.stats.tickets.gradient}
            color="white"
            boxShadow={styles.card.boxShadow}
            borderRadius={styles.card.borderRadius}
            transition={styles.card.transition}
            _hover={{
              transform: styles.card.hoverTransform,
              boxShadow: styles.card.hoverShadow
            }}
          >
            <CardBody p={6}>
              <Stat>
                <StatLabel fontSize="sm" fontWeight="medium" opacity={0.9}>
                  Открытые заявки
                </StatLabel>
                <StatNumber fontSize="3xl" fontWeight="bold" my={2}>
                  {stats.open_tickets}
                </StatNumber>
                <StatHelpText opacity={0.9}>
                  <HStack spacing={1}>
                    <Icon as={FiMessageCircle} />
                    <Text>Требуют внимания</Text>
                  </HStack>
                </StatHelpText>
              </Stat>
            </CardBody>
          </Card>
        </SimpleGrid>

        {/* График */}
        <Card
          boxShadow={styles.card.boxShadow}
          borderRadius={styles.card.borderRadius}
          overflow="hidden"
        >
          <CardHeader
            bg="white"
            borderBottom="2px"
            borderColor="gray.100"
            p={6}
          >
            <Flex align="center">
              <Icon as={FiTrendingUp} boxSize={6} color="purple.500" mr={3} />
              <Heading size="md" color="gray.800">
                Активность пользователей за неделю
              </Heading>
            </Flex>
          </CardHeader>
          <CardBody p={6} bg="white">
            <Box h={styles.chart.height}>
              <canvas ref={chartRef}></canvas>
            </Box>
          </CardBody>
        </Card>
      </VStack>
    </Box>
  );
};

export default Dashboard;
