/**
 * Утилиты для работы с датами
 *
 * Этот модуль содержит функции для корректной работы с датами без проблем с часовыми поясами.
 */

/**
 * Форматирует локальную дату в строку формата YYYY-MM-DD без UTC конвертации.
 *
 * ПРОБЛЕМА: JavaScript Date.toISOString() конвертирует локальное время в UTC,
 * что вызывает смещение дат в часовых поясах отличных от UTC.
 *
 * Например, в Москве (UTC+3):
 * - Локальная дата: 03.12.2025 00:00 MSK
 * - После toISOString(): "2025-12-02T21:00:00Z" (смещение на -1 день)
 *
 * РЕШЕНИЕ: Использовать локальные методы Date (getFullYear, getMonth, getDate)
 * вместо toISOString() для форматирования дат.
 *
 * @param {Date} date - JavaScript Date объект в локальном времени
 * @returns {string} Дата в формате "YYYY-MM-DD" (например, "2025-12-03")
 *
 * @example
 * const date = new Date(2025, 11, 3); // 3 декабря 2025
 * formatLocalDate(date); // "2025-12-03"
 */
export const formatLocalDate = (date) => {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
};

/**
 * Конвертирует строку даты "YYYY-MM-DD" в локальный Date объект без UTC смещения.
 *
 * ПРОБЛЕМА: new Date("2025-12-03") создает Date в UTC timezone,
 * что может вызвать смещение при отображении в локальном времени.
 *
 * РЕШЕНИЕ: Парсим компоненты даты и создаем Date в локальном времени.
 *
 * @param {string} dateString - Строка даты в формате "YYYY-MM-DD"
 * @returns {Date|null} Date объект в локальном времени или null если формат неверный
 *
 * @example
 * parseLocalDate("2025-12-03"); // Date объект для 3 декабря 2025 в локальном времени
 */
export const parseLocalDate = (dateString) => {
  if (!dateString) return null;

  const match = dateString.match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (!match) return null;

  const year = parseInt(match[1], 10);
  const month = parseInt(match[2], 10) - 1; // месяцы в JS 0-indexed
  const day = parseInt(match[3], 10);

  return new Date(year, month, day);
};
