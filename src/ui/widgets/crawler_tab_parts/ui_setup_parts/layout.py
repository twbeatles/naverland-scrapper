from __future__ import annotations

from typing import Any, TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from src.ui.widgets.crawler_tab import *  # noqa: F403


FavoriteKey = tuple[str, str, str]
FavoriteKeyProvider = Callable[[], set[FavoriteKey]]
CompactRowKey = tuple[str, str, str, str, str, float, str]
RowPayload = dict[str, Any]
ResultRow = dict[str, Any]


class CrawlerTabLayoutSetupMixin:
    if TYPE_CHECKING:
        def __getattr__(self: Any, name: str) -> Any: ...

    def __init__(
        self: Any,
        db,
        history_manager=None,
        theme="dark",
        parent=None,
        maintenance_guard=None,
        article_open_handler=None,
    ):
        base_init: Any = super().__init__
        base_init(parent)
        self.db = db
        self.history_manager = history_manager
        self.current_theme = theme
        self._maintenance_guard = maintenance_guard
        self.article_open_handler = article_open_handler
        self.crawler_thread: Any | None = None
        self.crawl_cache: Any | None = None
        self.collected_data: list[ResultRow] = []
        self.grouped_rows: dict[str, Any] = {}
        self._pending_search_text: str = ""
        self._row_search_cache: list[str] = []
        self._row_payload_cache: list[RowPayload] = []
        self._row_hidden_state: dict[int, bool] = {}
        self._advanced_filters: dict[str, Any] | None = None
        self._append_chunk_size: int = 200
        self._compact_duplicates: bool = bool(settings.get("compact_duplicate_listings", True))
        self._compact_items_by_key: dict[CompactRowKey, ResultRow] = {}
        self._compact_rows_data: list[ResultRow] = []
        self._compact_row_index_by_key: dict[CompactRowKey, int] = {}
        self._compact_source_keys_by_key: dict[CompactRowKey, set[FavoriteKey]] = {}
        self._compact_key_by_article: dict[FavoriteKey, set[CompactRowKey]] = {}
        self._compact_dirty_keys: set[CompactRowKey] = set()
        self._compact_full_refresh_pending: bool = False
        self._card_refresh_pending: bool = False
        self.favorite_keys_provider: FavoriteKeyProvider | None = None
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        try:
            debounce_ms = max(80, int(settings.get("result_filter_debounce_ms", 220)))
        except (TypeError, ValueError):
            debounce_ms = 220
        self._search_timer.setInterval(debounce_ms)
        self._search_timer.timeout.connect(self._apply_search_filter)
        self._compact_refresh_timer = QTimer(self)
        self._compact_refresh_timer.setSingleShot(True)
        self._compact_refresh_timer.setInterval(60)
        self._compact_refresh_timer.timeout.connect(self._flush_compact_updates)
        self._card_refresh_timer = QTimer(self)
        self._card_refresh_timer.setSingleShot(True)
        self._card_refresh_timer.setInterval(180)
        self._card_refresh_timer.timeout.connect(self._flush_card_view_refresh)
        self._splitter_save_timer = QTimer(self)
        self._splitter_save_timer.setSingleShot(True)
        self._splitter_save_timer.setInterval(250)
        self._splitter_save_timer.timeout.connect(self._save_splitter_state)
        
        # UI Setup
        self._init_ui()
        self._load_state()

    def _init_ui(self: Any):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Left Panel (Controls)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setMinimumWidth(400)
        scroll.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        scroll_content = QWidget()
        left = QVBoxLayout(scroll_content)
        left.setContentsMargins(6, 6, 6, 6)
        left.setSpacing(6)

        self.controls_splitter = QSplitter(Qt.Orientation.Vertical)
        self.controls_splitter.setChildrenCollapsible(False)
        self.controls_splitter.setHandleWidth(6)

        def _section(setup_fn):
            section = QWidget()
            section_layout = QVBoxLayout(section)
            section_layout.setContentsMargins(0, 0, 0, 0)
            section_layout.setSpacing(0)
            setup_fn(section_layout)
            section_layout.addStretch(1)
            return section

        self.controls_splitter.addWidget(_section(self._setup_options_group))
        self.controls_splitter.addWidget(_section(self._setup_filter_group))
        self.controls_splitter.addWidget(_section(self._setup_complex_list_group))
        self.controls_splitter.addWidget(_section(self._setup_speed_group))
        self.controls_splitter.addWidget(_section(self._setup_action_group))
        left.addWidget(self.controls_splitter, 1)

        scroll.setWidget(scroll_content)
        self.main_splitter.addWidget(scroll)
        
        # Right Panel (Results)
        right_w = QWidget()
        right = QVBoxLayout(right_w)
        right.setContentsMargins(6, 6, 6, 6)
        right.setSpacing(8)
        
        self.summary_card = SummaryCard(theme=self.current_theme)
        right.addWidget(self.summary_card)
        
        self._setup_result_area(right)
        
        self.main_splitter.addWidget(right_w)
        self.main_splitter.setChildrenCollapsible(False)
        self.main_splitter.setStretchFactor(0, 0)
        self.main_splitter.setStretchFactor(1, 1)
        self.main_splitter.setSizes([440, 880])
        self.main_splitter.splitterMoved.connect(lambda *_: self._queue_splitter_state_save())
        self.controls_splitter.splitterMoved.connect(lambda *_: self._queue_splitter_state_save())
        layout.addWidget(self.main_splitter)

    def _queue_splitter_state_save(self: Any):
        self._splitter_save_timer.start()

    def _save_splitter_state(self: Any):
        if not hasattr(self, "main_splitter") or not hasattr(self, "controls_splitter"):
            return
        settings.update(
            {
                "crawler_main_splitter_sizes": list(self.main_splitter.sizes()),
                "crawler_controls_splitter_sizes": list(self.controls_splitter.sizes()),
            }
        )

    def _restore_splitter_state(self: Any):
        main_default = [520, 880]
        control_count = int(getattr(self.controls_splitter, "count", lambda: 0)())
        control_default = [170, 300, 340, 140, 120]
        if control_count != len(control_default):
            control_default = [1 for _ in range(max(control_count, 1))]

        main_sizes = settings.get("crawler_main_splitter_sizes", main_default) or main_default
        control_sizes = settings.get("crawler_controls_splitter_sizes", control_default) or control_default
        try:
            main_values = [max(1, int(v)) for v in main_sizes]
        except (TypeError, ValueError):
            main_values = main_default
        try:
            control_values = [max(1, int(v)) for v in control_sizes]
        except (TypeError, ValueError):
            control_values = control_default

        if len(main_values) != 2:
            main_values = main_default
        if len(control_values) != control_count:
            control_values = control_default

        self.main_splitter.setSizes(main_values)
        self.controls_splitter.setSizes(control_values)

    def _load_state(self: Any):
        # Load any persisted state if needed
        logger.debug("CrawlerTab 상태 로드 없음 (기본값 사용)")
        self._restore_splitter_state()
        self.update_runtime_settings()
        self._update_advanced_filter_badge()

    def set_theme(self: Any, theme):
        self.current_theme = theme
        if hasattr(self, 'summary_card'):
            self.summary_card.set_theme(theme)
        if hasattr(self, 'card_view'):
            self.card_view.is_dark = (theme == "dark")
