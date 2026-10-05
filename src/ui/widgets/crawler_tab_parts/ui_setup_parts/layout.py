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
        region_open_handler=None,
    ):
        base_init: Any = super().__init__
        base_init(parent)
        self.db = db
        self.history_manager = history_manager
        self.current_theme = theme
        self._maintenance_guard = maintenance_guard
        self.article_open_handler = article_open_handler
        self.region_open_handler = region_open_handler
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
        from src.ui.fluent.design_tokens import SPACE_SM, SPACE_XS

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left panel: scrollable setup sections + an always-visible action bar.
        left_w = QWidget()
        left_w.setMinimumWidth(340)
        left_outer = QVBoxLayout(left_w)
        left_outer.setContentsMargins(0, 0, SPACE_XS, 0)
        left_outer.setSpacing(SPACE_XS)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        scroll_content = QWidget()
        left = QVBoxLayout(scroll_content)
        left.setContentsMargins(0, 0, 0, 0)
        left.setSpacing(SPACE_SM)

        # Primary path top to bottom: what to collect → trade kinds → optional conditions.
        self._setup_complex_list_group(left)
        self._setup_options_group(left)
        self._setup_filter_group(left)
        left.addStretch(0)

        scroll.setWidget(scroll_content)
        left_outer.addWidget(scroll, 1)
        self._setup_action_group(left_outer)
        self.main_splitter.addWidget(left_w)

        # Right Panel (Results)
        right_w = QWidget()
        right = QVBoxLayout(right_w)
        right.setContentsMargins(SPACE_XS, 0, 0, 0)
        right.setSpacing(SPACE_XS)

        self.summary_card = SummaryCard(theme=self.current_theme)
        right.addWidget(self.summary_card)

        self._setup_result_area(right)

        self.main_splitter.addWidget(right_w)
        self.main_splitter.setChildrenCollapsible(False)
        self.main_splitter.setStretchFactor(0, 0)
        self.main_splitter.setStretchFactor(1, 1)
        self.main_splitter.setSizes(self.MAIN_SPLITTER_DEFAULT)
        self.main_splitter.splitterMoved.connect(lambda *_: self._queue_splitter_state_save())
        layout.addWidget(self.main_splitter)

    MAIN_SPLITTER_DEFAULT = [400, 880]

    def _queue_splitter_state_save(self: Any):
        self._splitter_save_timer.start()

    def _save_splitter_state(self: Any):
        if not hasattr(self, "main_splitter"):
            return
        settings.update({"crawler_main_splitter_sizes": list(self.main_splitter.sizes())})

    def _restore_splitter_state(self: Any):
        main_default = list(self.MAIN_SPLITTER_DEFAULT)
        main_sizes = settings.get("crawler_main_splitter_sizes", main_default) or main_default
        try:
            main_values = [max(1, int(v)) for v in main_sizes]
        except (TypeError, ValueError):
            main_values = main_default
        if len(main_values) != 2:
            main_values = main_default
        self.main_splitter.setSizes(main_values)

    def _load_state(self: Any):
        # Load any persisted state if needed
        logger.debug("CrawlerTab 상태 로드 없음 (기본값 사용)")
        self._restore_splitter_state()
        self.update_runtime_settings()
        self._update_advanced_filter_badge()
        from src.ui.styles_parts.surfaces import apply_theme_surfaces

        apply_theme_surfaces(self, getattr(self, "current_theme", "dark"))

    def set_theme(self: Any, theme):
        self.current_theme = theme
        from src.ui.styles_parts.surfaces import apply_theme_surfaces

        apply_theme_surfaces(self, theme)
        if hasattr(self, "summary_card"):
            self.summary_card.set_theme(theme)
        if hasattr(self, "card_view"):
            if hasattr(self.card_view, "set_theme"):
                self.card_view.set_theme(theme)
            else:
                self.card_view.is_dark = str(theme or "dark").strip().lower() != "light"
