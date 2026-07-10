import { BrowserRouter, Route, Routes } from "react-router-dom";
import AppLayout from "./components/layout/AppLayout";
import DashboardPage from "./pages/DashboardPage";
import MapPage from "./pages/MapPage";
import ComparePage from "./pages/ComparePage";
import MyPage from "./pages/MyPage";

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<MapPage />} />
        <Route path="/dashboard/:districtCode" element={<DashboardPage />} />
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
