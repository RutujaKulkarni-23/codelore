import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { LandingPage } from "./pages/LandingPage";
import { CaseBoardPage } from "./pages/CaseBoardPage";
import { CaseViewPage } from "./pages/CaseViewPage";
import { CaseFilesPage } from "./pages/CaseFilesPage";
import { StartHerePage } from "./pages/StartHerePage";
import { SignInPage } from "./pages/SignInPage";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/board" element={<CaseBoardPage />} />
        <Route path="/case/:id" element={<CaseViewPage />} />
        <Route path="/files" element={<CaseFilesPage />} />
        <Route path="/start" element={<StartHerePage />} />
        <Route path="/signin" element={<SignInPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
