from __future__ import unicode_literals, print_function

import logging
import os
import re
from collections import OrderedDict

from qordoba.languages import normalize_language, LanguageNotFound
from qordoba.utils import python_2_unicode_compatible

log = logging.getLogger('qordoba')

DEFAULT_PATTERN = '<language_code><extension>'

CONTENT_TYPE_CODES = OrderedDict()
CONTENT_TYPE_CODES['excel'] = ('xlsx', )
CONTENT_TYPE_CODES['xliff'] = ('xliff', 'xlf')
CONTENT_TYPE_CODES['XLIFF1.2'] = ('xliff', 'xlf')
CONTENT_TYPE_CODES['xmlAndroid'] = ('xml', )
CONTENT_TYPE_CODES['macStrings'] = ('strings', )
CONTENT_TYPE_CODES['PO'] = ('po',)
CONTENT_TYPE_CODES['propertiesJava'] = ('properties', )
CONTENT_TYPE_CODES['YAML'] = ('yml', 'yaml')
CONTENT_TYPE_CODES['YAMLi18n'] = ('yml', 'yaml')
CONTENT_TYPE_CODES['csv'] = ('csv', )
CONTENT_TYPE_CODES['JSON'] = ('json', )
CONTENT_TYPE_CODES['SRT'] = ('srt', )
CONTENT_TYPE_CODES['md'] = ('md', 'text')

ALLOWED_EXTENSIONS = OrderedDict(
    {extension: k for k, extensions in CONTENT_TYPE_CODES.items() for extension in extensions}
)


class PatternNotValid(Exception):
    pass


class FileExtensionNotAllowed(Exception):
    """
    The file extension doesn't match any file format allowed for this project
    """


def to_posix(filepath):
    return filepath if os.altsep is None else filepath.replace(os.altsep, os.sep)


def to_native(filepath):
    return filepath if os.altsep is None else filepath.replace(os.altsep, os.sep)


@python_2_unicode_compatible
class TranslationFile(object):
    def __init__(self, path, lang, curdir):
        self.relpath = path
        self.name = os.path.basename(path)
        self.lang = lang
        self._curdir = curdir
        self.fullpath = os.path.join(curdir, path)

    @property
    def extension(self):
        try:
            _, extension = self.name.split('.', 1)
        except ValueError:
            extension = None
        return extension

    @property
    def posix_path(self):
        return to_posix(self.relpath)

    @property
    def native_path(self):
        return to_native(self.relpath)

    @property
    def path_parts(self):
        return self.relpath.split(os.sep)

    @property
    def unique_name(self):
        return '-'.join(self.path_parts).lower()

    def __hash__(self):
        return hash(str(self))

    def __str__(self):
        return self.name

    def replace(self, name):
        """
        Replace file name. Create new TranslationPath
        :param str name:
        :rtype: qordoba.sources.TranslationPath
        """
        new_path = os.path.join(os.path.dirname(self.relpath), name)

        return self.__class__(new_path, self.lang, self._curdir)


def validate_path(curdir, path, lang):
    """
    Validate path
        Make path relative to curdir
        Validate language string
        Create TranslationFile object
    :param str curdir: FilePath.
    :param str path: Raw file path
    :param str lang: Raw language string
    :rtype: qordoba.sources.TranslationFile
    """
    lang = normalize_language(lang)
    if not isinstance(path, TranslationFile):
        path = os.path.relpath(path, curdir)
        path = TranslationFile(path, lang, curdir)

    return path


class LanguagePatternVariables(object):
    language_code = 'language_code'
    language_name = 'language_name'
    language_name_cap = 'language_name_cap'
    language_name_allcap = 'language_name_allcap'
    language_lang_code = 'language_lang_code'

    all = language_code, language_name, language_name_cap, language_name_allcap, language_lang_code


push_pattern_validate_regexp = re.compile('\<({})\>'.format('|'.join((LanguagePatternVariables.language_code, LanguagePatternVariables.language_lang_code))))
pull_pattern_validate_regexp = re.compile('\<({})\>'.format('|'.join(LanguagePatternVariables.all)))


