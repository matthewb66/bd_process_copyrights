import sys
import urllib.parse

from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QLabel,
    QLineEdit,
    QListWidget,
    QTextEdit,
    QVBoxLayout,
)


class ConnectionDialog(QDialog):
    """
    Dialog for entering the Black Duck server URL and API token.

    Fields are pre-populated with any values already known (e.g. from
    environment variables).  The OK button is disabled until both fields
    are non-empty.

    Public attributes after accept():
      url        str – Black Duck server URL
      api_token  str – Black Duck API token
    """

    def __init__(self, url: str = '', api_token: str = ''):
        self._app = QApplication.instance() or QApplication(sys.argv)
        super().__init__()

        self.url: str = url
        self.api_token: str = api_token

        self.setWindowTitle('Black Duck – Server Connection')
        self.resize(500, 200)
        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        layout = QVBoxLayout(self)

        group = QGroupBox('Connection Details')
        group_layout = QVBoxLayout(group)

        group_layout.addWidget(QLabel('Server URL:'))
        self._url_edit = QLineEdit(self.url)
        self._url_edit.setPlaceholderText('https://blackduck.example.com')
        self._url_edit.textChanged.connect(self._on_text_changed)
        group_layout.addWidget(self._url_edit)

        group_layout.addWidget(QLabel('API Token:'))
        self._token_edit = QLineEdit(self.api_token)
        self._token_edit.setPlaceholderText('API token')
        self._token_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._token_edit.textChanged.connect(self._on_text_changed)
        group_layout.addWidget(self._token_edit)

        layout.addWidget(group)

        self._buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self._buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(
            bool(self.url and self.api_token)
        )
        self._buttons.accepted.connect(self._on_accept)
        self._buttons.rejected.connect(self.reject)
        layout.addWidget(self._buttons)

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_text_changed(self):
        ok = bool(self._url_edit.text().strip() and self._token_edit.text().strip())
        self._buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(ok)

    def _on_accept(self):
        self.url = self._url_edit.text().strip()
        self.api_token = self._token_edit.text().strip()
        self.accept()


