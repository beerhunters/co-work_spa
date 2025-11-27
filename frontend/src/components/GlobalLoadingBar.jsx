import { Box } from '@chakra-ui/react';
import { useEffect, useState } from 'react';

/**
 * Глобальный индикатор загрузки - появляется вверху страницы
 * Использует CSS анимацию для плавного прогресса
 */
const GlobalLoadingBar = ({ isLoading }) => {
  const [progress, setProgress] = useState(0);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    if (isLoading) {
      setVisible(true);
      setProgress(0);

      // Быстрый старт до 30%
      const timer1 = setTimeout(() => setProgress(30), 50);

      // Средняя загрузка до 60%
      const timer2 = setTimeout(() => setProgress(60), 200);

      // Медленная загрузка до 90%
      const timer3 = setTimeout(() => setProgress(90), 500);

      return () => {
        clearTimeout(timer1);
        clearTimeout(timer2);
        clearTimeout(timer3);
      };
    } else {
      // Завершаем до 100%
      setProgress(100);

      // Скрываем через 300ms после завершения
      const hideTimer = setTimeout(() => {
        setVisible(false);
        setProgress(0);
      }, 300);

      return () => clearTimeout(hideTimer);
    }
  }, [isLoading]);

  if (!visible) return null;

  return (
    <Box
      position="fixed"
      top="0"
      left="0"
      right="0"
      height="3px"
      zIndex="9999"
      bg="transparent"
    >
      <Box
        height="100%"
        bg="blue.500"
        width={`${progress}%`}
        transition="width 0.3s ease-out, opacity 0.3s ease-out"
        opacity={progress === 100 ? 0 : 1}
        boxShadow="0 0 10px rgba(49, 130, 206, 0.5)"
      />
    </Box>
  );
};

export default GlobalLoadingBar;
