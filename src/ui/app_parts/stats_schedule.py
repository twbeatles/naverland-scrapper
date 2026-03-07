from __future__ import annotations


class AppStatsScheduleMixin:
    def _load_schedule_groups(self):
        self.schedule_group_combo.clear()
        for gid, name, _ in self.db.get_all_groups():
            self.schedule_group_combo.addItem(name, gid)
        self._update_schedule_state()
    
    def _check_schedule(self):
        if not self.check_schedule.isChecked(): return
        if self.schedule_group_combo.count() == 0: return
        now = QTime.currentTime()
        target = self.time_edit.time()
        
        # 분 단위 비교
        if now.hour() == target.hour() and now.minute() == target.minute():
            if not self.is_scheduled_run:
                self.is_scheduled_run = True
                self._run_scheduled()
        else:
            self.is_scheduled_run = False
    
    def _run_scheduled(self):
        gid = self.schedule_group_combo.currentData()
        if gid:
            if hasattr(self, 'crawler_tab'):
                running_thread = getattr(self.crawler_tab, "crawler_thread", None)
                if running_thread and running_thread.isRunning():
                    self.status_bar.showMessage("⏸ 예약 작업 건너뜀: 현재 크롤링이 실행 중입니다.")
                    ui_logger.info("예약 작업 스킵: 현재 크롤러 실행 중")
                    return

                # 탭 전환
                self.tabs.setCurrentWidget(self.crawler_tab)
                
                # CrawlerTab 초기화 및 데이터 로드
                self.crawler_tab.clear_tasks()
                for _, name, _asset_type, cid, _ in self.db.get_complexes_in_group(gid):
                    self.crawler_tab.add_task(name, cid)
                
                # 크롤링 시작
                self.crawler_tab.start_crawling()
                self.status_bar.showMessage(f"⏰ 예약 작업 시작: 그룹 {gid}")


    def _update_group_empty_state(self):
        has_groups = self.group_list.count() > 0
        if hasattr(self, "group_empty_label"):
            self.group_empty_label.setVisible(not has_groups)
        self.group_list.setEnabled(has_groups)
        if not has_groups:
            self.group_complex_table.setRowCount(0)
            self._update_group_complex_empty_state(0)

    def _update_group_action_state(self):
        has_selection = self.group_list.currentRow() >= 0
        has_groups = self.group_list.count() > 0
        if hasattr(self, "group_btn_delete"):
            self.group_btn_delete.setEnabled(has_selection)
        if hasattr(self, "group_btn_add"):
            self.group_btn_add.setEnabled(has_groups)
        if hasattr(self, "group_btn_add_multi"):
            self.group_btn_add_multi.setEnabled(has_groups)
        if not has_groups:
            if hasattr(self, "group_btn_remove"):
                self.group_btn_remove.setEnabled(False)

    def _update_group_complex_empty_state(self, count):
        is_empty = count == 0
        if hasattr(self, "group_complex_empty_label"):
            self.group_complex_empty_label.setVisible(is_empty)
        self.group_complex_table.setEnabled(not is_empty)

    def _update_group_complex_action_state(self):
        has_selection = self.group_complex_table.currentRow() >= 0
        if hasattr(self, "group_btn_remove"):
            self.group_btn_remove.setEnabled(has_selection)

    def _update_schedule_state(self):
        has_groups = self.schedule_group_combo.count() > 0
        self.check_schedule.setEnabled(has_groups)
        self.time_edit.setEnabled(has_groups)
        self.schedule_group_combo.setEnabled(has_groups)
        if hasattr(self, "schedule_empty_label"):
            self.schedule_empty_label.setVisible(not has_groups)
    
    # History Tab handlers
    def _load_history(self):
        self.history_table.setUpdatesEnabled(False)
        try:
            self.history_table.setRowCount(0)
            history = self.db.get_crawl_history()
            self.history_table.setRowCount(len(history))
            for row, (name, cid, ttype, cnt, date) in enumerate(history):
                self.history_table.setItem(row, 0, QTableWidgetItem(name))
                self.history_table.setItem(row, 1, QTableWidgetItem(cid))
                self.history_table.setItem(row, 2, QTableWidgetItem(ttype))
                self.history_table.setItem(row, 3, QTableWidgetItem(str(cnt)))
                self.history_table.setItem(row, 4, QTableWidgetItem(date))
        finally:
            self.history_table.setUpdatesEnabled(True)

    @staticmethod
    def _parse_pyeong_value(value):
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        text = str(value).strip().replace(",", "")
        if not text:
            return None
        text = text.replace("평", "")
        match = re.search(r"-?\d+(?:\.\d+)?", text)
        if not match:
            return None
        try:
            return float(match.group(0))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _format_pyeong_value(value):
        try:
            return f"{float(value):g}"
        except (TypeError, ValueError):
            return str(value)

    # Stats Tab handlers
    def _load_stats_complexes(self):
        current_cid = self.stats_complex_combo.currentData()
        self.stats_complex_combo.blockSignals(True)
        try:
            self.stats_complex_combo.clear()
            complexes = self.db.get_complexes_for_stats()
            for name, cid in complexes:
                self.stats_complex_combo.addItem(f"{name}", cid)
            if current_cid:
                idx = self.stats_complex_combo.findData(current_cid)
                if idx >= 0:
                    self.stats_complex_combo.setCurrentIndex(idx)
            if self.stats_complex_combo.count() > 0 and self.stats_complex_combo.currentIndex() < 0:
                self.stats_complex_combo.setCurrentIndex(0)
        except Exception as e:
            ui_logger.warning(f"통계 단지 목록 로드 실패: {e}")
        finally:
            self.stats_complex_combo.blockSignals(False)
    
    def _load_stats(self):
        cid = self.stats_complex_combo.currentData()
        if not cid:
            return
        ttype = self.stats_type_combo.currentText()
        if ttype == "전체": ttype = None

        pyeong = self.stats_pyeong_combo.currentData()
        if pyeong is None:
            pyeong_text = self.stats_pyeong_combo.currentText()
            if pyeong_text != "전체":
                pyeong = self._parse_pyeong_value(pyeong_text)
                if pyeong is None:
                    ui_logger.warning(f"평형 파싱 실패: {pyeong_text}")

        snapshots = self.db.get_price_snapshots(cid, ttype)
        if pyeong is not None:
            filtered = []
            for s in snapshots:
                py = self._parse_pyeong_value(s[2] if len(s) > 2 else None)
                if py is not None and abs(py - float(pyeong)) <= 1e-6:
                    filtered.append(s)
            snapshots = filtered

        self.stats_table.setUpdatesEnabled(False)
        chart_data = {"date": [], "avg": [], "min": [], "max": [], "type": None, "py": None}
        try:
            self.stats_table.setRowCount(0)
            self.stats_table.setRowCount(len(snapshots))
            # 차트용 데이터 수집
            for row, (date, typ, py, min_p, max_p, avg_p, cnt) in enumerate(snapshots):
                parsed_py = self._parse_pyeong_value(py)
                py_text = (
                    f"{self._format_pyeong_value(parsed_py)}평"
                    if parsed_py is not None
                    else f"{py}평"
                )
                self.stats_table.setItem(row, 0, QTableWidgetItem(date))
                self.stats_table.setItem(row, 1, QTableWidgetItem(typ))
                self.stats_table.setItem(row, 2, QTableWidgetItem(py_text))
                self.stats_table.setItem(row, 3, SortableTableWidgetItem(str(min_p)))
                self.stats_table.setItem(row, 4, SortableTableWidgetItem(str(max_p)))
                self.stats_table.setItem(row, 5, SortableTableWidgetItem(str(avg_p)))
                
                # 같은 유형/평형만 차트에 표시 (첫 번째 데이터 기준)
                same_series = (
                    chart_data["type"] == typ
                    and chart_data["py"] == parsed_py
                )
                if parsed_py is not None and (not chart_data["date"] or same_series):
                    chart_data["type"] = typ
                    chart_data["py"] = parsed_py
                    chart_data["date"].append(date)
                    chart_data["avg"].append(avg_p)
                    chart_data["min"].append(min_p)
                    chart_data["max"].append(max_p)
        finally:
            self.stats_table.setUpdatesEnabled(True)
        
        # 차트 업데이트
        if chart_data["date"]:
            self._ensure_chart_widget()
            title = (
                f"{self.stats_complex_combo.currentText()} - "
                f"{chart_data.get('type','')} "
                f"{self._format_pyeong_value(chart_data.get('py', 0))}평 가격 추이"
            )
            self.chart_widget.update_chart(
                chart_data["date"], 
                chart_data["avg"], 
                chart_data["min"], 
                chart_data["max"],
                title
            )
    
    def _on_stats_complex_changed(self, index):
        """통계 탭 단지 변경 시 평형 콤보박스 업데이트"""
        cid = self.stats_complex_combo.currentData()
        if not cid:
            return

        try:
            snapshots = self.db.get_price_snapshots(cid)
        except Exception as e:
            ui_logger.warning(f"평형 목록 로드 실패: {e}")
            snapshots = []
        # 평형 목록 추출
        pyeong_values = []
        for row in snapshots:
            value = self._parse_pyeong_value(row[2] if len(row) > 2 else None)
            if value is not None:
                pyeong_values.append(value)
        pyeongs = sorted(set(pyeong_values))

        prev_text = self.stats_pyeong_combo.currentText()
        prev_value = self._parse_pyeong_value(prev_text) if prev_text and prev_text != "전체" else None

        self.stats_pyeong_combo.blockSignals(True)
        self.stats_pyeong_combo.clear()
        self.stats_pyeong_combo.addItem("전체", None)
        for p in pyeongs:
            self.stats_pyeong_combo.addItem(f"{self._format_pyeong_value(p)}평", p)
        if prev_value is not None:
            for i in range(1, self.stats_pyeong_combo.count()):
                row_value = self.stats_pyeong_combo.itemData(i)
                if row_value is None:
                    continue
                if abs(float(row_value) - float(prev_value)) <= 1e-6:
                    self.stats_pyeong_combo.setCurrentIndex(i)
                    break
        self.stats_pyeong_combo.blockSignals(False)

