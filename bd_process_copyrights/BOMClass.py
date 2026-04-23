from .ComponentListClass import ComponentList
from .ComponentClass import Component
from .ConfigClass import Config
from blackduck import Client
import sys
import asyncio
import platform


class BOM:
    def __init__(self, conf):
        try:
            self.complist = ComponentList()
            self.bd = Client(
                token=conf.bd_api,
                base_url=conf.bd_url,
                verify=(not conf.bd_trustcert),  # TLS certificate verification
                timeout=60
            )

            self.bdver_dict = self.get_project(conf)

            res = self.bd.list_resources(self.bdver_dict)
            self.projver = res['href']
            thishref = f"{self.projver}/components"

            bom_arr = self.get_paginated_data(thishref, "application/vnd.blackducksoftware.bill-of-materials-6+json")

            for comp in bom_arr:
                if 'componentVersion' not in comp:
                    continue

                compclass = Component(comp['componentName'], comp['componentVersionName'], comp)
                self.complist.add(compclass)

        except ValueError as v:
            conf.logger.error(v)
            sys.exit(-1)
        return

    def get_paginated_data(self, url, accept_hdr):
        headers = {
            'accept': accept_hdr,
        }
        url = url + "?limit=1000"
        res = self.bd.get_json(url, headers=headers)
        if 'totalCount' in res and 'items' in res:
            total_comps = res['totalCount']
        else:
            return []

        ret_arr = []
        downloaded_comps = 0
        while downloaded_comps < total_comps:
            downloaded_comps += len(res['items'])

            ret_arr += res['items']

            newurl = f"{url}&offset={downloaded_comps}"
            res = self.bd.get_json(newurl, headers=headers)
            if 'totalCount' not in res or 'items' not in res:
                break

        return ret_arr

    def get_project(self, conf):
        params = {
            'q': "name:" + conf.bd_project,
            'sort': 'name',
        }

        ver_dict = None
        projects = self.bd.get_resource('projects', params=params)
        for p in projects:
            if p['name'] == conf.bd_project:
                versions = self.bd.get_resource('versions', parent=p, params=params)
                for v in versions:
                    if v['versionName'] == conf.bd_version:
                        ver_dict = v
                        break
                break
        else:
            conf.logger.error(f"Project '{conf.bd_project}' does not exist")
            sys.exit(2)

        if ver_dict is None:
            conf.logger.error(f"Version '{conf.bd_version}' does not exist in project '{conf.bd_project}'")
            sys.exit(2)

        return ver_dict

    def get_source_tree_copyrights(self, conf, zero_count_ids):
        """Phase 3: Get copyrights from project source trees via file-level string search matches."""
        source_trees_url = f"{self.projver}/source-trees"
        internal_headers = {'accept': 'application/vnd.blackducksoftware.internal-1+json'}

        try:
            res = self.bd.get_json(source_trees_url, headers=internal_headers)
        except Exception as e:
            conf.logger.error(f"Error fetching source-trees: {e}")
            return {}

        items = res.get('items', [])
        conf.logger.debug(f"Source trees: {len(items)} item(s) found")

        # Dict keyed by component version URL -> list of copyright texts
        copyright_map = {}

        for item in items:
            if item.get('nodeType') != 'DIRECTORY':
                continue

            conf.logger.debug("- Located SIGNATURE scan ..")

            # Find the source-entries link
            source_entries_href = None
            for link in item.get('_meta', {}).get('links', []):
                if link.get('rel') == 'source-entries':
                    source_entries_href = link['href']
                    break

            if not source_entries_href:
                continue

            conf.logger.debug("- Found source-entries scan ...")

            # Build base URL for paginated source-entries requests
            separator = '&' if '?' in source_entries_href else '?'
            entries_base_url = (
                f"{source_entries_href}{separator}allDescendants=true"
                f"&filter=stringSearchMatchType%3Acopyright&limit=100"
            )

            offset = 0
            total_count = None
            total_fetched = 0

            while True:
                page_url = f"{entries_base_url}&offset={offset}"
                try:
                    page_res = self.bd.get_json(page_url)
                except Exception as e:
                    conf.logger.error(f"Error fetching source entries at offset {offset}: {e}")
                    break

                if total_count is None:
                    total_count = page_res.get('totalCount', 0)
                    conf.logger.info(
                        f"  Directory '{item.get('name', '')}': "
                        f"{total_count} source entry/entries with copyright matches"
                    )
                    if total_count == 0:
                        break

                page_items = page_res.get('items', [])
                if not page_items:
                    break

                for entry in page_items:
                    bom_comp = entry.get('fileMatchBomComponent')
                    if not bom_comp:
                        continue

                    project_id = bom_comp.get('project', {}).get('id', '')
                    release_id = bom_comp.get('release', {}).get('id', '')
                    if not project_id or not release_id:
                        continue

                    compver = f"{project_id}/versions/{release_id}"

                    if compver not in zero_count_ids:
                        continue

                    for match in entry.get('fileStringSearchMatches', []):
                        if match.get('matchType') == 'Copyright':
                            text = match.get('name', '')
                            if text:
                                if compver not in copyright_map:
                                    copyright_map[compver] = []
                                if text not in copyright_map[compver]:
                                    copyright_map[compver].append(text)

                total_fetched += len(page_items)
                offset += len(page_items)

                if total_fetched >= total_count:
                    break

        return copyright_map

    def process_copyrights(self, conf: Config):
        if platform.system() == "Windows":
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

        # Phase 1: collect existing copyright texts for all components
        existing_copyrights_data = asyncio.run(self.complist.async_get_copyright_counts(conf, self.bd))

        zero_count_ids = {comp_id for comp_id, texts in existing_copyrights_data.items() if not texts}
        conf.logger.info(f"  {len(zero_count_ids)} components with no copyrights")
        conf.summary_text.append(f"- {len(zero_count_ids)} components originally with no copyrights")

        # Phase 2: fetch actual copyright text via origins
        # With --all_copyrights, process every component; otherwise only those with zero existing copyrights
        if conf.all_copyrights:
            process_ids = set(existing_copyrights_data.keys())
        else:
            process_ids = zero_count_ids

        conf.logger.info("")
        conf.logger.info(f"Processing {len(process_ids)} components for alternate origins copyrights ...")
        phase2_data = {}
        if process_ids:
            phase2_data = asyncio.run(
                self.complist.async_get_copyrights(conf, self.bd, process_ids)
            )

        # Deduplicate Phase 2 results against copyrights already recorded in Black Duck (Phase 1)
        for comp_id, copyrights in phase2_data.items():
            existing = existing_copyrights_data.get(comp_id, [])
            phase2_data[comp_id] = [t for t in copyrights if t not in existing]

        phase2_compids_with_copyrights = {comp_id for comp_id, copyrights in phase2_data.items() if len(copyrights) > 0}
        phase2_compids_without_copyrights = {comp_id for comp_id, copyrights in phase2_data.items() if len(copyrights) == 0}

        conf.logger.info(f"  Found {len(phase2_compids_with_copyrights)} components with new copyrights in alternate origins")
        conf.summary_text.append(f"- {len(phase2_compids_with_copyrights)} components with new copyrights in alternate origins")

        # Phase 3: get copyrights from project source trees via file-level string search matches
        phase3_data = {}
        if conf.local_copyrights:
            conf.logger.info("")
            conf.logger.info(f""
                             f"Processing {len(phase2_compids_without_copyrights)} components for local copyright scans ...")
            phase3_data = self.get_source_tree_copyrights(conf, phase2_compids_without_copyrights)

            # Deduplicate Phase 3 results against copyrights already recorded in Black Duck (Phase 1)
            for comp_id, copyrights in phase3_data.items():
                existing = existing_copyrights_data.get(comp_id, [])
                phase3_data[comp_id] = [t for t in copyrights if t not in existing]

            phase3_compids_with_copyrights = {comp_id for comp_id, copyrights in phase3_data.items() if len(copyrights) > 0}

            conf.logger.info(f"  Found {len(phase3_compids_with_copyrights)} components with new copyrights in local copyright scans")
            conf.logger.info("")
            conf.summary_text.append(
                f"- {len(phase3_compids_with_copyrights)} components with new local scan copyrights")
        else:
            phase3_compids_with_copyrights = set()
            conf.summary_text.append(f"- skipped processing local scan copyrights")

        if conf.all_copyrights and conf.update_copyrights:
            all_modified_ids = phase2_compids_with_copyrights | phase3_compids_with_copyrights
            combined_for_count = {
                comp_id: list(dict.fromkeys(phase2_data.get(comp_id, []) + phase3_data.get(comp_id, [])))
                for comp_id in all_modified_ids
            }
            total_new_copyrights = sum(len(v) for v in combined_for_count.values())
            conf.summary_text.append(f"- {len(all_modified_ids)} components modified with new copyrights")
            conf.summary_text.append(f"- {total_new_copyrights} new copyrights created")

        if conf.update_copyrights:
            update_comp_ids = set(phase2_compids_with_copyrights) | set(phase3_compids_with_copyrights)
            combined_data = {
                comp_id: list(dict.fromkeys(phase2_data.get(comp_id, []) + phase3_data.get(comp_id, [])))
                for comp_id in update_comp_ids
            }
            if combined_data:
                conf.logger.info(f"Updating copyrights for {len(update_comp_ids)} components...")
                asyncio.run(self.complist.async_post_copyrights(conf, self.bd, combined_data))
        else:
            conf.summary_text.append(f"- No copyrights updated (--update_copyrights not specified)")

        if conf.report:
            all_comp_ids = set(phase2_compids_with_copyrights) | set(phase3_compids_with_copyrights)
            comp_name_map = {comp.id: (comp.name, comp.version) for comp in self.complist.components}

            for comp_id in sorted(all_comp_ids, key=lambda c: comp_name_map.get(c, (c, ''))):
                name, version = comp_name_map.get(comp_id, (comp_id, ''))
                conf.report_text.append(f"{name} {version}")

                p2 = phase2_data.get(comp_id, [])
                if p2:
                    conf.report_text.append(f"  Alternate Origins ({len(p2)} found):")
                    for text in p2:
                        conf.report_text.append(f"    - {text}")

                p3 = phase3_data.get(comp_id, [])
                if p3:
                    conf.report_text.append(f"  Local Source Tree Scan ({len(p3)} found):")
                    for text in p3:
                        conf.report_text.append(f"    - {text}")

                conf.report_text.append("")

        return
