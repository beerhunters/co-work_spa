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
  tickets,
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
      // Подсчет регистраций пользователей по дням недели
      const userRegistrationCounts = users.reduce((acc, u) => {
        if (u.reg_date || u.first_join_time) {
          const date = new Date(u.reg_date || u.first_join_time);
          const day = date.getDay() === 0 ? 6 : date.getDay() - 1;
          acc[day]++;
        }
        return acc;
      }, Array(7).fill(0));

      // Подсчет создания тикетов по дням недели
      const ticketCreationCounts = Array.isArray(tickets) ? tickets.reduce((acc, ticket) => {
        if (ticket.created_at) {
          const date = new Date(ticket.created_at);
          const day = date.getDay() === 0 ? 6 : date.getDay() - 1;
          acc[day]++;
        }
        return acc;
      }, Array(7).fill(0)) : Array(7).fill(0);

      // Подсчет бронирований по дням недели (заглушка - нужно добавить реальные данные)
      const bookingCreationCounts = Array(7).fill(0); // заменить на реальные данные бронирований

      const ctx = chartRef.current.getContext('2d');

      chartInstanceRef.current = new Chart(ctx, {
        type: 'line',
        data: {
          labels: ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'],
          datasets: [
            {
              label: 'Регистрации пользователей',
              data: userRegistrationCounts,
              borderColor: '#3B82F6',
              backgroundColor: 'rgba(59, 130, 246, 0.1)',
              tension: 0.4,
              borderWidth: 3,
              pointBackgroundColor: '#3B82F6',
              pointBorderColor: '#fff',
              pointBorderWidth: 2,
              pointRadius: 5,
              pointHoverRadius: 7,
              fill: true
            },
            {
              label: 'Создание тикетов',
              data: ticketCreationCounts,
              borderColor: '#F59E0B',
              backgroundColor: 'rgba(245, 158, 11, 0.1)',
              tension: 0.4,
              borderWidth: 3,
              pointBackgroundColor: '#F59E0B',
              pointBorderColor: '#fff',
              pointBorderWidth: 2,
              pointRadius: 5,
              pointHoverRadius: 7,
              fill: true
            },
            {
              label: 'Бронирования',
              data: bookingCreationCounts,
              borderColor: '#10B981',
              backgroundColor: 'rgba(16, 185, 129, 0.1)',
              tension: 0.4,
              borderWidth: 3,
              pointBackgroundColor: '#10B981',
              pointBorderColor: '#fff',
              pointBorderWidth: 2,
              pointRadius: 5,
              pointHoverRadius: 7,
              fill: true
            }
          ]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          interaction: {
            mode: 'index',
            intersect: false,
          },
          scales: {
            x: {
              display: true,
              title: {
                display: true,
                text: 'День недели',
                font: {
                  size: 14,
                  weight: 'bold'
                }
              },
              grid: {
                color: 'rgba(0, 0, 0, 0.05)'
              }
            },
            y: {
              type: 'linear',
              display: true,
              position: 'left',
              title: {
                display: true,
                text: 'Количество',
                font: {
                  size: 14,
                  weight: 'bold'
                },
                color: '#666'
              },
              grid: {
                color: 'rgba(0, 0, 0, 0.1)'
              },
              ticks: {
                color: '#666',
                beginAtZero: true,
                precision: 0
              }
            }
          },
          plugins: {
            tooltip: {
              backgroundColor: 'rgba(0, 0, 0, 0.8)',
              titleColor: '#fff',
              bodyColor: '#fff',
              borderColor: 'rgba(255, 255, 255, 0.1)',
              borderWidth: 1,
              cornerRadius: 8,
              displayColors: true,
              callbacks: {
                title: function(context) {
                  return `${context[0].label}`;
                },
                label: function(context) {
                  const label = context.dataset.label || '';
                  const value = context.parsed.y;
                  let unit = ' шт.';
                  if (label.includes('Пользователи')) unit = ' чел.';
                  if (label.includes('Бронирования')) unit = ' брон.';
                  return `${label}: ${value}${unit}`;
                }
              }
            },
            legend: {
              display: true,
              position: 'top',
              align: 'center',
              labels: {
                usePointStyle: true,
                pointStyle: 'circle',
                padding: 20,
                font: {
                  size: 13,
                  weight: '500'
                }
              }
            }
          },
          elements: {
            point: {
              hoverBorderWidth: 3
            }
          },
          ...(styles.chart?.options || {})
        }
      });
    }
  }, [users, tickets, chartRef, chartInstanceRef, section]);

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
                Активность за неделю
              </Heading>
              <Text fontSize="sm" color="gray.500" ml="auto">
                Регистрации и обращения по дням
              </Text>
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