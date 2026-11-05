import { Route, Routes } from "react-router-dom";
import { SessionProvider } from "./state/session";
import Age from "./pages/Age";
import Chat from "./pages/Chat";
import Confirmation from "./pages/Confirmation";
import Help from "./pages/Help";
import Language from "./pages/Language";
import Report from "./pages/Report";
import Status from "./pages/Status";
import Welcome from "./pages/Welcome";

export default function App() {
  return (
    <SessionProvider>
      <Routes>
        <Route path="/" element={<Welcome />} />
        <Route path="/age" element={<Age />} />
        <Route path="/language" element={<Language />} />
        <Route path="/chat" element={<Chat />} />
        <Route path="/report" element={<Report />} />
        <Route path="/confirmation" element={<Confirmation />} />
        <Route path="/status" element={<Status />} />
        <Route path="/help" element={<Help />} />
        <Route path="*" element={<Welcome />} />
      </Routes>
    </SessionProvider>
  );
}
