import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { Navigate } from "react-router-dom";
import {
  ClerkProvider,
  useAuth as useClerkAuth,
} from "@clerk/clerk-react";
import { setAuthTokenGetter } from "./apiClient";
import { meApi } from "../services/meApi";

const PUBLISHABLE_KEY = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY as
  | string
  | undefined;

/** Clerk 퍼블리셔블 키가 주입돼 있으면 실제 인증, 없으면 dev(ENV=dev 백엔드 우회) 모드. */
export const clerkEnabled = Boolean(PUBLISHABLE_KEY);

export interface AuthUser {
  name: string;
  email: string | null;
  isCompany: boolean;
  isAdmin: boolean;
}

interface AuthState {
  user: AuthUser | null;
  isLoaded: boolean;
  isSignedIn: boolean;
  signOut: () => void;
}

const AuthContext = createContext<AuthState>({
  user: null,
  isLoaded: false,
  isSignedIn: false,
  signOut: () => {},
});

export const useAuth = () => useContext(AuthContext);

/** 백엔드 /api/users/me 로 앱 유저(이름/이메일/등급)를 로드. 두 모드 공용. */
function useBackendUser(active: boolean) {
  const [user, setUser] = useState<AuthUser | null>(null);
  useEffect(() => {
    if (!active) {
      setUser(null);
      return;
    }
    let alive = true;
    meApi
      .me()
      .then((r) => {
        if (alive)
          setUser({
            name: r.data.name,
            email: r.data.email,
            isCompany: r.data.is_company,
            isAdmin: r.data.is_admin,
          });
      })
      .catch(() => {
        if (alive) setUser(null);
      });
    return () => {
      alive = false;
    };
  }, [active]);
  return user;
}

/** Clerk 활성 모드: 세션 토큰을 apiClient 에 등록하고 인증 상태를 컨텍스트로 노출. */
function ClerkBridge({ children }: { children: ReactNode }) {
  const { isLoaded, isSignedIn, getToken, signOut } = useClerkAuth();

  useEffect(() => {
    setAuthTokenGetter(() => getToken());
    return () => setAuthTokenGetter(null);
  }, [getToken]);

  const user = useBackendUser(Boolean(isSignedIn));

  return (
    <AuthContext.Provider
      value={{
        user,
        isLoaded: Boolean(isLoaded),
        isSignedIn: Boolean(isSignedIn),
        signOut: () => void signOut(),
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

/** dev 모드: 토큰 없이 ENV=dev 백엔드가 반환하는 고정 테스트 유저를 사용. */
function DevBridge({ children }: { children: ReactNode }) {
  useEffect(() => {
    setAuthTokenGetter(null);
  }, []);
  const user = useBackendUser(true);
  return (
    <AuthContext.Provider
      value={{
        user,
        isLoaded: true,
        isSignedIn: Boolean(user),
        signOut: () => {},
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function AuthProvider({ children }: { children: ReactNode }) {
  if (clerkEnabled) {
    return (
      <ClerkProvider publishableKey={PUBLISHABLE_KEY as string} afterSignOutUrl="/landing">
        <ClerkBridge>{children}</ClerkBridge>
      </ClerkProvider>
    );
  }
  return <DevBridge>{children}</DevBridge>;
}

/** 앱 내부 라우트 보호. Clerk 활성 && 미로그인이면 로그인으로 리다이렉트, dev 모드는 통과. */
export function RequireAuth({ children }: { children: ReactNode }) {
  const { isLoaded, isSignedIn } = useAuth();
  if (!clerkEnabled) return <>{children}</>;
  if (!isLoaded) return null;
  if (!isSignedIn) return <Navigate to="/landing" replace />;
  return <>{children}</>;
}
