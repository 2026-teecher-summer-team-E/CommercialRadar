import { useState } from "react";
import { AxiosError } from "axios";
import { apiClient } from "../../lib/apiClient";
import styles from "./ingestion.module.css";

/** 인제스천 대상. 백엔드 jobs.py JOBS + admin.py DataIngestionRequest 와 일치. */
const TARGETS: { value: string; name: string; hint: string }[] = [
  { value: "all", name: "all", hint: "아래 전체 대상을 순차 실행" },
  { value: "seoul_commercial", name: "seoul_commercial", hint: "서울 상권 영역" },
  { value: "seoul_population", name: "seoul_population", hint: "유동인구 (시계열 + 히트맵)" },
  { value: "seoul_business", name: "seoul_business", hint: "업종 (분기별 백필)" },
  { value: "seoul_foreign", name: "seoul_foreign", hint: "외국인 유동인구" },
  { value: "seoul_rent", name: "seoul_rent", hint: "R-ONE 임대료" },
];

type ResultState =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "ok"; message: string }
  | { kind: "err"; message: string };

/** 데이터 인제스천 수동 트리거 콘솔. POST /admin/data (헤더 X-Admin-Key). */
export default function IngestionConsole() {
  const [target, setTarget] = useState<string>("all");
  const [adminKey, setAdminKey] = useState<string>("");
  const [result, setResult] = useState<ResultState>({ kind: "idle" });

  const loading = result.kind === "loading";

  const handleRun = () => {
    if (loading) return;
    setResult({ kind: "loading" });
    apiClient
      .post(
        "/admin/data",
        { targets: [target] },
        { headers: { "X-Admin-Key": adminKey } },
      )
      .then((res) => {
        // 백엔드는 BackgroundTasks 로 던지고 즉시 {status: "accepted"} 반환.
        setResult({
          kind: "ok",
          message: `요청이 접수되었습니다 (${res.status}). 대상: ${target}. 실행 결과/이력은 ingestion_run 테이블에서 확인하세요.`,
        });
      })
      .catch((err: unknown) => {
        const status =
          err instanceof AxiosError ? err.response?.status : undefined;
        if (status === 403 || status === 401) {
          setResult({
            kind: "err",
            message:
              "관리자 키가 올바르지 않습니다 (인증 실패). X-Admin-Key 값을 확인하세요. ENV=dev 여도 이 인증은 우회되지 않습니다.",
          });
        } else {
          setResult({
            kind: "err",
            message: `요청에 실패했습니다${status ? ` (${status})` : ""}. 잠시 후 다시 시도해 주세요.`,
          });
        }
      });
  };

  return (
    <section className={styles.console}>
      <div className={styles.consoleHead}>
        <h2 className={styles.consoleTitle}>데이터 인제스천</h2>
        <p className={styles.consoleDesc}>
          크론과 동일한 수집 파이프라인을 수동으로 트리거합니다. 오래 걸릴 수
          있어 백그라운드로 실행되고 즉시 응답합니다.
        </p>
      </div>

      {/* 대상 선택 */}
      <div className={styles.field}>
        <span className={styles.fieldLabel}>인제스천 대상</span>
        <div className={styles.targetGrid}>
          {TARGETS.map((t) => {
            const active = target === t.value;
            return (
              <label
                key={t.value}
                className={`${styles.targetItem} ${active ? styles.targetItemActive : ""}`}
              >
                <input
                  type="radio"
                  name="ingest-target"
                  className={styles.targetRadio}
                  value={t.value}
                  checked={active}
                  onChange={() => setTarget(t.value)}
                />
                <span className={styles.targetText}>
                  <span className={styles.targetName}>{t.name}</span>
                  <span className={styles.targetHint}>{t.hint}</span>
                </span>
              </label>
            );
          })}
        </div>
      </div>

      {/* 관리자 키 */}
      <div className={styles.field}>
        <label className={styles.fieldLabel} htmlFor="admin-key">
          관리자 키 (X-Admin-Key)
        </label>
        <input
          id="admin-key"
          type="password"
          className={styles.keyInput}
          value={adminKey}
          onChange={(e) => setAdminKey(e.target.value)}
          placeholder="관리자 키를 입력하세요"
          autoComplete="off"
        />
        <span className={styles.keyNote}>
          키는 이 화면의 상태에만 보관되며 저장되거나 기록되지 않습니다.
        </span>
      </div>

      {/* 실행 */}
      <div className={styles.actions}>
        <button
          type="button"
          className={styles.runBtn}
          onClick={handleRun}
          disabled={loading || adminKey.length === 0}
        >
          {loading ? "실행 중…" : "인제스천 실행"}
        </button>
      </div>

      {/* 결과 */}
      {result.kind === "loading" && (
        <div className={`${styles.result} ${styles.resultMuted}`}>
          요청을 전송하는 중…
        </div>
      )}
      {result.kind === "ok" && (
        <div className={`${styles.result} ${styles.resultOk}`}>
          {result.message}
        </div>
      )}
      {result.kind === "err" && (
        <div className={`${styles.result} ${styles.resultErr}`}>
          {result.message}
        </div>
      )}
    </section>
  );
}
