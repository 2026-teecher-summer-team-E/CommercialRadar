import { apiClient } from "../lib/apiClient";
import type { UserMe, UserStats } from "../types";

export const meApi = {
  /** [신규] 현재 로그인 유저 */
  me: () => apiClient.get<UserMe>("/api/users/me"),
  /** [신규] 마이페이지 요약 카운트 */
  stats: () => apiClient.get<UserStats>("/api/users/me/stats"),
};
