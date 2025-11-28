import { Box, Skeleton, Stack, Table, Tbody, Td, Th, Thead, Tr } from '@chakra-ui/react';

/**
 * Skeleton для таблиц - показывается при загрузке данных таблицы
 * @param {number} rows - количество строк скелетона (по умолчанию 5)
 * @param {number} columns - количество колонок (по умолчанию 6)
 */
export const TableSkeleton = ({ rows = 5, columns = 6 }) => {
  return (
    <Table variant="simple">
      <Thead>
        <Tr>
          {Array.from({ length: columns }).map((_, i) => (
            <Th key={`th-${i}`}>
              <Skeleton height="20px" />
            </Th>
          ))}
        </Tr>
      </Thead>
      <Tbody>
        {Array.from({ length: rows }).map((_, rowIndex) => (
          <Tr key={`row-${rowIndex}`}>
            {Array.from({ length: columns }).map((_, colIndex) => (
              <Td key={`cell-${rowIndex}-${colIndex}`}>
                <Skeleton height="20px" />
              </Td>
            ))}
          </Tr>
        ))}
      </Tbody>
    </Table>
  );
};

/**
 * Skeleton для карточек - показывается при загрузке grid/flex контента
 * @param {number} count - количество карточек (по умолчанию 3)
 */
export const CardSkeleton = ({ count = 3 }) => {
  return (
    <Stack spacing={4}>
      {Array.from({ length: count }).map((_, index) => (
        <Box
          key={`card-${index}`}
          borderWidth="1px"
          borderRadius="lg"
          p={6}
          bg="white"
        >
          <Stack spacing={3}>
            <Skeleton height="24px" width="60%" />
            <Skeleton height="16px" width="100%" />
            <Skeleton height="16px" width="80%" />
            <Skeleton height="40px" width="120px" mt={4} />
          </Stack>
        </Box>
      ))}
    </Stack>
  );
};

/**
 * Skeleton для статистических карточек (Dashboard)
 * @param {number} count - количество stat cards (по умолчанию 4)
 */
export const StatCardSkeleton = ({ count = 4 }) => {
  return (
    <Stack direction={{ base: 'column', md: 'row' }} spacing={4}>
      {Array.from({ length: count }).map((_, index) => (
        <Box
          key={`stat-${index}`}
          flex="1"
          borderWidth="1px"
          borderRadius="lg"
          p={6}
          bg="white"
        >
          <Stack spacing={2}>
            <Skeleton height="14px" width="50%" />
            <Skeleton height="32px" width="70%" />
            <Skeleton height="12px" width="40%" />
          </Stack>
        </Box>
      ))}
    </Stack>
  );
};

/**
 * Skeleton для списков (List view)
 * @param {number} items - количество элементов списка (по умолчанию 5)
 */
export const ListSkeleton = ({ items = 5 }) => {
  return (
    <Stack spacing={3}>
      {Array.from({ length: items }).map((_, index) => (
        <Box
          key={`list-item-${index}`}
          borderWidth="1px"
          borderRadius="md"
          p={4}
          bg="white"
        >
          <Stack direction="row" spacing={4} align="center">
            <Skeleton boxSize="40px" borderRadius="full" />
            <Stack flex="1" spacing={2}>
              <Skeleton height="16px" width="60%" />
              <Skeleton height="14px" width="40%" />
            </Stack>
            <Skeleton height="32px" width="80px" />
          </Stack>
        </Box>
      ))}
    </Stack>
  );
};

/**
 * Skeleton для форм (Modal/Form loading)
 * @param {number} fields - количество полей формы (по умолчанию 4)
 */
export const FormSkeleton = ({ fields = 4 }) => {
  return (
    <Stack spacing={4}>
      {Array.from({ length: fields }).map((_, index) => (
        <Box key={`field-${index}`}>
          <Skeleton height="14px" width="30%" mb={2} />
          <Skeleton height="40px" width="100%" />
        </Box>
      ))}
      <Stack direction="row" spacing={3} mt={6}>
        <Skeleton height="40px" width="100px" />
        <Skeleton height="40px" width="100px" />
      </Stack>
    </Stack>
  );
};

/**
 * Skeleton для страницы целиком (Full page loading)
 */
export const PageSkeleton = () => {
  return (
    <Box p={8}>
      <Stack spacing={6}>
        {/* Header */}
        <Stack direction="row" justify="space-between" align="center">
          <Skeleton height="32px" width="200px" />
          <Skeleton height="40px" width="120px" />
        </Stack>

        {/* Stats */}
        <StatCardSkeleton count={4} />

        {/* Table */}
        <Box borderWidth="1px" borderRadius="lg" overflow="hidden" bg="white">
          <TableSkeleton rows={8} columns={6} />
        </Box>
      </Stack>
    </Box>
  );
};
