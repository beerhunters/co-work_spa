import React from 'react';
   import ReactDOM from 'react-dom/client';
   import App from './App.jsx';
   import axios from 'axios';

   /**
    * Настройка Axios для отправки credentials с каждым запросом
    */
   axios.defaults.withCredentials = true;

   /**
    * Инициализация приложения
    */
   ReactDOM.createRoot(document.getElementById('root')).render(
       <React.StrictMode>
           <App />
       </React.StrictMode>
   );