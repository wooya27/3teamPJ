import type { GraphEdge, GraphLayer, GraphNode } from "@/types/graphPipeline";

export interface LayoutPosition {
  x: number;
  y: number;
}

// ── 상수 ─────────────────────────────────────────────────────────────────────

const LAYER_ORDER: GraphLayer[] = ["L1", "L2", "L3", "L4"];

const LAYER_HEIGHT      = 220;   // 레이어 간 수직 간격
const ROOT_SPACING      = 360;   // L1 루트 노드 간격
const CHILD_SPACING     = 90;    // 자식 노드 기본 수평 간격
const STAGGER_OFFSET    = 30;    // 단일 행 교번 Y 오프셋

// Two-tier: 노드가 TWO_TIER_THRESHOLD 초과이면 두 줄로 배치
const TWO_TIER_THRESHOLD = 7;
const TWO_TIER_GAP       = 85;   // 두 번째 행 추가 Y 오프셋

// Cluster: 노드가 CLUSTER_THRESHOLD 초과이면 클러스터 분산 배치
const CLUSTER_THRESHOLD  = 20;
const CLUSTER_SIZE       = 8;
const CLUSTER_SPACING    = 310;

// 최소 거리 제약
const MIN_NODE_DIST  = 68;   // 같은 Y 밴드 내 최소 X 거리
const DIST_PASSES    = 10;   // pushout 반복 횟수

function layerDepth(layer?: GraphLayer): number {
  const index = LAYER_ORDER.indexOf(layer ?? "L2");
  return index < 0 ? 1 : index;
}

/**
 * 단일 행 staggered 배치 — 자식 수 ≤ TWO_TIER_THRESHOLD 에 사용.
 * 홀수/짝수 인덱스를 ±STAGGER_OFFSET 으로 교번 배치한다.
 */
function layoutSingleTier(
  centerX: number,
  baseY: number,
  children: GraphNode[],
  positions: Map<string, LayoutPosition>
): void {
  const totalWidth = (children.length - 1) * CHILD_SPACING;
  children.forEach((child, idx) => {
    const x = centerX - totalWidth / 2 + idx * CHILD_SPACING;
    const stagger = idx % 2 === 0 ? -STAGGER_OFFSET : STAGGER_OFFSET;
    positions.set(child.id, { x, y: baseY + stagger });
  });
}

/**
 * Two-tier bipartite 배치 — TWO_TIER_THRESHOLD < 자식 수 ≤ CLUSTER_THRESHOLD.
 *
 * 짝수 인덱스(0,2,4…) → Tier 1 (baseY)
 * 홀수 인덱스(1,3,5…) → Tier 2 (baseY + TWO_TIER_GAP), X를 half-step 오프셋
 *
 * 시각적 결과:
 *   Tier 1:  O     O     O     O
 *   Tier 2:     O     O     O
 */
function layoutTwoTier(
  centerX: number,
  baseY: number,
  children: GraphNode[],
  positions: Map<string, LayoutPosition>
): void {
  const tier1 = children.filter((_, i) => i % 2 === 0);
  const tier2 = children.filter((_, i) => i % 2 !== 0);

  const t1Half = ((tier1.length - 1) * CHILD_SPACING) / 2;
  tier1.forEach((node, idx) => {
    positions.set(node.id, {
      x: centerX - t1Half + idx * CHILD_SPACING,
      y: baseY,
    });
  });

  const t2Half = ((tier2.length - 1) * CHILD_SPACING) / 2;
  tier2.forEach((node, idx) => {
    positions.set(node.id, {
      x: centerX - t2Half + idx * CHILD_SPACING + CHILD_SPACING / 2,
      y: baseY + TWO_TIER_GAP,
    });
  });
}

/**
 * Cluster + Two-tier 혼합 배치 — 자식 수 > CLUSTER_THRESHOLD.
 * 소그룹(클러스터)마다 Two-tier 배치를 적용한다.
 */
function layoutClustered(
  centerX: number,
  baseY: number,
  children: GraphNode[],
  positions: Map<string, LayoutPosition>
): void {
  const clusterCount = Math.ceil(children.length / CLUSTER_SIZE);
  const totalClusterWidth = (clusterCount - 1) * CLUSTER_SPACING;

  for (let ci = 0; ci < clusterCount; ci++) {
    const group = children.slice(ci * CLUSTER_SIZE, (ci + 1) * CLUSTER_SIZE);
    const clusterCenterX = centerX - totalClusterWidth / 2 + ci * CLUSTER_SPACING;
    layoutTwoTier(clusterCenterX, baseY, group, positions);
  }
}

/**
 * 같은 Y 밴드(±threshold px) 안에 있는 노드들 사이의 최소 X 거리를 보장한다.
 * X 기준 정렬 후 인접 노드를 pushout 하는 방식으로 DIST_PASSES 회 반복한다.
 */
