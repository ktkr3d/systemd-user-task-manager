import shlex
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw

class TaskDialog(Adw.Window):
    def __init__(self, parent, manager, task_data=None):
        super().__init__(transient_for=parent, modal=True)
        self.set_title(_("タスクの設定"))
        self.set_default_size(400, -1)

        self.manager = manager
        self._updating = False
        self.task_data = task_data

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_content(main_box)

        header = Adw.HeaderBar()
        main_box.append(header)

        cancel_btn = Gtk.Button(label=_("キャンセル"))
        cancel_btn.connect("clicked", lambda _: self.close())
        header.pack_start(cancel_btn)

        self.save_btn = Gtk.Button(label=_("保存"))
        self.save_btn.add_css_class("suggested-action")
        self.save_btn.connect("clicked", self.on_save)
        header.pack_end(self.save_btn)

        group = Adw.PreferencesGroup()
        
        self.name_entry = Adw.EntryRow(title=_("タスク名 (ID)"))

        self.cmd_entry = Adw.EntryRow(title=_("実行コマンド"))
        self.file_chooser_btn = Gtk.Button(icon_name="document-open-symbolic")
        self.file_chooser_btn.set_tooltip_text(_("ファイルを選択"))
        self.file_chooser_btn.connect("clicked", self.on_select_command_file)
        self.cmd_entry.add_suffix(self.file_chooser_btn)

        self.delay_spin = Gtk.SpinButton.new_with_range(0, 1440, 1)
        self.delay_row = Adw.ActionRow(title=_("起動後の遅延 (分)"))
        self.delay_row.add_suffix(self.delay_spin)

        self.persistent_row = Adw.SwitchRow(title=_("停止中の実行漏れを次回起動時に実行 (Persistent)"))

        self.preset_labels = [_("カスタム"), _("起動時"), _("毎時"), _("毎日"), _("毎週"), _("毎月")]
        self.preset_values = [None, "startup", "hourly", "daily", "weekly", "monthly"]

        model = Gtk.StringList.new(self.preset_labels)
        self.combo_row = Adw.ComboRow(title=_("スケジュール（プリセット）"), model=model)
        self.combo_handler_id = self.combo_row.connect("notify::selected", self.on_combo_changed)

        self.schedule_entry = Adw.EntryRow(title=_("スケジュール (OnCalendar)"), text="hourly")
        self.schedule_entry.set_tooltip_text(
            _("systemdの時刻指定形式（OnCalendar）を入力します。\n\n"
              "主な例:\n"
              "・hourly, daily, weekly, monthly\n"
              "・12:00 (毎日12:00)\n"
              "・Mon 09:00 (毎週月曜 09:00)\n"
              "・*:00/15 (15分おき)\n"
              "・*-*-01 00:00 (毎月1日)")
        )
        
        if task_data:
            self.name_entry.set_text(task_data['id'])
            self.name_entry.set_editable(False) # IDの変更は不可
            self.cmd_entry.set_text(task_data.get('command', ''))

            sched = task_data['schedule']
            if sched.startswith("startup"):
                self.schedule_entry.set_text("startup")
                if ":" in sched:
                    try:
                        self.delay_spin.set_value(float(sched.split(":")[1]))
                    except ValueError:
                        pass
            else:
                self.schedule_entry.set_text(sched)
            self.persistent_row.set_active(task_data.get('persistent', False))

            # 初期値に基づいてコンボボックスの選択状態を復元
            idx = 0
            for i, val in enumerate(self.preset_values):
                if val == task_data['schedule']:
                    idx = i
                    break
            self.combo_row.set_selected(idx)

        group.add(self.name_entry)
        group.add(self.cmd_entry)
        group.add(self.combo_row)
        group.add(self.schedule_entry)
        group.add(self.delay_row)
        group.add(self.persistent_row)

        # 入力変更時のバリデーション接続
        self.name_entry.connect("changed", self.on_input_changed)
        self.cmd_entry.connect("changed", self.on_input_changed)
        self.schedule_entry.connect("changed", self.on_input_changed)
        self.delay_spin.connect("value-changed", self.on_input_changed)

        clamp = Adw.Clamp(maximum_size=360, margin_top=20, margin_bottom=20, margin_start=12, margin_end=12)
        clamp.set_child(group)
        main_box.append(clamp)

        self.success = False
        self.on_input_changed()

    def on_combo_changed(self, combo, pspec):
        if self._updating:
            return

        idx = combo.get_selected()
        val = self.preset_values[idx]
        current_text = self.schedule_entry.get_text()

        if val is not None:
            if current_text != val:
                self._updating = True
                self.schedule_entry.set_text(val)
                self._updating = False
        else:
            # 「カスタム」選択時、プリセット用キーワードが含まれているならクリアしてモード切替を促す
            if current_text.startswith("startup") or any(v == current_text for v in self.preset_values if v):
                self._updating = True
                self.schedule_entry.set_text("")
                self._updating = False

        # 常に表示状態（delay_rowの可視性など）を更新
        self.on_input_changed()

    def on_input_changed(self, *args):
        if self._updating:
            return

        name = self.name_entry.get_text().strip()
        cmd = self.cmd_entry.get_text()
        schedule = self.schedule_entry.get_text()

        # 起動時設定の場合のUI切り替え
        is_startup = schedule.startswith("startup")
        self.delay_row.set_visible(is_startup)
        self.schedule_entry.set_visible(not is_startup)
        self.persistent_row.set_visible(not is_startup)

        # バリデーション用のフルスケジュール文字列を作成
        full_schedule = schedule
        if is_startup:
            delay = int(self.delay_spin.get_value())
            full_schedule = f"startup:{delay}"

        # 入力内容に合わせてコンボの選択状態を更新（シグナルの無限ループ防止のため一時ブロック）
        matched_idx = 0
        for i, p_val in enumerate(self.preset_values):
            if not p_val: continue
            if p_val and (schedule == p_val or (p_val == "startup" and schedule.startswith("startup"))):
                matched_idx = i
                break
        
        # コンボボックスの選択が実際に変わる場合のみ更新
        if self.combo_row.get_selected() != matched_idx:
            self._updating = True
            self.combo_row.set_selected(matched_idx)
            self._updating = False

        valid_schedule, next_run = self.manager.validate_calendar(full_schedule)
        
        # 保存ボタンの有効化条件: 名前、コマンドがあり、かつスケジュールが有効
        is_valid = bool(name) and bool(cmd) and valid_schedule
        self.save_btn.set_sensitive(is_valid)

    def on_save(self, btn):
        self.success = True
        self.close()

    def get_data(self):
        schedule = self.schedule_entry.get_text()
        if schedule.startswith("startup"):
            delay = int(self.delay_spin.get_value())
            schedule = f"startup:{delay}"
        return {
            "id": self.name_entry.get_text(),
            "command": self.cmd_entry.get_text(),
            "schedule": schedule,
            "persistent": self.persistent_row.get_active()
        }

    def on_select_command_file(self, button):
        dialog = Gtk.FileDialog(title=_("コマンドファイルを選択"))

        def on_open_finished(source, result):
            try:
                file = source.open_finish(result)
                if file:
                    self.cmd_entry.set_text(shlex.quote(file.get_path()))
            except:
                # ユーザーがキャンセルした場合やエラーが発生した場合
                pass

        dialog.open(self, None, on_open_finished)
