from __future__ import unicode_literals, print_function

import logging
import os
import shutil
from argparse import ArgumentTypeError

from qordoba.commands.utils import mkdirs
from qordoba.languages import get_destination_languages, init_language_storage, normalize_language
from qordoba.project import ProjectAPI, PageStatus
from qordoba.settings import get_pull_pattern
from qordoba.sources import create_target_path_by_pattern

log = logging.getLogger('qordoba')


def validate_languges_input(languages, project_languages):
    selected_langs = set()
    for l in languages:
        selected_langs.add(normalize_language(l))

    not_valid = selected_langs.difference(set(project_languages))
    if not_valid:
        raise ArgumentTypeError('Selected languages not configured in project as target languages: `{}`'
                                .format(','.join((str(i) for i in not_valid))))

    return selected_langs


def pull_command(curdir, config, force=False, languages=(), download_ss=False, **kwargs):
    api = ProjectAPI(config)
    init_language_storage(api)
    project = api.get_project()
    target_languages = list(get_destination_languages(project))
    if languages:
        languages = validate_languges_input(languages, target_languages)
    else:
        languages = target_languages

    pattern = get_pull_pattern(config, default=None)

    status_filter = [PageStatus.enabled, ]
    if download_ss is False:
        log.debug('Pull only completed translations.')
        status_filter = [PageStatus.completed, ]

    for language in languages:
        is_started = False

        for page in api.page_search(language.id, status=status_filter):
            is_started = True
            page_status = api.get_page_details(language.id, page['page_id'], )

            log.info('Downloading translation file for source `{}` and language `{}`'.format(
                page_status['display_name'],
                language.code,
            ))
            milestone = None
            if download_ss:
                milestone = page_status['status']['id']
                log.debug('Selected status for page `{}` - {}'.format(page_status['id'], page_status['status']['name']))

            target_path = create_target_path_by_pattern(curdir, language, pattern=pattern,
                                                        source_name=page_status['name'],
                                                        content_type_code=page_status['content_type_code'])
            if os.path.exists(target_path.native_path) and not force:
                log.warning('Translation file is already exist. `{}`'.format(target_path.native_path))

            res = api.download_file(page_status['id'], language.id, milestone=milestone)
            res.raw.decode_content = True  # required to decompress content
            # ensure to create all directories
            mkdirs(os.path.dirname(target_path.native_path))
            # copy content to dest path
            with open(target_path.native_path, 'wb') as f:
                shutil.copyfileobj(res.raw, f)

            log.info('Downloaded translation file `{}` for source `{}` and language `{}`'
                     .format(target_path.native_path,
                             page_status['display_name'],
                             language.code))

        if not is_started:
            log.info('Nothing to download for language `{}`'.format(language.code))
