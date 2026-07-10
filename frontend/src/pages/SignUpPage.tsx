import { SignUp } from "@clerk/clerk-react";
import { Navigate } from "react-router-dom";
import { clerkEnabled } from "../lib/auth";
import styles from "./AuthPage.module.css";

export default function SignUpPage() {
  if (!clerkEnabled) return <Navigate to="/" replace />;
  return (
    <div className={styles.wrap}>
      <div className={styles.col}>
        <div className={styles.brand}>
          <span className={styles.brandMark}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
              <path
                d="M12 6c-2.8 0-5 2.2-5 5 0 3.5 5 9 5 9s5-5.5 5-9c0-2.8-2.2-5-5-5zm0 6.8a1.8 1.8 0 110-3.6 1.8 1.8 0 010 3.6z"
                fill="#fff"
              />
            </svg>
          </span>
          <span className={styles.brandText}>상권레이더</span>
        </div>
        <SignUp routing="path" path="/sign-up" signInUrl="/sign-in" fallbackRedirectUrl="/" />
      </div>
    </div>
  );
}
