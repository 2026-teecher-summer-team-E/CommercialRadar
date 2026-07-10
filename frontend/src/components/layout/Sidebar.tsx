import { NavLink } from "react-router-dom";
import { useAuth } from "../../lib/auth";
import styles from "./Sidebar.module.css";

function MapIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none">
      <path d="M12 21s7-6.3 7-11a7 7 0 10-14 0c0 4.7 7 11 7 11z" stroke="currentColor" strokeWidth="1.7" />
      <circle cx="12" cy="10" r="2.4" stroke="currentColor" strokeWidth="1.7" />
    </svg>
  );
}
function CompareIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none">
      <path d="M5 19V9M12 19V5M19 19v-6" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" />
    </svg>
  );
}
function RankIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none">
      <path
        d="M7 20h10M9 20v-4M15 20v-7M8 4h8v4a4 4 0 01-8 0V4zM8 5H5v1a3 3 0 003 3M16 5h3v1a3 3 0 01-3 3"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
function TrendIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none">
      <path d="M3 17l6-6 4 4 8-8M15 7h6v6" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
function GearIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none">
      <circle cx="12" cy="12" r="3" stroke="currentColor" strokeWidth="1.7" />
      <path
        d="M19 12a7 7 0 00-.1-1.3l2-1.5-2-3.4-2.3 1a7 7 0 00-2.3-1.3L13.7 2h-3.4l-.3 2.2a7 7 0 00-2.3 1.3l-2.3-1-2 3.4 2 1.5A7 7 0 005 12c0 .4 0 .9.1 1.3l-2 1.5 2 3.4 2.3-1a7 7 0 002.3 1.3l.3 2.2h3.4l.3-2.2a7 7 0 002.3-1.3l2.3 1 2-3.4-2-1.5c.1-.4.1-.9.1-1.3z"
        stroke="currentColor"
        strokeWidth="1.4"
      />
    </svg>
  );
}

const NAV = [
  { to: "/", label: "지역 분석", Icon: MapIcon, end: true },
  { to: "/compare", label: "상권 비교", Icon: CompareIcon },
  { to: "/ranking", label: "랭킹", Icon: RankIcon },
  { to: "/trends", label: "트렌드", Icon: TrendIcon },
  { to: "/admin", label: "관리", Icon: GearIcon },
];

export default function Sidebar() {
  const { user, isSignedIn } = useAuth();

  const name = user?.name ?? "게스트";
  const plan = user ? (user.isCompany ? "기업 회원" : "일반 회원") : "로그인 필요";

  return (
    <aside className={styles.sidebar}>
      <div className={styles.logo}>
        <span className={styles.logoMark}>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
            <path
              d="M12 6c-2.8 0-5 2.2-5 5 0 3.5 5 9 5 9s5-5.5 5-9c0-2.8-2.2-5-5-5zm0 6.8a1.8 1.8 0 110-3.6 1.8 1.8 0 010 3.6z"
              fill="#fff"
            />
          </svg>
        </span>
        <span className={styles.logoText}>상권레이더</span>
      </div>

      <nav className={styles.nav}>
        {NAV.map(({ to, label, Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) => (isActive ? `${styles.item} ${styles.active}` : styles.item)}
          >
            <Icon />
            <span>{label}</span>
          </NavLink>
        ))}
      </nav>

      <div className={styles.spacer} />

      {isSignedIn || user ? (
        <NavLink to="/mypage" className={styles.profile}>
          <span className={styles.avatar}>{name.charAt(0)}</span>
          <span className={styles.profileInfo}>
            <span className={styles.profileName}>{name}</span>
            <span className={styles.profilePlan}>{plan}</span>
          </span>
        </NavLink>
      ) : (
        <NavLink to="/sign-in" className={styles.profile}>
          <span className={styles.avatar}>?</span>
          <span className={styles.profileInfo}>
            <span className={styles.profileName}>로그인</span>
            <span className={styles.profilePlan}>계정으로 시작하기</span>
          </span>
        </NavLink>
      )}
    </aside>
  );
}
