import { BrowserRouter, Route, Routes } from "react-router-dom";
import AppLayout from "./components/layout/AppLayout";
import DashboardPage from "./pages/DashboardPage";
import MapPage from "./pages/MapPage";
import ComparePage from "./pages/ComparePage";
import MyPage from "./pages/MyPage";
import LandingPage from "./pages/LandingPage";

function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* 랜딩은 독립 레이아웃(사이드바 없음) */}
        <Route path="/landing" element={<LandingPage />} />

        {/* 앱 내부 페이지는 좌측 사이드바 레이아웃 공유 */}
        <Route
          path="/"
          element={
            <AppLayout>
              <MapPage />
            </AppLayout>
          }
        />
        <Route
          path="/dashboard/:districtCode"
          element={
            <AppLayout>
              <DashboardPage />
            </AppLayout>
          }
        />
        <Route
          path="/compare"
          element={
            <AppLayout>
              <ComparePage />
            </AppLayout>
          }
        />
        <Route
          path="/mypage"
          element={
            <AppLayout>
              <MyPage />
            </AppLayout>
          }
        />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
