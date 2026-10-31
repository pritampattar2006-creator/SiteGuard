import React from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import '../../shared/base.css';
import { AuthProvider } from '../../shared/auth.jsx';
import App from './App.jsx';

createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <BrowserRouter>
      <AuthProvider role="supervisor" auto={['S001', '123456789']}><App /></AuthProvider>
    </BrowserRouter>
  </React.StrictMode>,
);
