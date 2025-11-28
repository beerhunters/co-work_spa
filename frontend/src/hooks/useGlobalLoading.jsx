import { createContext, useContext, useState, useCallback } from 'react';

/**
 * Context для глобального loading состояния
 */
const GlobalLoadingContext = createContext(null);

/**
 * Provider для глобального loading индикатора
 */
export const GlobalLoadingProvider = ({ children }) => {
  const [loadingCount, setLoadingCount] = useState(0);

  const startLoading = useCallback(() => {
    setLoadingCount((prev) => prev + 1);
  }, []);

  const stopLoading = useCallback(() => {
    setLoadingCount((prev) => Math.max(0, prev - 1));
  }, []);

  const resetLoading = useCallback(() => {
    setLoadingCount(0);
  }, []);

  const isLoading = loadingCount > 0;

  return (
    <GlobalLoadingContext.Provider
      value={{ isLoading, startLoading, stopLoading, resetLoading }}
    >
      {children}
    </GlobalLoadingContext.Provider>
  );
};

/**
 * Хук для использования глобального loading индикатора
 * @returns {Object} - { isLoading, startLoading, stopLoading }
 *
 * @example
 * const { isLoading, startLoading, stopLoading } = useGlobalLoading();
 *
 * const fetchData = async () => {
 *   startLoading();
 *   try {
 *     const data = await api.get('/users');
 *   } finally {
 *     stopLoading();
 *   }
 * };
 */
export const useGlobalLoading = () => {
  const context = useContext(GlobalLoadingContext);

  if (!context) {
    throw new Error('useGlobalLoading must be used within GlobalLoadingProvider');
  }

  return context;
};

export default useGlobalLoading;
