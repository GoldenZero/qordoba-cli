import os

import pytest
from collections import OrderedDict
from qordoba.languages import Language
from qordoba.sources import validate_push_pattern, PatternNotValid, create_target_path_by_pattern, to_native, \
    find_files_by_pattern, TranslationFile, add_project_file_formats

PATTERN1 = 'i18n/<language_code>/translations.json'
PATTERN2 = 'folder1/values-<language_lang_code>/strings.xml'
PATTERN3 = 'config/locales/server.<language_code>.yml'

PATTERN4 = 'folder2/<language_name>/strings.xml'
PATTERN5 = 'folder3/strings.<language_name_cap>'
PATTERN6 = '<language_name_allcap>.locale'

PATTERN_PUSH1 = 'config/*'
PATTERN_PUSH2 = './*/*.json'
PATTERN_PUSH3 = 'sources/[0-9]/*'
PATTERN_PUSH4 = 'folder1/values-*/strings.xml'


PATTERN_PUSH_INVALID1 = 'i18n/<language_lang>/translations.json'
PATTERN_PUSH_INVALID2 = ''
PATTERN_PUSH_INVALID3 = './sources/'

PATH1 = 'i18n/fr-fr/translations.json'

paths = (
    'i18n/fr-fr/translations.json',
    'i18n/en/translations.json',
    'i18n/en_US/translations.json'
)

LANGUAGE_EN = Language({
            "id": 94,
            "name": "English - United States",
            "code": "en-us",
            "direction": "ltr",
            "override_order": "aaa - aaa - English - United States"
})

LANGUAGE_FR = Language({
    "id" : 110,
    "name" : "French - France",
    "code" : "fr-fr",
    "direction" : "ltr",
    "override_order" : "aaa - naa - French - France"
  })

LANGUAGE_CN = Language({
    "id" : 46,
    "name" : "Chinese - China",
    "code" : "zh-cn",
    "direction" : "ltr",
    "override_order" : "Chinese - China"
})


@pytest.fixture
def mock_change_dir(monkeypatch, curdir):
    root = os.path.abspath(curdir)
    chdir_path = os.path.join(root, 'fixtures', 'push')
    monkeypatch.chdir(chdir_path)
    return chdir_path


@pytest.mark.parametrize('pattern', [PATTERN_PUSH1, PATTERN_PUSH2, PATTERN_PUSH3])
def test_validate_push_pattern(pattern):
    res = validate_push_pattern(pattern)


# @pytest.mark.parametrize('invalid_pattern', [PATTERN_PUSH_INVALID1,
#                                              PATTERN_PUSH_INVALID2,
#                                              PATTERN_PUSH_INVALID3,
#                                              ])

# def test_validate_push_pattern_invalid(invalid_pattern):
#     with pytest.raises(PatternNotValid):
#         validate_push_pattern(invalid_pattern)


@pytest.mark.parametrize('invalid_pattern', [PATTERN_PUSH_INVALID1,
                                             PATTERN_PUSH_INVALID2,
                                             PATTERN_PUSH_INVALID3
                                             ])
def test_create_target_path_by_pattern_invalid(invalid_pattern, projectdir):
    with pytest.raises(PatternNotValid):
        create_target_path_by_pattern(projectdir, None, None, pattern=invalid_pattern)


@pytest.mark.parametrize('pattern,target_language,expected', [
    (PATTERN1, LANGUAGE_CN, to_native('i18n/zh-cn/translations.json')),
    (PATTERN2, LANGUAGE_EN, to_native('folder1/values-en/strings.xml')),
    (PATTERN3, LANGUAGE_FR, to_native('config/locales/server.fr-fr.yml')),
    (PATTERN4, LANGUAGE_CN, to_native('folder2/Chinese/strings.xml')),
    (PATTERN5, LANGUAGE_FR, to_native('folder3/strings.French')),
    (PATTERN6, LANGUAGE_FR, 'FRENCH.locale')
])

def test_create_target_path_by_pattern(mock_lang_storage, pattern, target_language, expected):
    res = create_target_path_by_pattern('', target_language, None, pattern=pattern)
    assert res.native_path == expected


@pytest.mark.parametrize('pattern,expected', [
    ('./sources/*', ['./sources/sampleA.json', './sources/sampleB.json']),
    ('./sources/*/*', ['./sources/C/sampleC.json', './sources/D/sampleD.json']),
    ('./sources/*/sample[A,C].json', ['./sources/C/sampleC.json', ])
])

def test_find_files_by_pattern(mock_change_dir, mock_lang_storage, pattern, expected):
    paths = list(find_files_by_pattern(mock_change_dir, pattern, LANGUAGE_EN, remote_content_type_codes))

    assert len(paths) == len(expected)
    for path in paths:
        assert path.posix_path in expected


@pytest.mark.parametrize('path,expected', [
    ('./path/some-path/Resource.Name.resx', 'resx'),
    ('./path/some-path/Resource.json', 'json'),
    ('./path/some-path/Resource.That.Has.Many.Extensions.json.yml', 'yml'),
])
def test_file_extension(path, expected):
    f = TranslationFile(path, "en-nz", "./")
    assert f.extension == expected


def test_add_project_file_formats():
    inbound = {
        'resx': ('resx',),
        'plaintext': ('txt', 'text',),
    }

    result = add_project_file_formats(inbound)

    assert result['resx'] == 'resx'
    assert result['txt'] == 'plaintext'

