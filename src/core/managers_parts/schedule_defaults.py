from __future__ import annotations


DEFAULT_SETTINGS = {
    "theme": "dark", "crawl_speed": "보통", "minimize_to_tray": True,
    "show_notifications": True, "confirm_before_close": True,
    "play_sound_on_complete": True, "default_sort_column": "가격",
    "default_sort_order": "asc", "max_search_history": 20,
    "window_geometry": None, "splitter_sizes": None,
    "crawler_main_splitter_sizes": None,
    "crawler_controls_splitter_sizes": None,
    # v7.3 설정
    "excel_template": None,  # 엑셀 컬럼 템플릿
    "show_new_badge": True,  # 신규 매물 배지 표시
    "show_price_change": True,  # 가격 변동 표시
    "price_change_threshold": 0,  # 가격 변동 알림 기준 (만원, 0=모두)
    # v12.0 설정
    "cache_enabled": True,  # 캐시 사용 여부
    "cache_ttl_minutes": 30,  # 캐시 유효시간 (분)
    "cache_negative_ttl_minutes": 5,  # 0건 결과 캐시 유효시간(분)
    "cache_write_back_interval_sec": 2,  # 캐시 파일 write-back 주기
    "cache_max_entries": 2000,  # 최대 캐시 엔트리 수
    "show_price_per_pyeong": True,  # 평당가 표시
    "track_disappeared": True,  # 매물 소멸 추적
    "visible_columns": None,  # 표시할 컬럼 목록
    # v13.0 신규 설정
    "view_mode": "table",  # table | card (뷰 모드)
    "show_trend_analysis": True,  # 트렌드 분석 표시
    "retry_on_error": True,  # 오류 시 재시도
    "max_retry_count": 3,  # 최대 재시도 횟수
    "recently_viewed_count": 50,  # 최근 본 매물 개수
    "ui_batch_interval_ms": 120,  # UI 배치 반영 주기 (ms)
    "ui_batch_size": 30,  # UI 배치 반영 최대 건수
    "history_batch_size": 200,  # 이력 DB 일괄 반영 크기
    "result_filter_debounce_ms": 220,  # 결과 검색 디바운스
    "max_log_lines": 1500,  # 로그 최대 라인 수
    "startup_lazy_noncritical_tabs": False,  # 레거시 설정키 유지(현재는 대시보드만 첫 진입 시 로드)
    "compact_duplicate_listings": True,  # 동일 매물(가격/평수/층) 묶어서 표시
    "crawl_engine": "playwright",
    "fallback_engine_enabled": True,
    "playwright_headless": True,
    "playwright_detail_workers": 4,
    "playwright_block_heavy_resources": True,
    "playwright_response_drain_timeout_ms": 3000,
    "playwright_navigation_timeout_ms": 15000,
    "playwright_article_api_fast_path": True,
    "playwright_article_api_timeout_ms": 2500,
    "playwright_article_response_wait_ms": 1200,
    "geo_incomplete_safety_mode": True,
    "geo_default_zoom": 15,
    "geo_grid_rings": 1,
    "geo_grid_step_px": 480,
    "geo_sweep_dwell_ms": 600,
    "geo_asset_types": ["APT", "VL"],
    "geo_last_lat": 37.5608,
    "geo_last_lon": 126.9888,
    "schedule_geo_lat": 37.5608,
    "schedule_geo_lon": 126.9888,
    # 수집 옵션 (경량 기본값 — DB 스키마 불변)
    "include_pre_sale_rights": False,  # APT realEstateType 에 :PRE (분양권)
    "detail_enrichment_enabled": True,  # 필터 통과 매물 상세 보강
    "detail_enrichment_max_per_complex": 0,  # 0=무제한, 단지당 상세 상한
    "detail_front_api_enabled": True,  # fin.land front-api 직접 보충
    # HTML 상세 생략·API만 (fin HTML 404 환경에서 권장). 기본 off=자동 degrade.
    "detail_front_api_only": False,
    "article_api_page_delay_ms": 150,  # 목록 API 페이지 간격
    "result_extra_columns": [],  # 결과 테이블 확장 컬럼 id 목록
    "card_show_extra_meta": True,  # 카드에 동/타입명 한 줄
    "schedule_config": {
        "enabled": False,
        "mode": "complex",
        "time": "09:00",
        "group_id": None,
        "last_run_slot": "",
        "last_run_at": "",
        "geo": {
            "lat": 37.5608,
            "lon": 126.9888,
            "zoom": 15,
            "rings": 1,
            "step_px": 480,
            "dwell_ms": 600,
            "asset_types": ["APT", "VL"],
        },
    },
}

DEPRECATED_SETTINGS_KEYS = {"result_tab_mode"}
