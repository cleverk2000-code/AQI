# Indoor AQI (HACS)

기존 PM2.5 센서의 농도를 EPA 2024 AQI 기준으로 실시간 환산하는 로컬 전용 Home Assistant 통합입니다. 공식 24시간 평균 AQI 또는 NowCast가 아닙니다.

## 설치
1. HACS → 사용자 지정 저장소 → https://github.com/cleverk2000-code/AQI → Integration
2. 다운로드 → Home Assistant 재시작
3. 설정 → 기기 및 서비스 → 통합 구성요소 추가 → **Indoor AQI** 검색 → 제출
4. PM2.5 센서별 AQI 및 실내 평균/최고 AQI 센서가 자동 생성됩니다.

Home Assistant 2026.5 이상을 대상으로 합니다. configuration.yaml 수정, 토큰, 외부 연결, 기기 명령이 필요 없습니다. 도메인은 indoor_aqi입니다.

## 동작
- sensor 도메인에서 device_class=pm25 및 µg/m³ (μg/m³, ug/m3 등 동등 단위)를 확인합니다. 특정 제조사나 엔티티 ID를 하드코딩하지 않습니다.
- PM2.5 상태 변경 즉시 환산하며, 30초마다 신규 센서를 자동 감지합니다.
- 원본의 HA 영역/기기명으로 이름을 만들고, 원본 영역이 있으면 생성된 AQI 센서에 영역을 지정합니다. 이미 지정된 영역은 덮어쓰지 않습니다.
- 오류/음수/NaN/무한대/연결 끊김은 unavailable. 평균과 최고는 유효한 센서만 사용하며 모두 무효면 unavailable입니다.
- 평균은 방별 AQI의 단순 산술평균으로, 면적/부피 가중치나 공식 전체 AQI가 아닙니다. 자동 감지는 모든 호환 PM2.5 센서를 대상으로 하므로 실외 센서도 조건에 맞으면 포함됩니다.
- EPA 2024 구간을 적용하고 PM2.5 소수 첫째 자리까지 절삭, AQI 정수 반올림. 대시보드용 500 상한을 적용합니다.
- device_class AQI, state_class measurement. AQI는 무차원입니다. 속성에 category, method, 원본 ID/농도 또는 유효 센서 수를 제공합니다.
- 기존 센서/공기청정기는 수정하지 않습니다. 원본이 삭제되면 생성 센서는 unavailable이며 필요 시 HA에서 삭제 가능합니다. 신규 센서 등록은 최대 30초 후 감지합니다.

## 근거
https://aqs.epa.gov/aqsweb/documents/codetables/aqi_breakpoints.html

## 검증
GitHub Actions에서 계산 및 발견/상태 동기화 테스트를 실행합니다. 실제 사용자 HA 설치 확인은 별도입니다.
