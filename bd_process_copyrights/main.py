from .BOMClass import BOM
from .ConfigClass import Config
import logging
import sys


def main():
    conf = Config()
    conf.get_cli_args()

    conf.logger.info(f"BLACK DUCK COPYRIGHT PROCESSOR - v1.0.1")
    conf.logger.info(f"")

    if not conf.no_ui and (not conf.bd_url or not conf.bd_api):
        from .UIClass import ConnectionDialog
        from PyQt6.QtWidgets import QDialog

        dlg = ConnectionDialog(url=conf.bd_url, api_token=conf.bd_api)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            conf.logger.info("Connection details not provided – exiting.")
            sys.exit(0)

        conf.bd_url = dlg.url
        conf.bd_api = dlg.api_token

    if not conf.bd_url or not conf.bd_api:
        conf.logger.error("Black Duck URL and API token are required")
        sys.exit(1)

    if not conf.no_ui and (not conf.bd_project or not conf.bd_version):
        from blackduck import Client
        from .UIClass import ProjectVersionDialog
        from PyQt6.QtWidgets import QDialog

        bd = Client(
            token=conf.bd_api,
            base_url=conf.bd_url,
            verify=(not conf.bd_trustcert),
            timeout=60
        )

        try:
            # Suppress the blackduck library's noisy traceback during auth validation
            bd_logger = logging.getLogger('blackduck.Authentication')
            prev_level = bd_logger.level
            bd_logger.setLevel(logging.CRITICAL)
            try:
                bd.list_resources()
            finally:
                bd_logger.setLevel(prev_level)
        except Exception:
            conf.logger.error("Failed to connect to Black Duck server – check the URL and API token")
            sys.exit(1)

        dlg = ProjectVersionDialog(bd, project_name=conf.bd_project)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            conf.logger.info("No project/version selected – exiting.")
            sys.exit(0)

        if not conf.bd_project:
            conf.bd_project = dlg.selected_project
        conf.bd_version = dlg.selected_version

    process(conf)

    if not conf.no_ui:
        from .UIClass import ResultsDialog

        dlg = ResultsDialog(
            conf.bd_project, conf.bd_version,
            conf.summary_text,
            conf.report_text if conf.report else None,
        )
        dlg.exec()

    sys.exit(0)

def process(conf):
    bom = BOM(conf)
    conf.logger.info(f"Working on project '{conf.bd_project}' version '{conf.bd_version}'")
    conf.logger.info(f"  {bom.complist.count() - bom.complist.count_ignored()} active components")
    conf.summary_text.append(f"- {bom.complist.count() - bom.complist.count_ignored()} active components in project")

    bom.process_copyrights(conf)

    conf.logger.info("PROJECT STATUS:")
    for oline in conf.summary_text:
        conf.logger.info(f"  {oline}")

    if conf.report and conf.report_text:
        conf.logger.info("")
        conf.logger.info("COPYRIGHT REPORT:")
        conf.logger.info("=" * 60)
        for line in conf.report_text:
            conf.logger.info(line)

    conf.logger.info("Done")


if __name__ == '__main__':
    main()
