import { useState, useCallback } from 'react';
import { userApi } from '../utils/api';
import { useToast } from '@chakra-ui/react';

export const useAvatar = (user, onUpdate) => {
  const [avatarFile, setAvatarFile] = useState(null);
  const [isUploading, setIsUploading] = useState(false);
  const toast = useToast();

  const getAvatarUrl = useCallback(() => {
    if (avatarFile) {
      return URL.createObjectURL(avatarFile);
    }
    // Проверяем, есть ли у пользователя аватар в базе данных
    if (user?.avatar) {
      return userApi.getAvatar(user.id);
    }
    return null;
  }, [avatarFile, user]);

  const uploadAvatar = useCallback(async (file) => {
    if (!file || !user) return false;

    setIsUploading(true);
    try {
      await userApi.uploadAvatar(user.id, file);
      setAvatarFile(null);

      if (onUpdate) {
        await onUpdate();
      }

      toast({
        title: 'Аватар загружен',
        status: 'success',
        duration: 3000,
        isClosable: true,
      });

      return true;
    } catch (error) {
      console.error('Ошибка при загрузке аватара:', error);
      toast({
        title: 'Ошибка при загрузке аватара',
        description: error.response?.data?.detail || 'Произошла ошибка',
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
      return false;
    } finally {
      setIsUploading(false);
    }
  }, [user, onUpdate, toast]);

  const deleteAvatar = useCallback(async () => {
    if (!user) return false;

    setIsUploading(true);
    try {
      await userApi.deleteAvatar(user.id);
      setAvatarFile(null);

      if (onUpdate) {
        await onUpdate();
      }

      toast({
        title: 'Аватар удалён',
        status: 'success',
        duration: 3000,
        isClosable: true,
      });

      return true;
    } catch (error) {
      console.error('Ошибка при удалении аватара:', error);
      toast({
        title: 'Ошибка при удалении аватара',
        description: error.response?.data?.detail || 'Произошла ошибка',
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
      return false;
    } finally {
      setIsUploading(false);
    }
  }, [user, onUpdate, toast]);

  const handleAvatarError = useCallback((e) => {
    // Если изображение не загрузилось, скрываем src чтобы показать fallback
    e.target.src = '';
  }, []);

  return {
    avatarFile,
    setAvatarFile,
    isUploading,
    getAvatarUrl,
    uploadAvatar,
    deleteAvatar,
    handleAvatarError
  };
};