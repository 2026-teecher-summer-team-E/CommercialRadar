"""유명 상권 벨트 큐레이션 정의.

각 벨트는 keywords로 앵커 상권을 매칭하고, seeder가 ST_Intersects로
인접 상권을 자동 확장해 멤버를 채운다. 여기서 벨트를 추가/수정하면
`python -m app.cli seed-belts` 재실행으로 반영된다.

keywords는 commercial_district.district_name에 대한 부분일치(LIKE %kw%)다.
검증(2021-Q1~2025-Q4 매출 성장률)으로 실제 스토리가 나오는 벨트만 넣었다.
"""

from typing import TypedDict


class BeltSeed(TypedDict):
    slug: str
    name: str
    description: str
    anchor_gu: str
    keywords: list[str]


BELT_SEEDS: list[BeltSeed] = [
    {
        "slug": "gyeongbokgung",
        "name": "경복궁 역사문화 벨트",
        "description": "광화문·경복궁을 중심으로 서촌·북촌·삼청동·인사동이 이어지는 역사문화 관광 축. 성장 동력이 종로 대로변에서 북촌·서촌 문화상권으로 북상 중.",
        "anchor_gu": "종로구",
        "keywords": ["광화문", "경복궁", "삼청", "북촌", "인사동", "서촌"],
    },
    {
        "slug": "hongdae",
        "name": "홍대 문화 벨트",
        "description": "홍대입구를 중심으로 연남·상수·합정·망원으로 확산되는 청년 문화상권 축. 코어에서 골목상권으로 매출이 서진(西進)하며 확산 중.",
        "anchor_gu": "마포구",
        "keywords": ["홍대", "연남", "상수", "합정", "망원"],
    },
    {
        "slug": "seongsu",
        "name": "성수 재생 벨트",
        "description": "성수동 카페거리·서울숲·뚝섬을 잇는 도시재생 신흥 상권 축. 카페거리·서울숲으로 매출이 폭발적으로 쏠리는 서울 최고 성장기 벨트.",
        "anchor_gu": "성동구",
        "keywords": ["성수", "서울숲", "뚝섬"],
    },
    {
        "slug": "gangnam",
        "name": "강남 업무 벨트",
        "description": "강남역·역삼·선릉·삼성을 잇는 서울 최대 업무·상업 축. 절대 규모는 서울 최대지만 성장 모멘텀은 낮은 성숙 상권.",
        "anchor_gu": "강남구",
        "keywords": ["강남역", "역삼", "선릉", "삼성역", "논현"],
    },
]