class ProjectVersionDialog(QDialog):
    """
    Dialog for selecting a Black Duck project and version.

    If project_name is empty, shows both a project list and a version list.
    If project_name is provided, skips the project list and loads versions directly.

    Public attributes after accept():
      selected_project  str – project name
      selected_version  str – version name
    """

    def __init__(self, bd, project_name: str = ''):
        self._app = QApplication.instance() or QApplication(sys.argv)
        super().__init__()
        self._bd = bd
        self._project_name = project_name
        self._projects: list[dict] = []   # [{name, href}]
        self._versions: list[dict] = []   # [{name, href}]

        self.selected_project: str = project_name
        self.selected_version: str = ''

        self.setWindowTitle('Black Duck – Select Project / Version')
        self.resize(600, 450)
        self._build_ui()

        if project_name:
            self._load_versions_for_project_name(project_name)
        else:
            self._load_projects()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        layout = QVBoxLayout(self)

        if not self._project_name:
            proj_group = QGroupBox('Project')
            proj_layout = QVBoxLayout(proj_group)
            self._proj_filter = QLineEdit()
            self._proj_filter.setPlaceholderText('Filter projects …')
            self._proj_filter.textChanged.connect(self._filter_projects)
            proj_layout.addWidget(self._proj_filter)
            self._proj_list = QListWidget()
            self._proj_list.currentItemChanged.connect(self._on_project_selected)
            proj_layout.addWidget(self._proj_list, stretch=1)
            layout.addWidget(proj_group, stretch=1)

        ver_group = QGroupBox('Version')
        ver_layout = QVBoxLayout(ver_group)
        self._ver_filter = QLineEdit()
        self._ver_filter.setPlaceholderText('Filter versions …')
        self._ver_filter.textChanged.connect(self._filter_versions)
        ver_layout.addWidget(self._ver_filter)
        self._ver_list = QListWidget()
        self._ver_list.currentItemChanged.connect(self._on_version_selected)
        ver_layout.addWidget(self._ver_list, stretch=1)
        layout.addWidget(ver_group, stretch=1)

        self._buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self._buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
        self._buttons.accepted.connect(self.accept)
        self._buttons.rejected.connect(self.reject)
        layout.addWidget(self._buttons)

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def _load_projects(self):
        try:
            url = f"{self._bd.base_url.rstrip('/')}/api/projects?limit=500&sort=name"
            data = self._bd.get_json(url)
            self._projects = [
                {'name': item['name'], 'href': item['_meta']['href']}
                for item in data.get('items', [])
                if item.get('name') and item.get('_meta', {}).get('href')
            ]
        except Exception as e:
            print(f"WARNING: error fetching projects: {e}", file=sys.stderr)

        self._proj_list.clear()
        for p in self._projects:
            self._proj_list.addItem(p['name'])

    def _load_versions(self, project_href: str):
        self._versions = []
        self._ver_list.clear()
        try:
            url = f"{project_href.rstrip('/')}/versions?limit=500&sort=versionName"
            data = self._bd.get_json(url)
            self._versions = [
                {'name': item['versionName'], 'href': item['_meta']['href']}
                for item in data.get('items', [])
                if item.get('versionName') and item.get('_meta', {}).get('href')
            ]
        except Exception as e:
            print(f"WARNING: error fetching versions: {e}", file=sys.stderr)

        for v in self._versions:
            self._ver_list.addItem(v['name'])

    def _load_versions_for_project_name(self, project_name: str):
        try:
            url = (
                f"{self._bd.base_url.rstrip('/')}/api/projects"
                f"?q=name:{urllib.parse.quote(project_name)}&limit=10"
            )
            data = self._bd.get_json(url)
            for item in data.get('items', []):
                if item.get('name') == project_name:
                    self._load_versions(item['_meta']['href'])
                    break
        except Exception as e:
            print(f"WARNING: error fetching project '{project_name}': {e}", file=sys.stderr)

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _filter_projects(self, text: str):
        query = text.lower()
        for i in range(self._proj_list.count()):
            item = self._proj_list.item(i)
            item.setHidden(query not in item.text().lower())

    def _filter_versions(self, text: str):
        query = text.lower()
        for i in range(self._ver_list.count()):
            item = self._ver_list.item(i)
            item.setHidden(query not in item.text().lower())

    def _on_project_selected(self, current, _previous):
        if not current:
            return
        self.selected_project = current.text()
        href = next((p['href'] for p in self._projects if p['name'] == self.selected_project), '')
        if href:
            self._load_versions(href)
        self.selected_version = ''
        self._update_ok()

    def _on_version_selected(self, current, _previous):
        self.selected_version = current.text() if current else ''
        self._update_ok()

    def _update_ok(self):
        ok = bool(self.selected_version)
        if not self._project_name:
            ok = ok and bool(self.selected_project)
        self._buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(ok)


class ResultsDialog(QDialog):
    """
    Dialog displaying the final run results.

    Shows the project status summary and, when available, the copyright
    report in a read-only text area with an OK button to dismiss.
    """

    def __init__(self, project: str, version: str,
                 summary_lines: list[str], report_lines: list[str] | None = None):
        self._app = QApplication.instance() or QApplication(sys.argv)
        super().__init__()

        self.setWindowTitle(f'Black Duck – Results: {project} / {version}')
        self.resize(700, 450)
        self._build_ui(project, version, summary_lines, report_lines)

    def _build_ui(self, project, version, summary_lines, report_lines):
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel(f'Project: {project}    Version: {version}'))

        summary_group = QGroupBox('Project Status')
        summary_layout = QVBoxLayout(summary_group)
        summary_text = QTextEdit()
        summary_text.setReadOnly(True)
        summary_text.setPlainText('\n'.join(summary_lines))
        summary_layout.addWidget(summary_text)
        layout.addWidget(summary_group, stretch=1)

        if report_lines:
            report_group = QGroupBox('Copyright Report')
            report_layout = QVBoxLayout(report_group)
            report_text = QTextEdit()
            report_text.setReadOnly(True)
            report_text.setPlainText('\n'.join(report_lines))
            report_layout.addWidget(report_text)
            layout.addWidget(report_group, stretch=2)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)
