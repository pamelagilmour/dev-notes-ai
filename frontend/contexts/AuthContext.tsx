'use client';

import { createContext, useContext, useState, useEffect, ReactNode } from 'react';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface User {
  id: number;
  email: string;
  created_at: string;
}

interface AuthContextType {
  user: User | null;
  token: string | null;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  logout: () => void;
  loading: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  // Check if user is logged in on mount
  useEffect(() => {
    const storedToken = localStorage.getItem('token');
    if (storedToken) {
      // Verify token is still valid
      fetch(`${API_URL}/api/auth/me`, {
        headers: {
          'Authorization': `Bearer ${storedToken}`
        }
      })
        .then(res => res.json())
        .then(data => {
          if (data.id) {
            setUser(data);
            setToken(storedToken);
          } else {
            localStorage.removeItem('token');
          }
        })
        .catch(() => {
          localStorage.removeItem('token');
        })
        .finally(() => {
          setLoading(false);
        });
    } else {
      setLoading(false);
    }
  }, []);

  const register = async (email: string, password: string) => {
    const response = await fetch(`${API_URL}/api/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password, website: '' })
    });

    if (!response.ok) {
      const error = await response.json();
      
      // Handle Pydantic validation errors
      if (error.detail && Array.isArray(error.detail)) {
        // Extract validation error messages
        const messages = error.detail.map((err: any) => {
          if (err.msg) return err.msg;
          if (err.message) return err.message;
          return JSON.stringify(err);
        }).join(', ');
        throw new Error(messages);
      }
      
      // Handle simple error messages
      if (typeof error.detail === 'string') {
        throw new Error(error.detail);
      }
      
      throw new Error('Registration failed');
    }

    // After successful registration, log them in
    await login(email, password);
  };

  const login = async (email: string, password: string) => {
    const response = await fetch(`${API_URL}/api/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password })
    });

    if (!response.ok) {
      const error = await response.json();
      
      // Handle Pydantic validation errors
      if (error.detail && Array.isArray(error.detail)) {
        const messages = error.detail.map((err: any) => {
          if (err.msg) return err.msg;
          if (err.message) return err.message;
          return JSON.stringify(err);
        }).join(', ');
        throw new Error(messages);
      }
      
      // Handle simple error messages
      if (typeof error.detail === 'string') {
        throw new Error(error.detail);
      }
      
      throw new Error('Login failed');
    }

    const data = await response.json();
    setToken(data.access_token);
    setUser(data.user);
    localStorage.setItem('token', data.access_token);
  };

  const logout = () => {
    setUser(null);
    setToken(null);
    localStorage.removeItem('token');
  };

  return (
    <AuthContext.Provider value={{ user, token, login, register, logout, loading }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}