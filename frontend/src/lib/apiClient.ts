import axios from "axios";

/** 공용 axios 인스턴스. baseURL 은 VITE_API_URL(.env). 경로는 각 서비스에서 `/api/...` 로 붙인다. */
export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_URL ?? "",
});

/**
 * 요청마다 Bearer 토큰을 주입하기 위한 getter. 인증 계층(AuthProvider)이 등록한다.
 * Clerk 활성 시 Clerk 세션 토큰을, dev 모드에선 null 을 반환한다.
 */
type TokenGetter = (() => Promise<string | null>) | null;
let tokenGetter: TokenGetter = null;

export function setAuthTokenGetter(fn: TokenGetter): void {
  tokenGetter = fn;
}

apiClient.interceptors.request.use(async (config) => {
  if (tokenGetter) {
    try {
      const token = await tokenGetter();
      if (token) config.headers.Authorization = `Bearer ${token}`;
    } catch {
      /* 토큰 획득 실패 시 헤더 없이 진행(dev 우회 등) */
    }
  }
  return config;
});
