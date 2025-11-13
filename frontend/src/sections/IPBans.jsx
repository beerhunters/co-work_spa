import React, { useState, useEffect, useRef } from 'react';
import {
  Box,
  VStack,
  HStack,
  Heading,
  Text,
  Card,
  CardHeader,
  CardBody,
  Button,
  Input,
  InputGroup,
  InputLeftElement,
  Select,
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  Badge,
  Spinner,
  useToast,
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalBody,
  ModalFooter,
  ModalCloseButton,
  FormControl,
  FormLabel,
  Textarea,
  Stat,
  StatLabel,
  StatNumber,
  StatHelpText,
  StatGroup,
  Code,
  Tooltip,
  AlertDialog,
  AlertDialogBody,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogContent,
  AlertDialogOverlay,
  useDisclosure
} from '@chakra-ui/react';
import {
  FiShield,
  FiRefreshCw,
  FiSearch,
  FiLock,
  FiUnlock,
  FiTrash2,
  FiAlertTriangle,
  FiDownload,
  FiZap
} from 'react-icons/fi';
import { ipBanApi } from '../utils/api';
import { createLogger } from '../utils/logger.js';

const logger = createLogger('IPBans');

const IPBans = ({ currentAdmin }) => {
  const [loading, setLoading] = useState(true);
  const [bannedIPs, setBannedIPs] = useState([]);
  const [stats, setStats] = useState(null);
  const [durations, setDurations] = useState([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedIP, setSelectedIP] = useState(null);

  // Модалки
  const { isOpen: isBanOpen, onOpen: onBanOpen, onClose: onBanClose } = useDisclosure();
  const { isOpen: isUnbanOpen, onOpen: onUnbanOpen, onClose: onUnbanClose } = useDisclosure();
  const { isOpen: isClearOpen, onOpen: onClearOpen, onClose: onClearClose } = useDisclosure();

  // Форма бана
  const [banForm, setBanForm] = useState({
    ip: '',
    reason: 'Manual ban',
    duration_type: 'day'
  });

  const toast = useToast();
  const cancelRef = React.useRef();
  const intervalRef = useRef(null);

  // Auto-refresh states
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [lastUpdate, setLastUpdate] = useState(null);

  useEffect(() => {
    loadData();
  }, []);

  // Auto-refresh effect
  useEffect(() => {
    if (autoRefresh) {
      intervalRef.current = setInterval(loadData, 30000); // 30 seconds
    }

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, [autoRefresh]);

  // Toggle auto-refresh function
  const toggleAutoRefresh = () => {
    setAutoRefresh(!autoRefresh);
    if (!autoRefresh) {
      loadData(); // Refresh immediately when enabling
    }
  };

  const loadData = async () => {
    setLoading(true);
    try {
      const [bannedIPsData, statsData, durationsData] = await Promise.all([
        ipBanApi.getAll(200),
        ipBanApi.getStats(),
        ipBanApi.getDurations()
      ]);

      // Убеждаемся что bannedIPsData - это массив
      setBannedIPs(Array.isArray(bannedIPsData) ? bannedIPsData : []);
      setStats(statsData);
      setDurations(durationsData.durations || []);
      setLastUpdate(new Date().toISOString());

      logger.info('IP ban data loaded successfully');
    } catch (error) {
      logger.error('Error loading IP ban data:', error);
      toast({
        title: 'Ошибка',
        description: error.message || 'Не удалось загрузить данные',
        status: 'error',
        duration: 5000,
        isClosable: true
      });
    } finally {
      setLoading(false);
    }
  };

  const handleBan = async () => {
    if (!banForm.ip.trim()) {
      toast({
        title: 'Ошибка',
        description: 'Введите IP адрес',
        status: 'error',
        duration: 3000,
        isClosable: true
      });
      return;
    }

    try {
      await ipBanApi.ban(banForm.ip, banForm.reason, banForm.duration_type);

      toast({
        title: 'Успешно',
        description: `IP ${banForm.ip} забанен`,
        status: 'success',
        duration: 3000,
        isClosable: true
      });

      setBanForm({ ip: '', reason: 'Manual ban', duration_type: 'day' });
      onBanClose();
      loadData();
    } catch (error) {
      logger.error('Error banning IP:', error);
      toast({
        title: 'Ошибка',
        description: error.message || 'Не удалось забанить IP',
        status: 'error',
        duration: 5000,
        isClosable: true
      });
    }
  };

  const handleUnban = async (ip) => {
    try {
      await ipBanApi.unban(ip);

      toast({
        title: 'Успешно',
        description: `IP ${ip} разбанен`,
        status: 'success',
        duration: 3000,
        isClosable: true
      });

      onUnbanClose();
      setSelectedIP(null);
      loadData();
    } catch (error) {
      logger.error('Error unbanning IP:', error);
      toast({
        title: 'Ошибка',
        description: error.message || 'Не удалось разбанить IP',
        status: 'error',
        duration: 5000,
        isClosable: true
      });
    }
  };

  const handleClearAll = async () => {
    try {
      const result = await ipBanApi.clearAll();

      toast({
        title: 'Успешно',
        description: `Очищено ${result.unbanned_count} банов`,
        status: 'success',
        duration: 3000,
        isClosable: true
      });

      onClearClose();
      loadData();
    } catch (error) {
      logger.error('Error clearing all bans:', error);
      toast({
        title: 'Ошибка',
        description: error.message || 'Не удалось очистить баны',
        status: 'error',
        duration: 5000,
        isClosable: true
      });
    }
  };

  const handleExportToNginx = async () => {
    try {
      const result = await ipBanApi.exportToNginx();

      toast({
        title: 'Успешно',
        description: `Экспортировано ${result.exported_count} IP адресов в nginx`,
        status: 'success',
        duration: 3000,
        isClosable: true
      });

      logger.info('Nginx export completed:', result);
    } catch (error) {
      logger.error('Error exporting to nginx:', error);
      toast({
        title: 'Ошибка',
        description: error.message || 'Не удалось экспортировать в nginx',
        status: 'error',
        duration: 5000,
        isClosable: true
      });
    }
  };

  const openUnbanDialog = (ip) => {
    setSelectedIP(ip);
    onUnbanOpen();
  };

  const filteredBans = bannedIPs.filter(ban =>
    ban.ip.toLowerCase().includes(searchTerm.toLowerCase()) ||
    ban.reason.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const formatDuration = (seconds) => {
    const hours = Math.floor(seconds / 3600);
    const days = Math.floor(hours / 24);

    if (days > 300) return 'Навсегда';
    if (days > 0) return `${days} дн.`;
    return `${hours} ч.`;
  };

  const formatDateTime = (isoString) => {
    try {
      const date = new Date(isoString);
      return date.toLocaleString('ru-RU');
    } catch {
      return isoString;
    }
  };

  if (loading) {
    return (
      <Box p={8} textAlign="center">
        <Spinner size="xl" />
        <Text mt={4}>Загрузка данных...</Text>
      </Box>
    );
  }

  return (
    <Box p={8}>
      <VStack spacing={6} align="stretch">
        {/* Заголовок и кнопки */}
        <HStack justify="space-between">
          <HStack spacing={3}>
            <FiShield size={32} />
            <Heading size="lg">Управление IP банами</Heading>
          </HStack>
          <HStack spacing={3}>
            <Button
              leftIcon={<FiRefreshCw />}
              onClick={loadData}
              variant="outline"
            >
              Обновить
            </Button>
            <Button
              leftIcon={<FiZap />}
              onClick={toggleAutoRefresh}
              colorScheme={autoRefresh ? 'green' : 'gray'}
              variant={autoRefresh ? 'solid' : 'outline'}
              size="md"
            >
              {autoRefresh ? 'Авто' : 'Ручное'}
            </Button>
            <Button
              leftIcon={<FiLock />}
              colorScheme="red"
              onClick={onBanOpen}
            >
              Забанить IP
            </Button>
            {bannedIPs.length > 0 && (
              <>
                <Button
                  leftIcon={<FiDownload />}
                  colorScheme="blue"
                  variant="outline"
                  onClick={handleExportToNginx}
                >
                  Экспорт в nginx
                </Button>
                <Button
                  leftIcon={<FiTrash2 />}
                  colorScheme="orange"
                  variant="outline"
                  onClick={onClearOpen}
                >
                  Очистить все
                </Button>
              </>
            )}
          </HStack>
        </HStack>

        {/* Статистика */}
        {stats && (
          <Card>
            <CardBody>
              <StatGroup>
                <Stat>
                  <StatLabel>Забанено IP</StatLabel>
                  <StatNumber>{stats.total_banned}</StatNumber>
                  <StatHelpText>Активные баны</StatHelpText>
                </Stat>
                <Stat>
                  <StatLabel>Отслеживается</StatLabel>
                  <StatNumber>{stats.total_tracked}</StatNumber>
                  <StatHelpText>Подозрительные IP</StatHelpText>
                </Stat>
                <Stat>
                  <StatLabel>Redis</StatLabel>
                  <StatNumber>
                    <Badge colorScheme={stats.redis_available ? 'green' : 'red'}>
                      {stats.redis_available ? 'Доступен' : 'Недоступен'}
                    </Badge>
                  </StatNumber>
                  <StatHelpText>Статус хранилища</StatHelpText>
                </Stat>
              </StatGroup>
            </CardBody>
          </Card>
        )}

        {/* Поиск */}
        <Card>
          <CardBody>
            <InputGroup>
              <InputLeftElement pointerEvents="none">
                <FiSearch color="gray.300" />
              </InputLeftElement>
              <Input
                placeholder="Поиск по IP или причине..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
              />
            </InputGroup>
          </CardBody>
        </Card>

        {/* Таблица забаненных IP */}
        <Card>
          <CardHeader>
            <Heading size="md">
              Забаненные IP адреса ({filteredBans.length})
            </Heading>
          </CardHeader>
          <CardBody>
            {filteredBans.length === 0 ? (
              <Text color="gray.500" textAlign="center" py={8}>
                {searchTerm ? 'Ничего не найдено' : 'Нет забаненных IP адресов'}
              </Text>
            ) : (
              <Table variant="simple">
                <Thead>
                  <Tr>
                    <Th>IP Адрес</Th>
                    <Th>Причина</Th>
                    <Th>Забанен</Th>
                    <Th>Длительность</Th>
                    <Th>Осталось</Th>
                    <Th>Тип</Th>
                    <Th>Действия</Th>
                  </Tr>
                </Thead>
                <Tbody>
                  {filteredBans.map((ban) => (
                    <Tr key={ban.ip}>
                      <Td>
                        <Code>{ban.ip}</Code>
                      </Td>
                      <Td>
                        <Tooltip label={ban.reason}>
                          <Text isTruncated maxW="200px">
                            {ban.reason}
                          </Text>
                        </Tooltip>
                      </Td>
                      <Td>
                        <Text fontSize="sm">{formatDateTime(ban.banned_at)}</Text>
                        {ban.admin && (
                          <Text fontSize="xs" color="gray.500">
                            by {ban.admin}
                          </Text>
                        )}
                      </Td>
                      <Td>{formatDuration(ban.duration)}</Td>
                      <Td>
                        {ban.seconds_remaining ? (
                          <Tooltip label={formatDateTime(ban.unbanned_at)}>
                            <Text>{formatDuration(ban.seconds_remaining)}</Text>
                          </Tooltip>
                        ) : (
                          '-'
                        )}
                      </Td>
                      <Td>
                        <Badge colorScheme={ban.manual ? 'purple' : 'orange'}>
                          {ban.manual ? 'Ручной' : 'Авто'}
                        </Badge>
                      </Td>
                      <Td>
                        <Button
                          size="sm"
                          leftIcon={<FiUnlock />}
                          colorScheme="green"
                          onClick={() => openUnbanDialog(ban.ip)}
                        >
                          Разбанить
                        </Button>
                      </Td>
                    </Tr>
                  ))}
                </Tbody>
              </Table>
            )}
          </CardBody>
        </Card>

        {/* Футер с информацией об обновлении */}
        {lastUpdate && (
          <Text fontSize="sm" color="gray.500" textAlign="center">
            Последнее обновление: {new Date(lastUpdate).toLocaleString()}
            {autoRefresh && ' • Автообновление включено (каждые 30 секунд)'}
          </Text>
        )}
      </VStack>

      {/* Модалка бана IP */}
      <Modal isOpen={isBanOpen} onClose={onBanClose}>
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>Забанить IP адрес</ModalHeader>
          <ModalCloseButton />
          <ModalBody>
            <VStack spacing={4}>
              <FormControl isRequired>
                <FormLabel>IP Адрес</FormLabel>
                <Input
                  placeholder="192.168.1.1"
                  value={banForm.ip}
                  onChange={(e) => setBanForm({ ...banForm, ip: e.target.value })}
                />
              </FormControl>

              <FormControl isRequired>
                <FormLabel>Причина</FormLabel>
                <Textarea
                  placeholder="Причина бана..."
                  value={banForm.reason}
                  onChange={(e) => setBanForm({ ...banForm, reason: e.target.value })}
                  rows={3}
                />
              </FormControl>

              <FormControl isRequired>
                <FormLabel>Длительность</FormLabel>
                <Select
                  value={banForm.duration_type}
                  onChange={(e) => setBanForm({ ...banForm, duration_type: e.target.value })}
                >
                  {durations.map((dur) => (
                    <option key={dur.type} value={dur.type}>
                      {dur.label}
                    </option>
                  ))}
                </Select>
              </FormControl>
            </VStack>
          </ModalBody>
          <ModalFooter>
            <Button variant="ghost" mr={3} onClick={onBanClose}>
              Отмена
            </Button>
            <Button colorScheme="red" onClick={handleBan}>
              Забанить
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>

      {/* Диалог разбана */}
      <AlertDialog
        isOpen={isUnbanOpen}
        leastDestructiveRef={cancelRef}
        onClose={onUnbanClose}
      >
        <AlertDialogOverlay>
          <AlertDialogContent>
            <AlertDialogHeader fontSize="lg" fontWeight="bold">
              Разбанить IP
            </AlertDialogHeader>

            <AlertDialogBody>
              Вы уверены, что хотите разбанить IP <Code>{selectedIP}</Code>?
            </AlertDialogBody>

            <AlertDialogFooter>
              <Button ref={cancelRef} onClick={onUnbanClose}>
                Отмена
              </Button>
              <Button
                colorScheme="green"
                onClick={() => handleUnban(selectedIP)}
                ml={3}
              >
                Разбанить
              </Button>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialogOverlay>
      </AlertDialog>

      {/* Диалог очистки всех банов */}
      <AlertDialog
        isOpen={isClearOpen}
        leastDestructiveRef={cancelRef}
        onClose={onClearClose}
      >
        <AlertDialogOverlay>
          <AlertDialogContent>
            <AlertDialogHeader fontSize="lg" fontWeight="bold">
              <HStack>
                <FiAlertTriangle color="orange" />
                <Text>Очистить все баны</Text>
              </HStack>
            </AlertDialogHeader>

            <AlertDialogBody>
              Вы уверены, что хотите разбанить все IP адреса ({bannedIPs.length})?
              Это действие нельзя отменить.
            </AlertDialogBody>

            <AlertDialogFooter>
              <Button ref={cancelRef} onClick={onClearClose}>
                Отмена
              </Button>
              <Button
                colorScheme="orange"
                onClick={handleClearAll}
                ml={3}
              >
                Очистить все
              </Button>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialogOverlay>
      </AlertDialog>
    </Box>
  );
};

export default IPBans;
