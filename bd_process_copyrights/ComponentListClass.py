from .ComponentClass import Component
from .ConfigClass import Config
# from BOMClass import BOM
# import global_values
# import logging
# import requests
import aiohttp
import asyncio

class ComponentList:
    def __init__(self):
        self.components = []

    def add(self, comp: Component):
        self.components.append(comp)

    def count(self):
        return len(self.components)

    def count_ignored(self):
        count = 0
        for comp in self.components:
            if comp.is_ignored():
                count += 1
        return count

    async def async_get_copyright_counts(self, conf :Config, bd):
        token = bd.session.auth.bearer_token

        async with aiohttp.ClientSession(trust_env=True) as session:
            copyright_tasks = []
            for comp in self.components:
                if comp.is_ignored():
                    continue

                copyright_task = asyncio.ensure_future(comp.async_get_copyright_count(bd, conf, session, token))
                copyright_tasks.append(copyright_task)

            copyright_data = dict(await asyncio.gather(*copyright_tasks))
            await asyncio.sleep(0.250)

        return copyright_data

    # async def async_get_file_level_copyrights(self, conf: Config, bd, zero_count_ids):
    #     token = bd.session.auth.bearer_token
    #
    #     async with aiohttp.ClientSession(trust_env=True) as session:
    #         tasks = []
    #         for comp in self.components:
    #             if comp.is_ignored() or comp.id not in zero_count_ids:
    #                 continue
    #             task = asyncio.ensure_future(
    #                 comp.async_get_file_level_copyrights(bd, conf, session, token)
    #             )
    #             tasks.append(task)
    #
    #         if not tasks:
    #             return {}
    #
    #         result = dict(await asyncio.gather(*tasks))
    #         await asyncio.sleep(0.250)
    #
    #     return result

    async def async_post_copyrights(self, conf: Config, bd, copyright_data):
        token = bd.session.auth.bearer_token
        ssl = False if conf.bd_trustcert else None
        headers = {
            'Accept': "application/vnd.blackducksoftware.copyright-4+json",
            'Content-Type': "application/vnd.blackducksoftware.copyright-4+json",
            'Authorization': f'Bearer {token}',
        }

        async with aiohttp.ClientSession(trust_env=True) as session:
            comps_updated = 0
            copyrights_posted = 0
            for comp in self.components:
                copyrights = copyright_data.get(comp.id, [])
                if not copyrights:
                    continue
                comp_posted = 0
                for origin in comp.data.get('origins', []):
                    copyrights_url = origin['origin'].rstrip('/') + '/copyrights'
                    for text in copyrights:
                        async with session.post(
                            copyrights_url, json={"copyright": text},
                            headers=headers, ssl=ssl
                        ) as resp:
                            if resp.status not in (200, 201, 204):
                                conf.logger.warning(
                                    f"  [{comp.name}/{comp.version}] Failed to post copyright "
                                    f"(HTTP {resp.status}): {text[:60]}"
                                )
                            else:
                                copyrights_posted += 1
                                comp_posted += 1
                if comp_posted > 0:
                    comps_updated += 1
                    # conf.logger.info(
                    #     f"  [{comp.name}/{comp.version}] Posted {posted} copyright(s) "
                    #     f"({failed} failed)"
                    # )
            conf.summary_text.append(f"- {comps_updated} components updated with new copyrights ({copyrights_posted} total copyrights)")

    async def async_get_copyrights(self, conf: Config, bd, zero_count_ids):
        token = bd.session.auth.bearer_token

        async with aiohttp.ClientSession(trust_env=True) as session:
            tasks = []
            for comp in self.components:
                if comp.is_ignored() or comp.id not in zero_count_ids:
                    continue
                task = asyncio.ensure_future(
                    comp.async_get_copyrights(bd, conf, session, token)
                )
                tasks.append(task)

            if not tasks:
                return {}

            result = {}
            total = len(tasks)
            for completed, coro in enumerate(asyncio.as_completed(tasks), start=1):
                comp_id, copyrights = await coro
                result[comp_id] = copyrights
                if completed % 20 == 0 or completed == total:
                    conf.logger.info(f"  Processed {completed}/{total} components")
            await asyncio.sleep(0.250)

        return result

