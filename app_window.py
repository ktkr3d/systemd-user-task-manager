from gi.repository import Gtk, Adw, Gio, GLib
from manager import SystemdManager
from task_dialog import TaskDialog

class AppWindow(Adw.ApplicationWindow):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_title("Systemd User Task Manager")
        self.set_default_size(600, 500)
        self.manager = SystemdManager()

        # Layout
        self.view = Adw.ToolbarView()
        self.set_content(self.view)

        # Header Bar
        header = Adw.HeaderBar()
        add_btn = Gtk.Button(icon_name="list-add-symbolic")
        add_btn.connect("clicked", self.show_add_dialog)
        header.pack_start(add_btn)

        # Create primary menu (three-dot menu)
        menu = Gio.Menu.new()

        theme_menu = Gio.Menu.new()
        theme_menu.append(_("Follow system settings"), "win.change-theme('default')")
        theme_menu.append(_("Light theme"), "win.change-theme('light')")
        theme_menu.append(_("Dark theme"), "win.change-theme('dark')")
        menu.append_submenu(_("Theme"), theme_menu)

        menu.append(_("Refresh"), "win.refresh")
        menu.append(_("Open unit files folder"), "win.open-folder")
        menu.append(_("About Systemd User Task Manager"), "win.about")

        menu_btn = Gtk.MenuButton(icon_name="view-more-symbolic", menu_model=menu)
        header.pack_end(menu_btn)

        self.view.add_top_bar(header)

        # Define actions
        action_theme = Gio.SimpleAction.new_stateful(
            "change-theme",
            GLib.VariantType.new("s"),
            GLib.Variant.new_string("default")
        )
        action_theme.connect("activate", self.on_theme_changed)
        self.add_action(action_theme)

        action_folder = Gio.SimpleAction.new("open-folder", None)
        action_folder.connect("activate", self.open_unit_folder)
        self.add_action(action_folder)

        action_refresh = Gio.SimpleAction.new("refresh", None)
        action_refresh.connect("activate", self.on_refresh)
        self.add_action(action_refresh)

        action_about = Gio.SimpleAction.new("about", None)
        action_about.connect("activate", self.show_about)
        self.add_action(action_about)

        # List Box
        self.list_box = Gtk.ListBox()
        self.list_box.add_css_class("boxed-list")
        
        clamp = Adw.Clamp(maximum_size=500)
        clamp.set_child(self.list_box)
        
        scroll = Gtk.ScrolledWindow()
        scroll.set_child(clamp)
        self.view.set_content(scroll)

        self.refresh_list()

    def refresh_list(self):
        # Clear
        while (child := self.list_box.get_first_child()):
            self.list_box.remove(child)
        
        # Load
        for task in self.manager.list_tasks():
            # Display schedule and execution times in the subtitle
            subtitle = (_("Next: {}\nLast: {} ({})")
                        .format(task['next'], task['last'], task['schedule']))
            
            row = Adw.ActionRow(title=task['id'], subtitle=subtitle)
            
            # Enable/Disable switch
            switch = Gtk.Switch(active=task['enabled'])
            switch.set_valign(Gtk.Align.CENTER)
            switch.set_margin_end(12)
            switch.connect("state-set", lambda s, state, tid=task['id']: self.on_toggle_task(s, state, tid))
            row.add_suffix(switch)

            edit_btn = Gtk.Button(icon_name="document-edit-symbolic")
            edit_btn.add_css_class("flat")
            edit_btn.set_valign(Gtk.Align.CENTER)
            edit_btn.connect("clicked", lambda b, t=task: self.show_edit_dialog(t))
            row.add_suffix(edit_btn)

            del_btn = Gtk.Button(icon_name="user-trash-symbolic")
            del_btn.add_css_class("flat")
            del_btn.set_valign(Gtk.Align.CENTER)
            del_btn.connect("clicked", lambda b, tid=task['id']: self.delete_task(tid))
            
            row.add_suffix(del_btn)
            self.list_box.append(row)

    def show_add_dialog(self, _):
        dialog = TaskDialog(self, self.manager)
        dialog.present()
        dialog.connect("close-request", self.on_dialog_closed)

    def show_edit_dialog(self, task_data):
        dialog = TaskDialog(self, self.manager, task_data)
        dialog.present()
        dialog.connect("close-request", self.on_dialog_closed)

    def on_dialog_closed(self, dialog):
        if dialog.success:
            data = dialog.get_data()
            self.manager.save_task(data['id'], data['command'], data['schedule'], data['persistent'])
            self.refresh_list()
        return False

    def on_toggle_task(self, switch, state, task_id):
        self.manager.toggle_task(task_id, state)
        GLib.idle_add(self.refresh_list)
        return False

    def on_refresh(self, action, param):
        self.refresh_list()

    def open_unit_folder(self, action, param):
        # Convert path to URI format (file://...) and open with default app
        uri = GLib.filename_to_uri(self.manager.UNIT_PATH, None)
        Gio.AppInfo.launch_default_for_uri(uri, None)

    def on_theme_changed(self, action, value):
        theme = value.get_string()
        style_manager = Adw.StyleManager.get_default()
        
        if theme == "light":
            style_manager.set_color_scheme(Adw.ColorScheme.PREFER_LIGHT)
        elif theme == "dark":
            style_manager.set_color_scheme(Adw.ColorScheme.PREFER_DARK)
        else:
            style_manager.set_color_scheme(Adw.ColorScheme.DEFAULT)
        
        action.set_state(value)

    def show_about(self, action, param):
        about = Adw.AboutWindow(
            transient_for=self,
            application_name="Systemd User Task Manager",
            application_icon="io.github.ktkr3d.systemd-user-task-manager",
            version="0.1.0",
            developer_name="ktkr3d",
            license_type=Gtk.License.GPL_3_0,
            website="https://github.com/ktkr3d/systemd-user-task-manager"
        )
        about.present()

    def delete_task(self, task_id):
        dialog = Adw.MessageDialog(
            transient_for=self,
            heading=_("Delete task?"),
            body=_("Task \"{}\" will be deleted. This action cannot be undone.").format(task_id),
        )

        dialog.add_response("cancel", _("Cancel"))
        dialog.add_response("delete", _("Delete"))
        dialog.set_response_appearance("delete", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")

        def on_response(d, response_id):
            if response_id == "delete":
                self.manager.delete_task(task_id)
                self.refresh_list()

        dialog.connect("response", on_response)
        dialog.present()