function applyMinDistanceConstraint(
  nodes: GraphNode[],
  positions: Map<string, LayoutPosition>
): void {
  const Y_BAND = TWO_TIER_GAP * 0.6;

  const bands = new Map<number, GraphNode[]>();
  for (const n of nodes) {
    const pos = positions.get(n.id);
    if (!pos) continue;
    let found: number | null = null;
    for (const bandY of bands.keys()) {
      if (Math.abs(pos.y - bandY) <= Y_BAND) { found = bandY; break; }
    }
    const key = found ?? pos.y;
    const list = bands.get(key) ?? [];
    list.push(n);
    bands.set(key, list);
  }

  for (const group of bands.values()) {
    if (group.length < 2) continue;
    for (let pass = 0; pass < DIST_PASSES; pass++) {
      group.sort((a, b) => (positions.get(a.id)?.x ?? 0) - (positions.get(b.id)?.x ?? 0));
      let moved = false;
      for (let i = 0; i < group.length - 1; i++) {
        const posA = positions.get(group[i].id)!;
        const posB = positions.get(group[i + 1].id)!;
        const gap = posB.x - posA.x;
        if (gap < MIN_NODE_DIST) {
          const push = (MIN_NODE_DIST - gap) / 2;
          positions.set(group[i].id,     { ...posA, x: posA.x - push });
          positions.set(group[i + 1].id, { ...posB, x: posB.x + push });
          moved = true;
        }
      }
      if (!moved) break;
    }
  }
}

/**
 * 노드의 layer(깊이)와 edges 부모-자식 관계를 바탕으로 계층형 좌표를 계산한다.
 *
 * - 자식 수 ≤ TWO_TIER_THRESHOLD   → 단일 행 staggered 배치
 * - 자식 수 ≤ CLUSTER_THRESHOLD    → Two-tier bipartite 배치
 * - 자식 수 > CLUSTER_THRESHOLD    → Cluster + Two-tier 혼합 배치
 * - 이후 최소 거리 제약(pushout) 적용으로 겹침 제거
 */
export function computeHierarchicalLayout(
  nodes: GraphNode[],
  edges: GraphEdge[]
): Map<string, LayoutPosition> {
  const positions = new Map<string, LayoutPosition>();
  if (nodes.length === 0) return positions;

  const nodesById = new Map(nodes.map((n) => [n.id, n]));
  const childrenOf = new Map<string, string[]>();

  for (const e of edges) {
    const a = nodesById.get(e.source);
    const b = nodesById.get(e.target);
    if (!a || !b) continue;
    const da = layerDepth(a.layer);
    const db = layerDepth(b.layer);
    if (db - da === 1) {
      const list = childrenOf.get(a.id) ?? [];
      if (!list.includes(b.id)) list.push(b.id);
      childrenOf.set(a.id, list);
    } else if (da - db === 1) {
      const list = childrenOf.get(b.id) ?? [];
      if (!list.includes(a.id)) list.push(a.id);
      childrenOf.set(b.id, list);
    }
  }

  const depths = nodes.map((n) => layerDepth(n.layer));
  const minDepth = Math.min(...depths);
  const maxDepth = Math.max(...depths);

  // L1 루트 배치
  const roots = nodes.filter((n) => layerDepth(n.layer) === minDepth);
  roots.forEach((root, i) => {
    positions.set(root.id, {
      x: (i - (roots.length - 1) / 2) * ROOT_SPACING,
      y: 0,
    });
  });

  // 각 depth → 자식 배치 (미배치 노드만)
  for (let depth = minDepth; depth < maxDepth; depth++) {
    const parents = nodes.filter(
      (n) => layerDepth(n.layer) === depth && positions.has(n.id)
    );
    for (const parent of parents) {
      const parentPos = positions.get(parent.id)!;
      const children = (childrenOf.get(parent.id) ?? [])
        .map((id) => nodesById.get(id))
       .filter((n): n is GraphNode => n != null && !positions.has(n.id));
      if (children.length === 0) continue;

      const childY = (depth + 1 - minDepth) * LAYER_HEIGHT;
      if (children.length <= TWO_TIER_THRESHOLD) {
        layoutSingleTier(parentPos.x, childY, children, positions);
      } else if (children.length <= CLUSTER_THRESHOLD) {
        layoutTwoTier(parentPos.x, childY, children, positions);
      } else {
        layoutClustered(parentPos.x, childY, children, positions);
      }
    }
  }

  // 고아 노드 배치
  let orphanIndex = 0;
  for (const n of nodes) {
    if (positions.has(n.id)) continue;
    const y = (layerDepth(n.layer) - minDepth) * LAYER_HEIGHT;
    const stagger = orphanIndex % 2 === 0 ? -STAGGER_OFFSET : STAGGER_OFFSET;
    positions.set(n.id, { x: orphanIndex * CHILD_SPACING, y: y + stagger });
    orphanIndex += 1;
  }

  // 최소 거리 제약 (pushout)
  applyMinDistanceConstraint(nodes, positions);

  return positions;
}
