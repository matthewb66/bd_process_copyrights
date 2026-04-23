from .ConfigClass import Config


class Component:
    def __init__(self, name, version, data):
        self.name = name
        self.version = version
        self.data = data
        self.id = self.get_compid()

    def is_ignored(self):
        try:
            return self.data['ignored']
        except KeyError:
            return False

    def get_compid(self):
        try:
            compurl = self.data['componentVersion']
            return compurl.split('/components/')[-1]
        except KeyError:
            return ''

    async def async_get_copyright_count(self, bd, conf, session, token):
        if conf.bd_trustcert:
            ssl = False
        else:
            ssl = None

        headers = {
            'Accept': "application/vnd.blackducksoftware.copyright-4+json",
            'Authorization': f'Bearer {token}',
        }

        comp_id = self.id
        try:
            existing_copyrights = []
            for origin in self.data['origins']:
                copyright_url = origin['origin'] + "/copyrights"
                copyright_url += "?limit=100&offset=0"
                async with session.get(copyright_url, headers=headers, ssl=ssl) as resp:
                    data = await resp.json()
                for item in data.get("items", []):
                    if item.get('active'):
                        text = item.get('updatedCopyright', item.get('originalCopyright', ''))
                        if text and text not in existing_copyrights:
                            existing_copyrights.append(text)
            return comp_id, existing_copyrights
        except Exception as e:
            conf.logger.error(e)

        return comp_id, []

    def _make_headers(self, token):
        auth = f'Bearer {token}'
        return {
            'origins': {
                'Accept': "application/vnd.blackducksoftware.component-detail-4+json",
                'Authorization': auth,
            },
            'copyrights': {
                'Accept': "application/vnd.blackducksoftware.copyright-4+json",
                'Authorization': auth,
            },
        }

    async def _fetch_copyrights_for_origins(self, session, origins_list_url, headers, ssl, conf, defined_origin_urls=None):
        async with session.get(origins_list_url, headers=headers['origins'], ssl=ssl) as resp:
            origins_data = await resp.json()

        copyrights = []
        items = origins_data.get('items', [])
        conf.logger.debug(f"  {self.name}/{self.version}: found {len(items)} origin(s) to scan")
        for origin_item in items:
            href = origin_item.get('_meta', {}).get('href', '')
            if not href:
                continue
            if defined_origin_urls and href.rstrip('/') in defined_origin_urls:
                continue
            copyright_url = href.rstrip('/') + '/copyrights'
            async with session.get(copyright_url, headers=headers['copyrights'], ssl=ssl) as resp:
                data = await resp.json()
            for item in data.get('items', []):
                text = item.get('updatedCopyright', item.get('originalCopyright', ''))
                if text and text not in copyrights:
                    copyrights.append(text)
        return copyrights

    async def async_get_copyrights(self, bd, conf, session, token):
        ssl = False if conf.bd_trustcert else None
        headers = self._make_headers(token)
        all_copyrights = []

        defined_origin_urls = {
            selected_origin['origin'].rstrip('/')
            for selected_origin in self.data.get('origins', [])
        }

        try:
            for selected_origin in self.data.get('origins', []):
                origin_url = selected_origin['origin'].rstrip('/')
                origins_list_url = origin_url.rsplit('/', 1)[0] + '?limit=100'

                origin_copyrights = await self._fetch_copyrights_for_origins(
                    session, origins_list_url, headers, ssl, conf, defined_origin_urls
                )

                for text in origin_copyrights:
                    if text not in all_copyrights:
                        all_copyrights.append(text)

        except Exception as e:
            conf.logger.error(
                f"[{self.name}/{self.version}] Error during copyright processing: {e}"
            )

        return self.id, all_copyrights