def validate_push_pattern(pattern):
    if not push_pattern_validate_regexp.search(pattern):
        raise PatternNotValid(
            'Pattern not valid. Should contain one of the value: {}'.format(', '.join(LanguagePatternVariables.all)))

    pattern_re = to_posix(pattern)
    pattern_re = re.escape(pattern_re)

    expression_re = pattern_re.replace(re.escape('<language_code>'), '(?P<language_code>[\w]{2}\-[\w]{2})')

    lang_pattern_escaped = re.escape('<{}>'.format(LanguagePatternVariables.language_lang_code))
    expression_re = expression_re.replace(lang_pattern_escaped, '(?P<{}>[\w]*)'.format(LanguagePatternVariables.language_lang_code))

    expression_re = re.compile('^{}$'.format(expression_re), flags=re.IGNORECASE)
    return expression_re


def create_target_path_by_pattern(curdir, language, pattern=None, source_name=None, content_type_code=None):
    if pattern is not None and not pull_pattern_validate_regexp.search(pattern):
        raise PatternNotValid(
            'Pull pattern not valid. Should contain one of the value: {}'.format(
                ', '.join(LanguagePatternVariables.all)))

    pattern = pattern or DEFAULT_PATTERN

    target_path = pattern.replace('<{}>'.format(LanguagePatternVariables.language_code), language.code)
    target_path = target_path.replace('<{}>'.format(LanguagePatternVariables.language_lang_code), language.lang)
    target_path = target_path.replace('<{}>'.format(LanguagePatternVariables.language_name), language.name)
    target_path = target_path.replace('<{}>'.format(LanguagePatternVariables.language_name_cap),
                                      language.name.capitalize())
    target_path = target_path.replace('<{}>'.format(LanguagePatternVariables.language_name_allcap),
                                      language.name.upper())

    if target_path.endswith('<extension>'):
        try:
            _, extension = os.path.splitext(source_name)
        except (ValueError, AttributeError):
            extension = ''

        target_path = target_path.replace('<extension>', extension)

    return validate_path(curdir, target_path, language)


def files_in_project(curpath, return_absolute_path=True):
    """
    Iterate over the files in the project.

    Return each file under ``curpath`` with its absolute name.
    """
    visited = set()
    for root, dirs, files in os.walk(curpath, followlinks=True):
        root_realpath = os.path.realpath(root)

        # Don't visit any subdirectory
        if root_realpath in visited:
            del dirs[:]
            continue

        for f in files:
            file_path = os.path.realpath(os.path.join(root, f))
            if not return_absolute_path:
                file_path = os.path.relpath(file_path, curpath)
            yield file_path

        visited.add(root_realpath)

        # Find which directories are already visited and remove them from
        # further processing
        removals = list(
            d for d in dirs
            if os.path.realpath(os.path.join(root, d)) in visited
        )
        for removal in removals:
            dirs.remove(removal)


def find_files_by_pattern(curpath, pattern):
    """
    :param str curpath: Current directory
    :param pattern: regexp
    :type pattern:
    :return: Iterator. Valid paths by pattern
    """
    for path in files_in_project(curpath, return_absolute_path=False):
        match = pattern.match(path)
        if match:
            lang_map = match.groupdict()
            lang = ''
            for lang_str in (lang_map[pattern] for pattern in LanguagePatternVariables.all if pattern in lang_map):
                try:
                    lang = normalize_language(lang_str)
                except LanguageNotFound:
                    continue
                else:
                    break

            try:
                path = validate_path(curpath, path, lang)
            except LanguageNotFound:
                log.warning('Language code "{}" not found in qordoba.'.format(repr(lang_map)))

            yield path


def get_content_type_code(path):
    """
    :param qordoba.sources.TranslationFile path:
    :return:
    """
    path_ext = path.extension
    if path_ext not in ALLOWED_EXTENSIONS:
        raise FileExtensionNotAllowed("File format `{}` not in allowed list of file formats: {}"
                                      .format(path_ext, ', '.join(ALLOWED_EXTENSIONS)))

    return ALLOWED_EXTENSIONS[path_ext]
