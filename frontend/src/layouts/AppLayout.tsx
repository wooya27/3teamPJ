/**
 * 노션 스타일 사이드바 레이아웃.
 * 팀 워크스페이스 + 역할(lead/member)별 메뉴 분기.
 */

import { useState } from "react";
import { Link, Outlet, useLocation, useNavigate } from "react-router-dom";
import {
  BookOpen,
  ChevronLeft,
  ChevronRight,
  FileText,
  GitPullRequest,
  Home,
  LayoutDashboard,
  LogOut,
  Network,
  Plus,
  ShieldCheck,
  Search,
  Settings,
  Users,
  Youtube,
} from "lucide-react";
import HeaderNotifications from "../components/HeaderNotifications";
import { useAuth } from "../lib/auth";
import { useTeamContext } from "../contexts/TeamContext";

interface NavItem {
  label: string;
  path: string;
  icon: React.ReactNode;
  leadOnly?: boolean;
  requiresTeam?: boolean;
  testId?: string;
}

const COMMON_NAV: NavItem[] = [
  {
    label: "KMS 지식 검색",
    path: "/kms",
    icon: <BookOpen size={16} />,
    requiresTeam: true,
    testId: "nav-item-kms",
  },
  {
    label: "PR 코드 리뷰",
    path: "/review",
    icon: <GitPullRequest size={16} />,
    requiresTeam: true,
    testId: "nav-item-review",
  },
{
  label: "정적 분석 · 보안 스캔",
  path: "/security",
  icon: <ShieldCheck size={16} />,
  requiresTeam: true,
  testId: "nav-item-security",
},


  {
    label: "커리큘럼 추천",
    path: "/learning",
    icon: <LayoutDashboard size={16} />,
    requiresTeam: true,
    testId: "nav-item-learning",
  },
  {
    label: "유튜브 추천",
    path: "/youtube",
    icon: <Youtube size={16} />,
    requiresTeam: true,
    testId: "nav-item-youtube",
  },
];

const MEMBER_NAV: NavItem[] = [
  {
    label: "내 현황",
    path: "/",
    icon: <Home size={16} />,
    requiresTeam: true,
    testId: "nav-item-home-member",
  },
];

const LEAD_NAV: NavItem[] = [
  {
    label: "팀 현황판",
    path: "/",
    icon: <Home size={16} />,
    leadOnly: true,
    requiresTeam: true,
    testId: "nav-item-dashboard",
  },
  {
    label: "KMS 문서 관리",
    path: "/kms/manage",
    icon: <FileText size={16} />,
    leadOnly: true,
    requiresTeam: true,
    testId: "nav-item-kms-manage",
  },
  {
    label: "지식 그래프",
    path: "/graph",
    icon: <Network size={16} />,
    leadOnly: true,
    requiresTeam: true,
    testId: "nav-item-graph",
  },
];

const ALWAYS_NAV: NavItem[] = [
  {
    label: "팀 멤버 관리",
    path: "/team",
    icon: <Users size={16} />,
    requiresTeam: false,
    testId: "nav-item-team",
  },
  {
    label: "설정",
    path: "/settings",
    icon: <Settings size={16} />,
    requiresTeam: false,
    testId: "nav-item-settings",
  },
];

