/**
 * TDD: 학습 페이지 — 진입 시 모달 자동 표시, 예/아니오로 닫기 (T9, FRONTEND_SPEC Section 1/10).
 */

// [REVIEW] 아래 3줄: 기존 import에 afterEach/vi, m4Api, vi.mock(...)이 추가됨 (원래는 render/screen, userEvent, {describe, expect, it}, LearningPage만 있었음)
import { act, render, screen } from "@testing-library/react"; // [REVIEW] act 추가됨 — Slice 3 (지연된 mock 응답을 resolve할 때 상태 업데이트를 act로 감싸기 위함)
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest"; // [REVIEW] 추가됨: afterEach, vi (기존엔 describe, expect, it만 있었음)

import LearningPage from "../pages/learning/LearningPage";
import { m4Api } from "../pages/learning/lib/m4Api"; // [REVIEW] 신규 추가 — Slice 1

// [REVIEW] 신규 추가 블록 — Slice 1 (m4Api 모킹)
vi.mock("../pages/learning/lib/m4Api", () => ({
  m4Api: {
    post: vi.fn().mockResolvedValue({ data: { scan_id: "default-scan", plan_ids: [] }, status: 202 }),
    get: vi.fn().mockResolvedValue({ data: { issues: [] }, status: 200 }),
  },
}));

// [REVIEW] 여기서부터 ── 이 describe 블록과 안의 it 3개는 "원래 있던 것" (이번 세션에서 수정 안 함)
describe("LearningPage", () => {
  it("마운트되면 학습 시작 확인 모달이 자동으로 표시된다", () => {
    render(<LearningPage />);

    expect(screen.getByText("학습을 시작하겠습니까?")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "예" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "아니오" })).toBeInTheDocument();
  });

  it("예 클릭 시 모달이 닫힌다", async () => {
    const user = userEvent.setup();
    render(<LearningPage />);

    await user.click(screen.getByRole("button", { name: "예" }));

    expect(screen.queryByText("학습을 시작하겠습니까?")).not.toBeInTheDocument();
  });

  it("아니오 클릭 시 모달이 닫힌다", async () => {
    const user = userEvent.setup();
    render(<LearningPage />);

    await user.click(screen.getByRole("button", { name: "아니오" }));

    expect(screen.queryByText("학습을 시작하겠습니까?")).not.toBeInTheDocument();
  });
}); // [REVIEW] ── 여기까지 "원래 있던 것"

// [REVIEW] 이 describe 블록 전체가 신규 추가됨 — Slice 1
describe("LearningPage — 학습 시작 API 연동 (T9 Slice 1)", () => {
  afterEach(() => {
    vi.mocked(m4Api.post).mockClear();
    vi.mocked(m4Api.get).mockClear();
  });

  it("예 클릭 시 m4Api.post('/api/learn')을 호출하고 로딩 상태를 표시한다", async () => {
    // [REVIEW] Slice 3에서 폴링 결과가 즉시 resolve되도록 바뀌면서, mockResolvedValue로는 로딩 문구가
    // 카드 목록으로 너무 빨리 교체돼 관찰이 불가능해짐 → post 응답 시점을 직접 제어하는 방식으로 변경
    let resolvePost!: (value: { data: { scan_id: string; plan_ids: string[] }; status: number }) => void;
    vi.mocked(m4Api.post).mockImplementation(
      () =>
        new Promise((resolve) => {
          resolvePost = resolve;
        }),
    );
    const user = userEvent.setup();
    render(<LearningPage />);

    await user.click(screen.getByRole("button", { name: "예" }));

    expect(m4Api.post).toHaveBeenCalledWith("/api/learn", {});
    expect(screen.getByText("학습 카드를 생성하고 있어요...")).toBeInTheDocument();

    // [REVIEW] act로 감싸서 응답 이후의 상태 업데이트(setIssues, setLoading)를 테스트 종료 전에 모두 반영시킴
    await act(async () => {
      resolvePost({ data: { scan_id: "scan-1", plan_ids: ["p1", "p2", "p3"] }, status: 202 });
    });
  });
});

