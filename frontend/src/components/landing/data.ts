/** 랜딩 페이지 정적 데이터 (랜딩은 정적이므로 하드코딩). */

export const POPULAR_SEARCHES = ["성수동", "홍대입구", "을지로", "강남역", "연남동"];

export interface FeatureCard {
  title: string;
  description: string;
  items: string[];
}

export const FEATURE_CARDS: FeatureCard[] = [
  {
    title: "유동인구 분석",
    description: "요일·시간·성별·연령별 인구 흐름을 히트맵으로 직관적으로 확인합니다.",
    items: ["시간대별 혼잡도 지도", "성별·연령대 인구 구성", "피크타임 자동 감지"],
  },
  {
    title: "매출 & 경쟁도",
    description: "주변 동종 업종 매출 추이와 폐업률로 시장 포화도를 미리 파악합니다.",
    items: ["동종 업종 생존율 3년 추이", "반경 내 경쟁점 밀도 분석", "임대료 대비 수익성 지수"],
  },
  {
    title: "트렌드 리포트",
    description: "이달의 뜨는 상권과 지는 상권을 비교해 최적의 진입 타이밍을 포착합니다.",
    items: ["월별 상권 성장률 순위", "업종 트렌드 예보", "PDF 리포트 자동 생성"],
  },
];

export interface RankItem {
  name: string;
  sub: string;
  delta: string;
}

export const RISING_DISTRICTS: RankItem[] = [
  { name: "성수동 카페거리", sub: "성동구", delta: "+42%" },
  { name: "망원·합정 상권", sub: "마포구", delta: "+28%" },
  { name: "을지로 3가", sub: "중구", delta: "+19%" },
  { name: "한남·이태원", sub: "용산구", delta: "+12%" },
  { name: "익선동 골목", sub: "종로구", delta: "+8%" },
];

export const TREND_INDUSTRIES: Omit<RankItem, "sub">[] = [
  { name: "무인 사진관", delta: "+38%" },
  { name: "저가 커피", delta: "+31%" },
  { name: "비건 레스토랑", delta: "+24%" },
  { name: "셀프 네일샵", delta: "+18%" },
  { name: "반려동물 용품", delta: "+15%" },
];

export interface ReportItem {
  title: string;
  meta: string;
  hot?: boolean;
}

export const LATEST_REPORTS: ReportItem[] = [
  { title: "2026년 하반기 수도권 핵심 상권 분석", meta: "2026.07.01 · 48p", hot: true },
  { title: "서울시 카페 업종 생존율 심층 리포트", meta: "2026.06.15 · 32p" },
  { title: "MZ 세대 소비 패턴과 뜨는 상권 입지", meta: "2026.06.01 · 27p" },
];

export interface AudienceCard {
  tag: string;
  title: string;
  description: string;
  cta: string;
  to: string;
}

export const AUDIENCE_CARDS: AudienceCard[] = [
  {
    tag: "예비 창업자",
    title: "내 자본에 맞는 추천 상권 찾기",
    description: "예산과 업종을 입력하면 생존율이 높은 입지를 AI가 자동 추천합니다.",
    cta: "상권 추천받기",
    to: "/",
  },
  {
    tag: "기존 소상공인",
    title: "우리 매장 주변 경쟁점 분석하기",
    description: "현 매장 위치 기반으로 반경 내 동종 업종 현황과 고객 유입 패턴을 분석합니다.",
    cta: "경쟁 분석 시작",
    to: "/compare",
  },
  {
    tag: "기업 / 프랜차이즈",
    title: "프랜차이즈 출점 전략 솔루션",
    description: "다수 후보지 데이터 일괄 분석, 경쟁사 출점 현황, 상권 성장성을 종합 리포트로 제공합니다.",
    cta: "솔루션 문의하기",
    to: "/compare",
  },
];

export interface StatItem {
  value: string;
  label: string;
  note: string;
}

export const STATS: StatItem[] = [
  { value: "150,000건+", label: "누적 분석 건수", note: "공공데이터 기반 · 2026.06 기준" },
  { value: "50,000명+", label: "활용 회원 수", note: "공공데이터 기반 · 2026.06 기준" },
  { value: "424개", label: "총 행정동 수", note: "공공데이터 기반 · 2026.06 기준" },
];

export const DATA_PARTNERS = [
  "통신사 유동인구",
  "카드사 매출",
  "행안부 공공데이터",
  "국토교통부",
  "서울 열린데이터광장",
  "소상공인시장진흥공단",
];
