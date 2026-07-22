import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';

import { ReviewDashboard } from '../features/review/ReviewDashboard';
import { App } from './App';
import './styles.css';
import '../features/review/review.css';

const Root = window.location.pathname === '/review' ? ReviewDashboard : App;

createRoot(document.getElementById('app')!).render(
  <StrictMode><Root /></StrictMode>,
);
