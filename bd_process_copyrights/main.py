# from . import global_values
from BOMClass import BOM
# from . import config
# from KernelSourceClass import KernelSource
from ConfigClass import Config
import sys


def main():
    conf = Config()
    conf.get_cli_args()

    conf.logger.info(f"BLACK DUCK COPYRIGHT PROCESSOR - v1.0")
    conf.logger.info(f"")

    process(conf)
    # config.check_args(args)
    
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
