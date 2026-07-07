# alembic/

데이터베이스 스키마 변경 이력(마이그레이션)을 관리하는 곳입니다.

모델(`models/`)을 수정한 뒤 실제 DB에 반영할 때 Alembic을 사용합니다.

## 기본 사용법

```bash
# 가상환경 활성화 후 backend/ 폴더에서 실행

# 모델 변경사항을 감지해 마이그레이션 파일 자동 생성
alembic revision --autogenerate -m "변경 내용 설명"

# 최신 버전으로 DB 적용
alembic upgrade head

# 이전 버전으로 롤백
alembic downgrade -1

# 현재 적용된 버전 확인
alembic current
```

## 폴더 구조

```
alembic/
├── env.py          # 마이그레이션 실행 환경 설정 (models/ 전체를 감지하도록 설정됨)
└── versions/       # 자동 생성된 마이그레이션 파일들이 쌓이는 곳
```

## 주의사항

- `versions/`의 `.py` 파일들은 반드시 git에 커밋해야 팀원 모두가 동일한 DB 구조를 유지할 수 있습니다
- 마이그레이션 파일을 직접 수정하지 마세요 (필요하면 새 revision 생성)
- 프로덕션 DB에 `upgrade`하기 전 반드시 내용을 검토하세요
