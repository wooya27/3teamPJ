/**
 * 라우터 + 인증 가드
 */

import { useEffect, useState } from "react";
import {
  BrowserRouter,
  Navigate,
  Outlet,
  Route,
  Routes,
  useNavigate,
  useSearchParams,
} from "react-router-dom";
import { authApi } from "./lib/api";
import { AuthProvider, useAuth } from "./lib/auth";
import { TeamProvider } from "./contexts/TeamContext";
import AppLayout from "./layouts/AppLayout";

// Pages
import Login from "./pages/Login";
import DashboardHome from "./pages/DashboardHome";
import Team from "./pages/Team";
import Settings from "./pages/Settings";
import KmsPage from "./pages/kms/KmsPage";
import KmsManagePage from "./pages/kms/KmsManagePage";
import ReviewPage from "./pages/review/ReviewPage";
import SecurityPage from "./pages/security/SecurityPage";
import LearningPage from "./pages/learning/LearningPage";
import YoutubeRecommendPage from "./pages/youtube/YoutubeRecommendPage";
import ApprovalsPlaceholder from "./pages/approvals/Placeholder";
import GraphPlaceholder from "./pages/graph/Placeholder";

function ProtectedRoute() {
  const { isAuthenticated, isLoading } = useAuth();
  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-notion-text-secondary text-sm">로딩 중...</div>
      </div>
    );
  }
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }
  return <Outlet />;
}

function AppRoutes() {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-notion-text-secondary text-sm">로딩 중...</div>
      </div>
    );
  }

  return (
    <Routes>
      <Route
        path="/login"
        element={isAuthenticated ? <Navigate to="/" replace /> : <Login />}
      />

      {/* OAuth callback — 토큰을 받아 저장 후 대시보드로 */}
      <Route path="/auth/callback" element={<OAuthCallback />} />

      <Route element={<ProtectedRoute />}>
        <Route
          element={
            <TeamProvider>
              <AppLayout />
            </TeamProvider>
          }
        >
          <Route path="/" element={<DashboardHome />} />
          <Route path="/team" element={<Team />} />
          <Route path="/settings" element={<Settings />} />
          <Route path="/kms" element={<KmsPage />} />
          <Route path="/kms/manage" element={<KmsManagePage />} />
          <Route path="/review" element={<ReviewPage />} />
          <Route path="/security" element={<SecurityPage />} />
          <Route path="/learning" element={<LearningPage />} />
          <Route path="/youtube" element={<YoutubeRecommendPage />} />
          <Route path="/approvals" element={<ApprovalsPlaceholder />} />
          <Route path="/graph" element={<GraphPlaceholder />} />
        </Route>
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

function oauthDedupeKey(code: string) {
  return `oauth:code:${code}`;
}

function OAuthCallback() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { completeLogin, reloadUser } = useAuth();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function finishLogin() {
      await reloadUser();
      if (!cancelled) navigate("/", { replace: true });
    }

    async function exchangeCode(code: string) {
      const dedupeKey = oauthDedupeKey(code);
      const status = sessionStorage.getItem(dedupeKey);

      if (status === "done" && localStorage.getItem("access_token")) {
        await finishLogin();
        return;
      }

      if (status === "pending") {
        for (let i = 0; i < 50; i++) {
          if (cancelled) return;
          if (
            sessionStorage.getItem(dedupeKey) === "done" &&
            localStorage.getItem("access_token")
          ) {
            await finishLogin();
            return;
          }
          await new Promise((r) => setTimeout(r, 100));
        }
        if (localStorage.getItem("access_token")) {
          await finishLogin();
        }
        return;
      }

      sessionStorage.setItem(dedupeKey, "pending");
      try {
        const res = await authApi.exchangeCallback(code);
        sessionStorage.setItem(dedupeKey, "done");
        await completeLogin(res.data.access_token, res.data.refresh_token);
        if (!cancelled) navigate("/", { replace: true });
      } catch (err: unknown) {
        if (localStorage.getItem("access_token")) {
          sessionStorage.setItem(dedupeKey, "done");
          await finishLogin();
          return;
        }
        sessionStorage.removeItem(dedupeKey);
        const detail = (err as { response?: { data?: { detail?: string } } })
          .response?.data?.detail;
        const msg =
          typeof detail === "string"
            ? detail
            : "GitHub 로그인에 실패했습니다. 로그인부터 다시 시도해 주세요.";
        if (!cancelled) setError(msg);
      }
    }

    const accessToken = searchParams.get("access_token");
    const refreshToken = searchParams.get("refresh_token");
    if (accessToken) {
      void completeLogin(accessToken, refreshToken ?? "").then(() => {
        if (!cancelled) navigate("/", { replace: true });
      });
      return () => {
        cancelled = true;
      };
    }

    const code = searchParams.get("code");
    if (!code) {
      setError("인증 코드가 없습니다.");
      return;
    }

    void exchangeCode(code);
    return () => {
      cancelled = true;
    };
  }, [searchParams, navigate, completeLogin, reloadUser]);

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-screen gap-4">
        <p className="text-sm text-red-600">{error}</p>
        <a href="/login" className="text-sm text-blue-600 underline">
          로그인으로 돌아가기
        </a>
      </div>
    );
  }

  return (
    <div className="flex items-center justify-center h-screen">
      <p className="text-sm text-notion-text-secondary">로그인 처리 중...</p>
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </BrowserRouter>
  );
}