function TeamWorkspaceSection() {
  const {
    teams,
    teamsLoading,
    currentTeamId,
    currentTeam,
    setCurrentTeamId,
    createTeam,
  } = useTeamContext();
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState("");
  const [newRepo, setNewRepo] = useState("");
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  const handleCreate = async () => {
    if (!newName.trim()) return;
    setCreating(true);
    setCreateError(null);
    try {
      if (!newRepo.trim()) {
        setCreateError("GitHub repo(owner/repo)를 입력하세요.");
        return;
      }
      await createTeam(newName.trim(), newRepo.trim());
      setNewName("");
      setNewRepo("");
      setShowCreate(false);
    } catch {
      setCreateError("팀 생성에 실패했습니다.");
    } finally {
      setCreating(false);
    }
  };

  const repoHint = currentTeam?.github_repo ?? null;

  return (
    <div
      className="px-3 py-3 border-b border-sidebar-border space-y-2"
      data-testid="team-workspace-section"
    >
      <p className="text-xs font-medium text-notion-text-secondary uppercase tracking-wide">
        워크스페이스
      </p>

      {teamsLoading ? (
        <p className="text-xs text-notion-text-secondary">팀 불러오는 중...</p>
      ) : teams.length > 0 ? (
        <div className="space-y-1">
          <select
            value={currentTeamId ?? ""}
            onChange={(e) => {
              const v = e.target.value;
              if (v) setCurrentTeamId(v);
            }}
            className="w-full text-sm border border-notion-border rounded px-2 py-1.5 bg-white text-notion-text focus:outline-none focus:ring-1 focus:ring-notion-text"
            data-testid="team-switcher"
            aria-label="팀 전환"
          >
            {currentTeamId == null && (
              <option value="" disabled>
                팀 선택...
              </option>
            )}
            {teams.map((t) => (
              <option key={t.id} value={t.id}>
                {t.name}
              </option>
            ))}
          </select>
          {repoHint && (
            <p className="text-xs text-notion-text-secondary truncate" title={repoHint}>
              repo: {repoHint}
            </p>
          )}
        </div>
      ) : (
        <p className="text-xs text-notion-text-secondary">
          팀을 선택하거나 생성하세요
        </p>
      )}

      {showCreate ? (
        <div className="space-y-2 rounded border border-notion-border bg-white p-2">
          <input
            type="text"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            placeholder="팀 이름"
            className="w-full text-sm border border-notion-border rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-notion-text"
            data-testid="sidebar-new-team-name"
          />
          <input
            type="text"
            value={newRepo}
            onChange={(e) => setNewRepo(e.target.value)}
            placeholder="GitHub repo (owner/repo)"
            className="w-full text-sm border border-notion-border rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-notion-text"
            data-testid="sidebar-new-team-repo"
          />
          <p className="text-[10px] text-notion-text-secondary">
            PR 웹훅은 이 repo와 매칭됩니다 (Phase 2)
          </p>
          {createError && (
            <p className="text-xs text-red-600">{createError}</p>
          )}
          <div className="flex gap-1">
            <button
              type="button"
              onClick={() => void handleCreate()}
              disabled={creating || !newName.trim()}
              className="flex-1 text-xs py-1.5 rounded bg-notion-text text-white disabled:opacity-50"
              data-testid="team-create-submit"
            >
              {creating ? "생성 중..." : "만들기"}
            </button>
            <button
              type="button"
              onClick={() => {
                setShowCreate(false);
                setCreateError(null);
              }}
              className="text-xs py-1.5 px-2 rounded border border-notion-border text-notion-text-secondary"
            >
              취소
            </button>
          </div>
        </div>
      ) : (
        <button
          type="button"
          onClick={() => setShowCreate(true)}
          className="flex items-center gap-1.5 w-full text-xs px-2 py-1.5 rounded border border-dashed border-notion-border text-notion-text-secondary hover:bg-sidebar-hover hover:text-notion-text"
          data-testid="team-create-button"
        >
          <Plus size={12} />
          팀 만들기
        </button>
      )}
    </div>
  );
}

function NavSection({
  title,
  children,
  testId,
}: {
  title: string;
  children: React.ReactNode;
  testId?: string;
}) {
  return (
    <div className="mb-4" data-testid={testId}>
      <p className="px-3 py-1.5 text-[11px] font-semibold text-notion-text-secondary uppercase tracking-wider">
        {title}
      </p>
      <div className="space-y-0.5">{children}</div>
    </div>
  );
}

function NavItemsGroup({
  items,
  navEnabled,
  isPathActive,
}: {
  items: NavItem[];
  navEnabled: boolean;
  isPathActive: (path: string) => boolean;
}) {
  return (
    <>
      {items.map((item) => {
        const enabled = !item.requiresTeam || navEnabled;
        return (
          <NavLinkItem
            key={`${item.path}-${item.label}`}
            item={item}
            enabled={enabled}
            isPathActive={isPathActive}
          />
        );
      })}
    </>
  );
}

function NavLinkItem({
  item,
  enabled,
  isPathActive,
}: {
  item: NavItem;
  enabled: boolean;
  isPathActive: (path: string) => boolean;
}) {
  const baseClass = `
    flex items-center gap-2 px-3 py-1.5 mx-1 rounded text-sm
    transition-colors duration-100
  `;
  const activeClass = "bg-sidebar-active text-notion-text font-medium";
  const inactiveClass =
    "text-notion-text-secondary hover:bg-sidebar-hover hover:text-notion-text";
  const disabledClass = "opacity-40 cursor-not-allowed text-notion-text-secondary";

  if (!enabled) {
    return (
      <span
        className={`${baseClass} ${disabledClass}`}
        aria-disabled="true"
        tabIndex={-1}
        title="팀을 먼저 선택하세요"
        data-testid={item.testId ? `${item.testId}-disabled` : undefined}
      >
        {item.icon}
        {item.label}
      </span>
    );
  }

  return (
    <Link
      to={item.path}
      className={`${baseClass} ${isPathActive(item.path) ? activeClass : inactiveClass}`}
      data-testid={item.testId}
    >
      {item.icon}
      {item.label}
    </Link>
  );
}

