import shlex
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw

class TaskDialog(Adw.Window):
    def __init__(self, parent, manager, task_data=None):
        super().__init__(transient_for=parent, modal=True)
        self.set_title(_("Task Settings"))
        self.set_default_size(400, -1)

        self.manager = manager
        self._updating = False
        self.task_data = task_data

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_content(main_box)

        header = Adw.HeaderBar()
        main_box.append(header)

        cancel_btn = Gtk.Button(label=_("Cancel"))
        cancel_btn.connect("clicked", lambda _: self.close())
        header.pack_start(cancel_btn)

        self.save_btn = Gtk.Button(label=_("Save"))
        self.save_btn.add_css_class("suggested-action")
        self.save_btn.connect("clicked", self.on_save)
        header.pack_end(self.save_btn)

        group = Adw.PreferencesGroup()
        
        self.name_entry = Adw.EntryRow(title=_("Task ID"))

        self.cmd_entry = Adw.EntryRow(title=_("Command to execute"))
        self.file_chooser_btn = Gtk.Button(icon_name="document-open-symbolic")
        self.file_chooser_btn.set_tooltip_text(_("Select file"))
        self.file_chooser_btn.connect("clicked", self.on_select_command_file)
        self.cmd_entry.add_suffix(self.file_chooser_btn)

        self.delay_spin = Gtk.SpinButton.new_with_range(0, 1440, 1)
        self.delay_row = Adw.ActionRow(title=_("Delay after boot (min)"))
        self.delay_row.add_suffix(self.delay_spin)

        self.persistent_row = Adw.SwitchRow(title=_("Execute missed tasks on next boot (Persistent)"))

        self.preset_labels = [_("Custom"), _("At Startup"), _("Hourly"), _("Daily"), _("Weekly"), _("Monthly")]
        self.preset_values = [None, "startup", "hourly", "daily", "weekly", "monthly"]

        model = Gtk.StringList.new(self.preset_labels)
        self.combo_row = Adw.ComboRow(title=_("Schedule (Preset)"), model=model)
        self.combo_handler_id = self.combo_row.connect("notify::selected", self.on_combo_changed)

        self.schedule_entry = Adw.EntryRow(title=_("Schedule (OnCalendar)"))
        self.schedule_entry.set_text("hourly")
        self.schedule_entry.set_tooltip_text(
            _("Enter systemd time format (OnCalendar).\n\n"
              "Examples:\n"
              "- minutely, hourly, daily\n"
              "- 12:00 (Every day at 12:00)\n"
              "- Mon 09:00 (Every Monday at 09:00)\n"
              "- *:0/15:00 (Every 15 minutes)\n"
              "- *-*-01 00:00 (1st of every month)")
        )
        
        if task_data:
            self.name_entry.set_text(task_data['id'])
            self.name_entry.set_editable(False) # ID cannot be changed
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

            # Restore combo box selection based on initial value
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

        # Connect validation on input change
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
            # When "Custom" is selected, clear if it contains preset keywords to prompt mode switch
            if current_text.startswith("startup") or any(v == current_text for v in self.preset_values if v):
                self._updating = True
                self.schedule_entry.set_text("")
                self._updating = False

        self.on_input_changed()

    def on_input_changed(self, *args):
        name = self.name_entry.get_text().strip()
        cmd = self.cmd_entry.get_text()
        schedule = self.schedule_entry.get_text()

        # UI switching for startup configuration
        is_startup = schedule.startswith("startup")
        self.delay_row.set_visible(is_startup)
        self.schedule_entry.set_visible(not is_startup)
        self.persistent_row.set_visible(not is_startup)

        # Create full schedule string for validation
        full_schedule = schedule
        if is_startup:
            delay = int(self.delay_spin.get_value())
            full_schedule = f"startup:{delay}"

        # Update combo selection according to input content (temporarily blocked to prevent infinite loops)
        matched_idx = 0
        for i, p_val in enumerate(self.preset_values):
            if not p_val: continue
            if p_val and (schedule == p_val or (p_val == "startup" and schedule.startswith("startup"))):
                matched_idx = i
                break
        
        # Update only if the combo box selection actually changes
        if self.combo_row.get_selected() != matched_idx:
            self._updating = True
            self.combo_row.set_selected(matched_idx)
            self._updating = False

        is_valid = bool(name) and bool(cmd)
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
        dialog = Gtk.FileDialog(title=_("Select command file"))

        def on_open_finished(source, result):
            try:
                file = source.open_finish(result)
                if file:
                    self.cmd_entry.set_text(shlex.quote(file.get_path()))
            except:
                # Handle user cancellation or errors
                pass

        dialog.open(self, None, on_open_finished)