// [REVIEW] 이 describe 블록 전체가 신규 추가됨 — Slice 3
describe("LearningPage — 학습 카드 렌더링 (T9 Slice 3)", () => {
  afterEach(() => {
    vi.mocked(m4Api.post).mockClear();
    vi.mocked(m4Api.get).mockClear();
  });

  it("폴링 결과(issues)를 받으면 로딩 문구 대신 이슈별 학습 카드를 렌더링한다", async () => {
    vi.mocked(m4Api.post).mockResolvedValue({
      data: { scan_id: "scan-1", plan_ids: ["p1"] },
      status: 202,
    });
    vi.mocked(m4Api.get).mockResolvedValue({
      data: {
        issues: [
          {
            id: "issue-1",
            keyword: "SQL Injection",
            severity: "high",
            plan: {
              id: "p1",
              status: "completed",
              llm_fallback: false,
              error_message: null,
              ragas_reason: null,
              attempt_count: 1,
              card_content: {
                header: {
                  keyword: "SQL Injection",
                  name_of_function: "search_products",
                  sub_category: "input validation",
                  language: "Python",
                  framework: "FastAPI",
                  framework_version: "0.104.0",
                  depth: "deep",
                },
                before_code: null,
                after_code: 'def safe_query(keyword):\n    return "SELECT * FROM t WHERE x=%s", (keyword,)',
                explanation: "사용자 입력을 직접 SQL에 삽입하면 공격자가 쿼리를 조작할 수 있습니다.",
                why_dangerous: "상품 검색에 SQL Injection이 발생하면 전체 DB가 노출될 수 있습니다.",
                core_summary: "SQL Injection: 사용자 입력은 Parameterized Query로만 처리한다",
                learning_recommendations: [],
              },
            },
          },
        ],
      },
      status: 200,
    });
    const user = userEvent.setup();
    render(<LearningPage />);

    await user.click(screen.getByRole("button", { name: "예" }));

    expect(await screen.findByText(/\[SQL Injection\]/)).toBeInTheDocument();
    expect(screen.queryByText("학습 카드를 생성하고 있어요...")).not.toBeInTheDocument();
  });
});

describe("LearningPage — 학습할 이슈 없음 안내", () => {
  afterEach(() => {
    vi.mocked(m4Api.post).mockClear();
    vi.mocked(m4Api.get).mockClear();
  });

  it("폴링 결과 issues가 빈 배열이면 빈 화면 대신 안내 문구를 표시한다", async () => {
    vi.mocked(m4Api.post).mockResolvedValue({ data: { scan_id: "scan-empty", plan_ids: [] }, status: 200 });
    vi.mocked(m4Api.get).mockResolvedValue({ data: { issues: [] }, status: 200 });

    const user = userEvent.setup();
    render(<LearningPage />);

    await user.click(screen.getByRole("button", { name: "예" }));

    expect(await screen.findByText("학습할 이슈를 찾지 못했어요")).toBeInTheDocument();
    expect(
      screen.getByText(/PR 리뷰가 진행 중이거나 발견된 이슈가 없을 수 있어요/),
    ).toBeInTheDocument();
    expect(screen.queryByText("학습 카드를 생성하고 있어요...")).not.toBeInTheDocument();
  });

  it("'다시 확인하기' 버튼 클릭 시 /api/learn을 재호출하고, 이번엔 이슈가 있으면 카드를 렌더링한다", async () => {
    vi.mocked(m4Api.post)
      .mockResolvedValueOnce({ data: { scan_id: "scan-empty", plan_ids: [] }, status: 200 })
      .mockResolvedValueOnce({ data: { scan_id: "scan-empty", plan_ids: ["p1"] }, status: 200 });
    vi.mocked(m4Api.get)
      .mockResolvedValueOnce({ data: { issues: [] }, status: 200 })
      .mockResolvedValueOnce({
        data: {
          issues: [
            {
              id: "issue-1",
              keyword: "SQL Injection",
              severity: "high",
              plan: {
                id: "p1",
                status: "completed",
                llm_fallback: false,
                error_message: null,
                ragas_reason: null,
                attempt_count: 1,
                card_content: {
                  header: {
                    keyword: "SQL Injection",
                    name_of_function: "search_products",
                    sub_category: "input validation",
                    language: "Python",
                    framework: "FastAPI",
                    framework_version: "0.104.0",
                    depth: "deep",
                  },
                  before_code: null,
                  after_code: 'def safe_query(keyword):\n    return "SELECT * FROM t WHERE x=%s", (keyword,)',
                  explanation: "사용자 입력을 직접 SQL에 삽입하면 공격자가 쿼리를 조작할 수 있습니다.",
                  why_dangerous: "상품 검색에 SQL Injection이 발생하면 전체 DB가 노출될 수 있습니다.",
                  core_summary: "SQL Injection: 사용자 입력은 Parameterized Query로만 처리한다",
                  learning_recommendations: [],
                },
              },
            },
          ],
        },
        status: 200,
      });

    const user = userEvent.setup();
    render(<LearningPage />);

    await user.click(screen.getByRole("button", { name: "예" }));

    expect(await screen.findByText("학습할 이슈를 찾지 못했어요")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "다시 확인하기" }));

    expect(await screen.findByText(/\[SQL Injection\]/)).toBeInTheDocument();
    expect(screen.queryByText("학습할 이슈를 찾지 못했어요")).not.toBeInTheDocument();
    const learnCalls = vi.mocked(m4Api.post).mock.calls.filter(([url]) => url === "/api/learn");
  });
});