export default function AppLayout() {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const { user, logout } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const { currentTeamId, teamsLoading, role, roleLoading } = useTeamContext();

  const navEnabled = currentTeamId != null && !teamsLoading;
  const isLead = role === "lead";

  const handleLogout = async () => {
    await logout();
    navigate("/login");
  };

  const isActive = (path: string) => {
    if (path === "/") return location.pathname === "/";
    if (path === "/kms") {
      return (
        location.pathname === "/kms" ||
        (location.pathname.startsWith("/kms/") &&
          !location.pathname.startsWith("/kms/manage"))
      );
    }
    return location.pathname === path || location.pathname.startsWith(`${path}/`);
  };

  const commonNavItems = isLead ? COMMON_NAV : [...MEMBER_NAV, ...COMMON_NAV];

  return (
    <div className="flex h-screen overflow-hidden bg-notion-bg">
      <aside
        className={`
          flex-shrink-0 flex flex-col bg-sidebar border-r border-sidebar-border
          transition-all duration-200 ease-in-out
          ${sidebarOpen ? "w-60" : "w-0 overflow-hidden"}
        `}
      >
        <div className="flex items-center justify-between gap-2 px-3 py-3 border-b border-sidebar-border">
          <Link to="/" className="min-w-0 flex-shrink">
            <img
              src="/logo2.png"
              alt="code shepherd"
              className="h-7 w-auto max-w-[148px] object-contain object-left"
              data-testid="sidebar-logo"
            />
          </Link>
          <button
            type="button"
            onClick={() => setSidebarOpen(false)}
            className="p-1 rounded hover:bg-sidebar-hover text-notion-text-secondary"
            aria-label="사이드바 닫기"
          >
            <ChevronLeft size={16} />
          </button>
        </div>

        <TeamWorkspaceSection />

        <nav className="flex-1 overflow-y-auto py-2" aria-label="메인 메뉴">
          {!navEnabled && (
            <p
              className="px-3 py-1 text-xs text-notion-text-secondary"
              data-testid="nav-disabled-hint"
            >
              팀을 선택하면 메뉴가 활성화됩니다
            </p>
          )}
          {roleLoading && currentTeamId != null && (
            <p className="px-3 py-1 text-xs text-notion-text-secondary">역할 확인 중...</p>
          )}

          <NavSection title="공통" testId="nav-section-common">
            <NavItemsGroup
              items={commonNavItems}
              navEnabled={navEnabled}
              isPathActive={isActive}
            />
          </NavSection>

          {isLead && (
            <NavSection title="팀장" testId="nav-section-lead">
              <NavItemsGroup
                items={LEAD_NAV}
                navEnabled={navEnabled}
                isPathActive={isActive}
              />
            </NavSection>
          )}

          <div
            className="mt-2 pt-2 border-t border-sidebar-border"
            data-testid="nav-section-footer"
          >
            <NavItemsGroup
              items={ALWAYS_NAV}
              navEnabled={navEnabled}
              isPathActive={isActive}
            />
          </div>
        </nav>

        <div className="border-t border-sidebar-border px-3 py-3">
          <div className="flex items-center gap-2 mb-2">
            {user?.avatar_url ? (
              <img
                src={user.avatar_url}
                alt={user.login}
                className="w-6 h-6 rounded-full"
              />
            ) : (
              <div className="w-6 h-6 rounded-full bg-gray-300 flex items-center justify-center text-xs">
                {user?.login?.[0]?.toUpperCase()}
              </div>
            )}
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-notion-text truncate">
                {user?.name ?? user?.login}
              </p>
              <p className="text-xs text-notion-text-secondary truncate">
                @{user?.login}
                {currentTeamId != null && role && (
                  <span className="ml-1">
                    · {role === "lead" ? "팀장" : "팀원"}
                  </span>
                )}
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => void handleLogout()}
            className="flex items-center gap-2 w-full px-2 py-1.5 rounded text-sm text-notion-text-secondary hover:bg-sidebar-hover hover:text-notion-text transition-colors"
            data-testid="logout-button"
          >
            <LogOut size={14} />
            로그아웃
          </button>
        </div>
      </aside>

      <div className="flex-1 flex flex-col overflow-hidden">
        <header className="flex items-center gap-2 px-4 py-2 border-b border-notion-border bg-notion-bg">
          {!sidebarOpen && (
            <button
              type="button"
              onClick={() => setSidebarOpen(true)}
              className="p-1 rounded hover:bg-sidebar-hover text-notion-text-secondary"
              aria-label="사이드바 열기"
            >
              <ChevronRight size={16} />
            </button>
          )}
          <div className="flex items-center gap-2 flex-1 max-w-md bg-notion-bg-secondary rounded px-3 py-1.5 text-sm text-notion-text-secondary border border-notion-border">
            <Search size={14} />
            <span>검색...</span>
          </div>
          <HeaderNotifications />
        </header>

        <main className="flex-1 overflow-y-auto">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
