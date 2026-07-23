import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';

import { ReviewDashboard } from '../features/review/ReviewDashboard';
import { AccountPage } from '../features/auth/AccountPage';
import { AuthProvider } from '../features/auth/AuthContext';
import { AuthPage } from '../features/auth/AuthPage';
import { OAuthConsentPage } from '../features/auth/OAuthConsentPage';
import { App } from './App';
import './styles.css';
import '../features/review/review.css';

const savedTheme = localStorage.getItem('theme');
if (savedTheme === 'light' || savedTheme === 'dark') {
  document.documentElement.dataset.theme = savedTheme;
}

const Root = window.location.pathname === '/review' ? ReviewDashboard :
  window.location.pathname === '/auth' ? AuthPage :
    window.location.pathname === '/oauth/consent' ? OAuthConsentPage :
    window.location.pathname === '/account' ? AccountPage : App;

createRoot(document.getElementById('app')!).render(
  <StrictMode><AuthProvider><Root /></AuthProvider></StrictMode>,
);
