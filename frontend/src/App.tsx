import {
  BrowserRouter,
  Route,
  Routes,
} from "react-router-dom"

import { ProtectedRoute } from "./components/ProtectedRoute"
import { DashboardPage } from "./pages/DashboardPage"
import { DocumentsPage } from "./pages/DocumentsPage"
import { LoginPage } from "./pages/LoginPage"
import { RegisterPage } from "./pages/RegisterPage"

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route
          path="/login"
          element={<LoginPage />}
        />

        <Route
          path="/register"
          element={<RegisterPage />}
        />

        <Route element={<ProtectedRoute />}>
          <Route
            path="/"
            element={<DashboardPage />}
          />

          <Route
            path="/documents"
            element={<DocumentsPage />}
          />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
