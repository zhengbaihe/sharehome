import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from 'react';
import { getCurrentUser, login as requestLogin, type LoginRequest, type User } from '../api/auth';

export const TOKEN_KEY = 'sharehome.accessToken';
interface AuthState {
  user: User | null;
  loading: boolean;
  login: (body: LoginRequest) => Promise<void>;
  logout: () => void;
}
const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const generation = useRef(0);
  useEffect(() => {
    const current = ++generation.current;
    const restore = async () => {
      try {
        const token = sessionStorage.getItem(TOKEN_KEY);
        if (token) {
          const restored = await getCurrentUser(token);
          if (current === generation.current) setUser(restored);
        }
      } catch {
        if (current === generation.current) {
          sessionStorage.removeItem(TOKEN_KEY);
          setUser(null);
        }
      } finally {
        if (current === generation.current) setLoading(false);
      }
    };
    void restore();
    return () => { generation.current++; };
  }, []);

  async function login(body: LoginRequest) {
    const current = ++generation.current;
    const result = await requestLogin(body);
    const authenticatedUser = await getCurrentUser(result.access_token);
    if (current !== generation.current) return;
    sessionStorage.setItem(TOKEN_KEY, result.access_token);
    setUser(authenticatedUser);
  }
  function logout() {
    generation.current++;
    sessionStorage.removeItem(TOKEN_KEY);
    setUser(null);
    setLoading(false);
  }
  return <AuthContext.Provider value={{ user, loading, login, logout }}>{children}</AuthContext.Provider>;
}
export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error('AuthProvider is required');
  return context;
}
