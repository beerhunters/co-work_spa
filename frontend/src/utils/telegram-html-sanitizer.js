/**
 * Утилита для очистки HTML от ненужных тегов для отправки в Telegram
 * Telegram поддерживает только: <b>, <i>, <u>, <code>, <a href="">
 */

/**
 * Очищает HTML, оставляя только теги поддерживаемые Telegram
 * @param {string} html - HTML строка для очистки
 * @returns {string} - Очищенная HTML строка
 */
export const sanitizeHtmlForTelegram = (html) => {
  if (!html) return '';

  // Создаем временный элемент для парсинга HTML
  const temp = document.createElement('div');
  temp.innerHTML = html;

  // Рекурсивная функция для обработки узлов
  const processNode = (node) => {
    if (node.nodeType === Node.TEXT_NODE) {
      return node.textContent;
    }

    if (node.nodeType === Node.ELEMENT_NODE) {
      const tagName = node.tagName.toLowerCase();
      const children = Array.from(node.childNodes).map(processNode).join('');

      // Конвертация тегов
      switch (tagName) {
        case 'b':
        case 'strong':
          return `<b>${children}</b>`;

        case 'i':
        case 'em':
          return `<i>${children}</i>`;

        case 'u':
          return `<u>${children}</u>`;

        case 'code':
          return `<code>${children}</code>`;

        case 'a':
          const href = node.getAttribute('href');
          if (href) {
            return `<a href="${href}">${children}</a>`;
          }
          return children; // Ссылка без href - просто текст

        case 'br':
          return '\n';

        case 'p':
        case 'div':
          return `${children}\n`;

        // Все остальные теги игнорируем, оставляем только содержимое
        default:
          return children;
      }
    }

    return '';
  };

  // Обрабатываем все узлы
  let result = Array.from(temp.childNodes).map(processNode).join('');

  // Убираем множественные переносы строк (больше 2 подряд)
  result = result.replace(/\n{3,}/g, '\n\n');

  // Убираем пробелы в начале и конце
  result = result.trim();

  return result;
};

/**
 * Проверяет длину текста (без HTML тегов) для Telegram
 * @param {string} html - HTML строка
 * @returns {number} - Длина текста без тегов
 */
export const getTextLength = (html) => {
  if (!html) return 0;

  const temp = document.createElement('div');
  temp.innerHTML = html;
  return temp.textContent.length;
};

/**
 * Обрезает HTML до указанной длины (учитывая только текст, не теги)
 * @param {string} html - HTML строка
 * @param {number} maxLength - Максимальная длина текста
 * @returns {string} - Обрезанная HTML строка
 */
export const truncateHtml = (html, maxLength = 4096) => {
  if (!html) return '';

  const temp = document.createElement('div');
  temp.innerHTML = html;

  const text = temp.textContent;
  if (text.length <= maxLength) {
    return html;
  }

  // Если текст слишком длинный, обрезаем его
  let truncated = '';
  let currentLength = 0;

  const processNode = (node) => {
    if (currentLength >= maxLength) return '';

    if (node.nodeType === Node.TEXT_NODE) {
      const remaining = maxLength - currentLength;
      const text = node.textContent;

      if (text.length <= remaining) {
        currentLength += text.length;
        return text;
      } else {
        currentLength = maxLength;
        return text.substring(0, remaining) + '...';
      }
    }

    if (node.nodeType === Node.ELEMENT_NODE) {
      const tagName = node.tagName.toLowerCase();
      const children = Array.from(node.childNodes).map(processNode).join('');

      if (!children) return '';

      switch (tagName) {
        case 'b':
        case 'strong':
          return `<b>${children}</b>`;
        case 'i':
        case 'em':
          return `<i>${children}</i>`;
        case 'u':
          return `<u>${children}</u>`;
        case 'code':
          return `<code>${children}</code>`;
        case 'a':
          const href = node.getAttribute('href');
          return href ? `<a href="${href}">${children}</a>` : children;
        case 'br':
          return '\n';
        case 'p':
        case 'div':
          return `${children}\n`;
        default:
          return children;
      }
    }

    return '';
  };

  truncated = Array.from(temp.childNodes).map(processNode).join('');
  return truncated.trim();
};
