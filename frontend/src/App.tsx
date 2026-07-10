import { BrowserRouter, Route, Routes } from "react-router-dom";
import AppLayout from "./components/layout/AppLayout";
import { RequireAuth } from "./lib/auth";
import DashboardPage from "./pages/DashboardPage";
import MapPage from "./pages/MapPage";
import ComparePage from "./pages/ComparePage";
import MyPage from "./pages/MyPage";
import LandingPage from "./pages/LandingPage";
import SignInPage from "./pages/SignInPage";
import SignUpPage from "./pages/SignUpPage";

/** 앱 내부 페이지: 인증 가드 + 사이드바 레이아웃 공유. */
function appRoute(node: React.ReactNode) {
  return (
    <RequireAuth>
      <AppLayout>{node}</AppLayout>
    </RequireAuth>
  );
}

function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* 공개 라우트 */}
        <Route path="/landing" element={<LandingPage />} />
        <Route path="/sign-in/*" element={<SignInPage />} />
        <Route path="/sign-up/*" element={<SignUpPage />} />

        {/* 앱 내부(가드 + 사이드바) */}
        <Route path="/" element={appRoute(<MapPage />)} />
        <Route path="/dashboard/:districtCode" element={appRoute(<DashboardPage />)} />
        <Route path="/compare" element={appRoute(<ComparePage />)} />
        <Route path="/mypage" element={appRoute(<MyPage />)} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
