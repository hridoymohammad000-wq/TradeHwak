import React from 'react';
import { useAuth } from '../context/AuthContext';
import Login from '../pages/Login';

export default function AuthGuard({ children }: { children: React.ReactNode }) {
  const { token } = useAuth();
  if (!token) return <Login />;
  return <>{children}</>;
}
