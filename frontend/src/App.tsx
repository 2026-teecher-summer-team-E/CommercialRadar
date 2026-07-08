import { BrowserRouter, Route, Routes } from "react-router-dom";

import DashboardPage from "./pages/DashboardPage";
import GangnamCafeDemoPage from "./pages/GangnamCafeDemoPage";
import MapPage from "./pages/MapPage";

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<MapPage />} />
        <Route path="/dashboard/:districtCode" element={<DashboardPage />} />
        <Route path="/demo/gangnam-cafe" element={<GangnamCafeDemoPage />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