describe("LearningPage — 카드 생성 모두 실패 안내", () => {
  afterEach(() => {
    vi.mocked(m4Api.post).mockClear();
    vi.mocked(m4Api.get).mockClear();
  });

  it("issues 전부 status가 failed면 카드별 실패 메시지 대신 안내 문구를 한 번만 표시한다", async () => {
    vi.mocked(m4Api.post).mockResolvedValue({
      data: { scan_id: "scan-1", plan_ids: ["p1", "p2", "p3"] },
      status: 202,
    });
    vi.mocked(m4Api.get).mockResolvedValue({
      data: {
        issues: [
          {
            id: "issue-1",
            keyword: "A",
            severity: "high",
            plan: {
              id: "p1",
              status: "failed",
              llm_fallback: false,
              error_message: "err1",
              card_content: null,
              ragas_reason: null,
              attempt_count: 3,
            },
          },
          {
            id: "issue-2",
            keyword: "B",
            severity: "medium",
            plan: {
              id: "p2",
              status: "failed",
              llm_fallback: false,
              error_message: "err2",
              card_content: null,
              ragas_reason: null,
              attempt_count: 3,
            },
          },
          {
            id: "issue-3",
            keyword: "C",
            severity: "low",
            plan: {
              id: "p3",
              status: "failed",
              llm_fallback: false,
              error_message: "err3",
              card_content: null,
              ragas_reason: null,
              attempt_count: 3,
            },
          },
        ],
      },
      status: 200,
    });

    const user = userEvent.setup();
    render(<LearningPage />);

    await user.click(screen.getByRole("button", { name: "예" }));

    expect(await screen.findByText("카드를 생성하는 중 문제가 발생했어요")).toBeInTheDocument();
    expect(screen.getAllByText("카드를 생성하는 중 문제가 발생했어요")).toHaveLength(1);
  });
});

describe("LearningPage — 학습 시작 실패 안내 (FRONTEND_SPEC Section 8)", () => {
  afterEach(() => {
    vi.mocked(m4Api.post).mockClear();
    vi.mocked(m4Api.get).mockClear();
  });

  it("POST /api/learn이 404를 반환하면 'PR 없음' 안내를 표시하고 로딩 문구를 내린다", async () => {
    vi.mocked(m4Api.post).mockRejectedValueOnce({ isAxiosError: true, response: { status: 404 } });
    const user = userEvent.setup();
    render(<LearningPage />);

    await user.click(screen.getByRole("button", { name: "예" }));

    expect(await screen.findByText(/아직 등록된 PR이 없습니다/)).toBeInTheDocument();
    expect(screen.getByText(/PR을 제출하면 자동으로 코드 리뷰가 진행되고/)).toBeInTheDocument();
    expect(screen.queryByText("학습 카드를 생성하고 있어요...")).not.toBeInTheDocument();
  });

  it("POST /api/learn이 404 외 에러(네트워크 등)로 실패하면 일반 오류 안내를 표시하고 로딩 문구를 내린다", async () => {
    vi.mocked(m4Api.post).mockRejectedValueOnce(new Error("Network Error"));
    const user = userEvent.setup();
    render(<LearningPage />);

    await user.click(screen.getByRole("button", { name: "예" }));

    expect(await screen.findByText("학습 카드를 불러오는 중 문제가 발생했어요")).toBeInTheDocument();
    expect(screen.getByText("잠시 후 다시 시도해주세요")).toBeInTheDocument();
    expect(screen.queryByText("학습 카드를 생성하고 있어요...")).not.toBeInTheDocument();
  });
});

describe("LearningPage — 학습 보류 안내 (아니오 클릭 후 빈 화면, FRONTEND_SPEC Section 1)", () => {
  it("아니오 클릭 시 모달이 닫히고 빈 화면 대신 학습 보류 안내 문구를 표시한다", async () => {
    const user = userEvent.setup();
    render(<LearningPage />);

    await user.click(screen.getByRole("button", { name: "아니오" }));

    expect(screen.getByText("학습은 준비되셨을 때 시작해도 괜찮아요")).toBeInTheDocument();
    expect(screen.getByText("페이지를 새로고침하면 언제든 다시 안내가 떠요")).toBeInTheDocument();
  });
});
