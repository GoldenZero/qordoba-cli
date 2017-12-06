from i18n_base import get_files_in_dir_with_subdirs, save_dict_to_JSON, get_root_path, ignore_files, filter_config_files, get_lexer_from_config

import codecs
import re

import datetime

now = datetime.datetime.now()
date = now.strftime("%Y%m%d%H%M")
from collections import defaultdict
import logging
log = logging.getLogger('qordoba')

import pygments
import os
from pygments.lexers import get_lexer_by_name, guess_lexer, get_all_lexers, \
    load_lexer_from_file, get_lexer_for_filename, find_lexer_class_for_filename

"""
 The Extract Handler takes in a directory and extracts stringliterals file by file
 input: Directory of the files
 optional input: custom lexer. Either specify a pygments lexer (e.g. "html", "python" or call one of qordobas custom Lexers eg. "NonJunk")
 output: location where the JSON report is stored

 """

LEXER_STRINGS = dict()
# JS
LEXER_STRINGS["<class 'pygments.lexers.javascript.JavascriptLexer'>"] = ("Token.Literal.String.Single",)
LEXER_STRINGS["<pygments.lexers.JavascriptLexer with {'stripall': True}>"] = ("Token.Literal.String.Single",)
# Scala
LEXER_STRINGS["<class 'pygments.lexers.scala.ScalaLexer'>"] = ("Token.Literal.String",)
LEXER_STRINGS["<pygments.lexers.ScalaLexer with {'stripall': True}>"] = ("Token.Literal.String",)
# Ruby
LEXER_STRINGS["<class 'pygments.lexers.ruby.RubyLexer'>"] = (
"Token.Literal.String.Other", "Token.Literal.String.Double")
LEXER_STRINGS["<pygments.lexers.RubyLexer with {'stripall': True}>"] = (
"Token.Literal.String.Other", "Token.Literal.String.Double",)
#C sharp
LEXER_STRINGS["<class 'pygments.lexers.csharp.CSharpLexer'>"] = ("Token.Literal.String",)
LEXER_STRINGS["<pygments.lexers.CSharpLexer with {'stripall': True}>"] = ("Token.Literal.String",)



# 'pygments.lexers.javascript.JavascriptLexer'


def get_lexer(file_name, code, lexer_custom=None):
    # finding the right lexer for filename otherwise guess
    lexer = find_lexer_class_for_filename(file_name)
    if lexer is None and not file_name.endswith('.pyc'):
        try:
            lexer = get_lexer_for_filename(file_name)
        except ValueError:
            lexer = None
    if lexer is None:
        lexer = guess_lexer(file_name)

    if lexer_custom:  # if custom lexer is given e.g. pygments "html" or custom e.g. "nonjunk"
        rel_path = "../pygments_custom/" + lexer_custom + ".py"
        path_to_custom_lexer = get_root_path(rel_path)
        path_to_custom_lexer_clean = path_to_custom_lexer.replace("commands/../", '')
        try:
            lexer = get_lexer_by_name(lexer_custom, stripall=True)
        except pygments.util.ClassNotFound:
            lexer = load_lexer_from_file(path_to_custom_lexer_clean, lexer_custom, stripall=True)
        except NameError:
            lexer = load_lexer_from_file(path_to_custom_lexer_clean, lexer_custom, stripall=True)
        except AttributeError:
            lexer = load_lexer_from_file(path_to_custom_lexer_clean, lexer_custom, stripall=True)

        log.info(
            "Custom Lexer defined: `{lexer_custom}`. File `{file}`.".format(lexer_custom=lexer_custom, file=file_name))

    log.info("Lexer is {lexer} for file `{file}`.".format(lexer=lexer, file=file_name))
    return lexer


def extract(curdir, input_dir=None, report_dir=None, lexer_custom=None, bulk_report=False):
    # first getting all files in directory, than iteration
    no_files = False
    files = get_files_in_dir_with_subdirs(input_dir)
    files = ignore_files(files)

    # load i18n-ml and dismiss files which are specified to be ignored
    files = filter_config_files(files)

    if not files:
        no_files = True
        log.info("Seems like you have no file in your directory {}".format(input_dir))

    if bulk_report:  # if True, the report will reflect all files as bulk. no single report per file
        json_report = defaultdict(dict)

    for file_ in files:
        if not bulk_report:
            json_report = defaultdict(dict)

        count = 0
        f = codecs.open(file_, 'r')
        code = f.read()
        file_name = file_.split('/')[-1]

        if not lexer_custom: # cmd line input prioritized
            lexer_custom = get_lexer_from_config(file_)

        lexer = get_lexer(file_name, code, lexer_custom=lexer_custom)

        # depending on type of lexer class lexer has to be called or not (lexer() vs. lexer)
        try:
            results_generator = lexer.get_tokens_unprocessed(code)
        except TypeError:
            results_generator = lexer().get_tokens_unprocessed(code)

        token_format = None
        for item in results_generator:  # unpacking content of generator

            pos, token, value = item
            '''filter for stringliterals. 
            Scala's token is e.g. Stringliteral,but for Python it is Token.text
            For some languages custom filters are applyied. Default is token.text'''
            lexer_stringliteral_def = str(lexer)
            token_format = LEXER_STRINGS.get(lexer_stringliteral_def, ("Token.Text",))
            if any(x in str(token) for x in token_format) and not re.match(r'\n', value) and value.strip() != '':

                pos_start, token, value = item
                value = value.decode('utf-8').strip()
                # calculating fileline of string based on character position of entire file
                file_chunk = code[:pos_start]
                start_line = file_chunk.count("\n")
                multilinestring = value.count("\n")
                end_line = start_line + multilinestring
                json_report[file_][count] = {"value": value, "start_line": start_line + 1, "end_line": end_line + 1}
                count += 1

        log.info("Strings extracted! \n (pygments-token: {}) ".format(token_format[0]))
        if not bulk_report:
            file_path = report_dir + '/qordoba-report-' + file_name + "-" + date + '.json'
            save_dict_to_JSON(file_path, json_report)
            log.info("Report saved in: `{}`".format(file_path))

    # creating report file for bulk
    if bulk_report and not no_files:
        file_path = report_dir + '/qordoba-bulkreport-' + date + '.json'
        save_dict_to_JSON(file_path, json_report)
        log.info("Bulk-Report saved for all files in: `{}`".format(file_path))
