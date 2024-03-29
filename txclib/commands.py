# -*- coding: utf-8 -*-
"""
In this file we have all the top level commands for the transifex client.
Since we're using a way to automatically list them and execute them, when
adding code to this file you must take care of the following:
 * Added functions must begin with 'cmd_' followed by the actual name of the
   command being used in the command line (eg cmd_init)
 * The description for each function that we display to the user is read from
   the func_doc attribute which reads the doc string. So, when adding
   docstring to a new function make sure you add an oneliner which is
   descriptive and is meant to be seen by the user.
 * When including libraries, it's best if you include modules instead of
   functions because that way our function resolution will work faster and the
   chances of overlapping are minimal
 * All functions should use the OptionParser and should have a usage and
   descripition field.
"""
import os
import re, shutil
import sys
from optparse import OptionParser, OptionGroup
import ConfigParser


from txclib import utils, project
from txclib.utils import parse_json, compile_json, relpath
from txclib.config import OrderedRawConfigParser
from txclib.exceptions import UnInitializedError


def cmd_init(argv, path_to_tx):
    "Initialize a new transifex project."

    # Current working dir path
    usage="usage: %prog [tx_options] init <path>"
    description="This command initializes a new project for use with"\
        " transifex. It is recommended to execute this command in the"\
        " top level directory of your project so that you can include"\
        " all files under it in transifex. If no path is provided, the"\
        " current working dir will be used."
    parser = OptionParser(usage=usage, description=description)
    parser.add_option("--host", action="store", dest="host",
        default=None, help="Specify a default Transifex host.")
    parser.add_option("--user", action="store", dest="user",
        default=None, help="Specify username for Transifex server.")
    parser.add_option("--pass", action="store", dest="password",
        default=None, help="Specify password for Transifex server.")
    (options, args) = parser.parse_args(argv)

    if len(args) > 1:
        parser.error("Too many arguments were provided. Aborting...")

    if args:
        path_to_tx = args[0]
    else:
        path_to_tx = os.getcwd()

    if os.path.isdir(os.path.join(path_to_tx,".tx")):
        utils.MSG("tx: There is already a tx folder!")
        reinit = raw_input("Do you want to delete it and reinit the project? [y/N]: ")
        while (reinit != 'y' and reinit != 'Y' and reinit != 'N' and reinit != 'n' and reinit != ''):
            reinit = raw_input("Do you want to delete it and reinit the project? [y/N]: ")
        if not reinit or reinit in ['N', 'n', 'NO', 'no', 'No']:
            return
        # Clean the old settings
        # FIXME: take a backup
        else:
            rm_dir = os.path.join(path_to_tx, ".tx")
            shutil.rmtree(rm_dir)

    utils.MSG("Creating .tx folder...")
    os.mkdir(os.path.join(path_to_tx,".tx"))

    # Handle the credentials through transifexrc
    home = os.path.expanduser("~")
    txrc = os.path.join(home, ".transifexrc")
    config = OrderedRawConfigParser()

    default_transifex = "https://www.transifex.net"
    transifex_host = options.host or raw_input("Transifex instance [%s]: " % default_transifex)

    if not transifex_host:
        transifex_host = default_transifex
    if not transifex_host.startswith(('http://', 'https://')):
        transifex_host = 'https://' + transifex_host

    config_file = os.path.join(path_to_tx, ".tx", "config")
    if not os.path.exists(config_file):
        # The path to the config file (.tx/config)
        utils.MSG("Creating skeleton...")
        config = OrderedRawConfigParser()
        config.add_section('main')
        config.set('main', 'host', transifex_host)
        # Touch the file if it doesn't exist
        utils.MSG("Creating config file...")
        fh = open(config_file, 'w')
        config.write(fh)
        fh.close()

    prj = project.Project(path_to_tx)
    prj.getset_host_credentials(transifex_host, user=options.user,
        password=options.password)
    prj.save()

    utils.MSG("Done.")


def cmd_set(argv, path_to_tx):
    "Add local or remote files under transifex"

    class EpilogParser(OptionParser):
       def format_epilog(self, formatter):
           return self.epilog

    usage="usage: %prog [tx_options] set [options] [args]"
    description="This command can be used to create a mapping between files"\
        " and projects either using local files or using files from a remote"\
        " Transifex server."
    epilog="\nExamples:\n"\
        " To set the source file:\n  $ tx set -r project.resource --source -l en <file>\n\n"\
        " To set a single translation file:\n  $ tx set -r project.resource -l de <file>\n\n"\
        " To automatically detect and assign translation files:\n"\
        "  $ tx set --auto-local -r project.resource 'expr'\n\n"\
        " To automatically detect and assign the source files and translations:\n"\
        "  $ tx set --auto-local -r project.resource 'expr' --source-lang en\n\n"\
        " To set a specific file as a source and auto detect translations:\n"\
        "  $ tx set --auto-local -r project.resource 'expr' --source-lang en"\
        " --source-file <file>\n\n"\
        " To set a remote release/resource/project:\n"\
        "  $ tx set --auto-remote <transifex-url>\n"
    parser = EpilogParser(usage=usage, description=description, epilog=epilog)
    parser.add_option("--auto-local", action="store_true", dest="local",
        default=False, help="Used when auto configuring local project.")
    parser.add_option("--auto-remote", action="store_true", dest="remote",
        default=False, help="Used when adding remote files from Transifex"
        " server.")
    parser.add_option("-r","--resource", action="store", dest="resource",
        default=None, help="Specify the slug of the resource that you're"
            " setting up (This must be in the following format:"
            " `project_slug.resource_slug`).")
    parser.add_option("--source", action="store_true", dest="is_source",
        default=False, help="Specify that added file a source file [doesn't"
        " work with the --auto-* commands].")
    parser.add_option("-l","--language", action="store", dest="language",
        default=None, help="Specify which translations you want to pull"
        " [doesn't work with the --auto-* commands].")
    group = OptionGroup(parser, "Extended options", "These options can only be"
        " used with the --auto-local command.")
    group.add_option("-s","--source-language", action="store",
        dest="source_language",
        default=None, help="Specify the source language of a resource"
        " [requires --auto-local].")
    group.add_option("-f","--source-file", action="store", dest="source_file",
        default=None, help="Specify the source file of a resource [requires"
        " --auto-local].")
    group.add_option("--execute", action="store_true", dest="execute",
        default=False, help="Execute commands [requires --auto-local].")
    parser.add_option_group(group)

    (options, args) = parser.parse_args(argv)

    # Implement options/args checks
    # TODO !!!!!!!

    # if --auto is true
    if options.local:
        try:
            expression = args[0]
        except IndexError:
            parser.error("Please specify an expression.")
        if not options.resource:
            parser.error("Please specify a resource")
        if not options.source_language:
            parser.error("Please specify a source language.")
        if not '<lang>' in expression:
            parser.error("The expression you have provided is not valid.")
        if not utils.valid_slug(options.resource):
            parser.error("Invalid resource slug. The format is <project_slug>"\
                ".<resource_slug> and the valid characters include [_-\w].")
        _auto_local(path_to_tx, options.resource,
            source_language=options.source_language,
            expression = expression, source_file=options.source_file,
            execute=options.execute, nosource=False, regex=False)
    elif options.remote:
        try:
            url = args[0]
        except IndexError:
            parser.error("Please specify an remote url")
        _auto_remote(path_to_tx, url)
    # if we have --source, we set source
    elif options.is_source:
        resource = options.resource
        if not resource:
            parser.error("You must specify a resource name with the"
                " -r|--resource flag.")

        lang = options.language
        if not lang:
            parser.error("Please specify a source language.")

        if len(args) != 1:
            parser.error("Please specify a file.")

        if not utils.valid_slug(resource):
            parser.error("Invalid resource slug. The format is <project_slug>"\
                ".<resource_slug> and the valid characters include [_-\w].")

        file = args[0]
        # Calculate relative path
        path_to_file = relpath(file, path_to_tx)
        _set_source_file(path_to_tx, resource, options.language, path_to_file)

    else:
        resource = options.resource
        lang = options.language

        if not resource or not lang:
            parser.error("You need to specify a resource and a language for the"
                " translation")

        if len(args) != 1:
            parser.error("Please specify a file")

        # Calculate relative path
        path_to_file = relpath(args[0], path_to_tx)

        try:
            _go_to_dir(path_to_tx)
        except UnInitializedError, e:
            utils.ERRMSG(e)
            return

        if not utils.valid_slug(resource):
            parser.error("Invalid resource slug. The format is <project_slug>"\
                ".<resource_slug> and the valid characters include [_-\w].")

        _set_translation(path_to_tx, resource, lang, path_to_file)

    utils.MSG("Done.")

    return


def _auto_local(path_to_tx, resource, source_language, expression, execute=False, source_file=None,
    nosource=False, regex=False):
    """
    Auto configure local project
    """

    # The path everything will be relative to
    curpath = os.path.abspath(os.curdir)

    # Force expr to be a valid regex expr (escaped) but keep <lang> intact
    expr_re = utils.regex_from_filefilter(expression, curpath)
    expr_rec = re.compile(expr_re)

    if not execute:
        utils.MSG("Only printing the commands which will be run if the "
                  "--execute switch is specified.")

    # First, let's construct a dictionary of all matching files.
    # Note: Only the last matching file of a language will be stored.
    translation_files = {}
    for root, dirs, files in os.walk(curpath):
        for f in files:
            f_path = os.path.abspath(os.path.join(root, f))
            match = expr_rec.match(f_path)
            if match:
                lang = match.group(1)
                f_path = os.path.abspath(f_path)
                if lang == source_language and not source_file:
                    source_file = f_path
                else:
                    translation_files[lang] = f_path

    # The set_source_file commands needs to be handled first.
    # If source file search is enabled, go ahead and find it:
    if not nosource:
        if not source_file:
            raise Exception("Could not find a source language file. Please run"
                " set --source manually and then re-run this command or provide"
                " the source file with the -s flag.")
        if execute:
            utils.MSG("Updating source for resource %s ( %s -> %s )." % (resource,
                source_language, relpath(source_file, path_to_tx)))
            _set_source_file(path_to_tx, resource, source_language,
                relpath(source_file, path_to_tx))
        else:
            utils.MSG('\ntx set --source -r %(res)s -l %(lang)s %(file)s\n' % {
                'res': resource,
                'lang': source_language,
                'file': relpath(source_file, curpath)})

    prj = project.Project(path_to_tx)
    root_dir = os.path.abspath(path_to_tx)

    if execute:
        try:
            prj.config.get("%s" % resource, "source_file")
        except ConfigParser.NoSectionError:
            raise Exception("No resource with slug \"%s\" was found.\nRun 'tx set --auto"
                "-local -r %s \"expression\"' to do the initial configuration." % resource)

    # Now let's handle the translation files.
    if execute:
        utils.MSG("Updating file expression for resource %s ( %s )." % (resource,
            expression))
        # Eval file_filter relative to root dir
        file_filter = relpath(os.path.join(curpath, expression),
            path_to_tx)
        prj.config.set("%s" % resource, "file_filter", file_filter)
    else:
        for (lang, f_path) in sorted(translation_files.items()):
            utils.MSG('tx set -r %(res)s -l %(lang)s %(file)s' % {
                'res': resource,
                'lang': lang,
                'file': relpath(f_path, curpath)})

    prj.save()


def _auto_remote(path_to_tx, url):
    """
    Initialize a remote release/project/resource to the current directory.
    """
    utils.MSG("Auto configuring local project from remote URL...")

    type, vars = utils.parse_tx_url(url)
    prj = project.Project(path_to_tx)
    username, password = prj.getset_host_credentials(vars['hostname'])

    if type == 'project':
        utils.MSG("Getting details for project %s" % vars['project'])
        proj_info = utils.get_details('project_details',
            username, password,
            hostname = vars['hostname'], project = vars['project'])
        resources = [ '.'.join([vars['project'], r['slug']]) for r in proj_info['resources'] ]
        utils.MSG("%s resources found. Configuring..." % len(resources))
    elif type == 'release':
        utils.MSG("Getting details for release %s" % vars['release'])
        rel_info = utils.get_details('release_details',
            username, password, hostname = vars['hostname'],
            project = vars['project'], release = vars['release'])
        resources = []
        for r in rel_info['resources']:
            if r.has_key('project_slug'):
                resources.append('.'.join([r['project_slug'], r['slug']]))
            else:
                resources.append('.'.join([vars['project'], r['slug']]))
        utils.MSG("%s resources found. Configuring..." % len(resources))
    elif type == 'resource':
        utils.MSG("Getting details for resource %s" % vars['resource'])
        resources = [ '.'.join([vars['project'], vars['resource']]) ]
    else:
        raise("Url '%s' is not recognized." % url)

    for resource in resources:
        utils.MSG("Configuring resource %s." % resource)
        proj, res = resource.split('.')
        res_info = utils.get_details('resource_details',
             username, password, hostname = vars['hostname'],
             project = proj, resource=res)
        try:
            source_lang = res_info['source_language']['code']
            i18n_type = res_info['i18n_type']
        except KeyError:
            raise Exception("Remote server seems to be running an unsupported version"
                " of Transifex. Either update your server software of fallback"
                " to a previous version of transifex-client.")
        prj.set_remote_resource(
            resource=resource,
            host = vars['hostname'],
            source_lang = source_lang,
            i18n_type = i18n_type)

    prj.save()


def cmd_push(argv, path_to_tx):
    "Push local files to remote server"
    usage="usage: %prog [tx_options] push [options]"
    description="This command pushes all local files that have been added to"\
        " Transifex to the remote server. All new translations are merged"\
        " with existing ones and if a language doesn't exists then it gets"\
        " created. If you want to push the source file as well (either"\
        " because this is your first time running the client or because"\
        " you just have updated with new entries), use the -f|--force option."\
        " By default, this command will push all files which are watched by"\
        " Transifex but you can filter this per resource or/and language."
    parser = OptionParser(usage=usage, description=description)
    parser.add_option("-l","--language", action="store", dest="languages",
        default=None, help="Specify which translations you want to push"
        " (defaults to all)")
    parser.add_option("-r","--resource", action="store", dest="resources",
        default=None, help="Specify the resource for which you want to push"
        " the translations (defaults to all)")
    parser.add_option("-f","--force", action="store_true", dest="force_creation",
        default=False, help="Push source files without checking modification"
        " times.")
    parser.add_option("--skip", action="store_true", dest="skip_errors",
        default=False, help="Don't stop on errors. Useful when pushing many"
        " files concurrently.")
    parser.add_option("-s", "--source", action="store_true", dest="push_source",
        default=False, help="Push the source file to the server.")

    parser.add_option("-t", "--translations", action="store_true", dest="push_translations",
        default=False, help="Push the translation files to the server")
    parser.add_option("--no-interactive", action="store_true", dest="no_interactive",
        default=False, help="Don't require user input when forcing a push.")

    (options, args) = parser.parse_args(argv)

    force_creation = options.force_creation

    if options.languages:
        languages = options.languages.split(',')
    else:
        languages = []

    if options.resources:
        resources = options.resources.split(',')
    else:
        resources = []

    skip = options.skip_errors

    # instantiate the project.Project
    prj = project.Project(path_to_tx)
    if not (options.push_source or options.push_translations):
        parser.error("You need to specify at least one of the -s|--source,"
            " -t|--translations flags with the push command.")

    prj.push(
        force=force_creation, resources=resources, languages=languages,
        skip=skip, source=options.push_source,
        translations=options.push_translations,
        no_interactive=options.no_interactive
    )

    utils.MSG("Done.")


def cmd_pull(argv, path_to_tx):
    "Pull files from remote server to local repository"
    usage="usage: %prog [tx_options] pull [options]"
    description="This command pulls all outstanding changes from the remote"\
        " Transifex server to the local repository. By default, only the"\
        " files that are watched by Transifex will be updated but if you"\
        " want to fetch the translations for new languages as well, use the"\
        " -a|--all option. (Note: new translations are saved in the .tx folder"\
        " and require the user to manually rename them and add then in "\
        " transifex using the set_translation command)."
    parser = OptionParser(usage=usage,description=description)
    parser.add_option("-l","--language", action="store", dest="languages",
        default=[], help="Specify which translations you want to pull"
        " (defaults to all)")
    parser.add_option("-r","--resource", action="store", dest="resources",
        default=[], help="Specify the resource for which you want to pull"
        " the translations (defaults to all)")
    parser.add_option("-a","--all", action="store_true", dest="fetchall",
        default=False, help="Fetch all translation files from server (even new"
        " ones)")
    parser.add_option("-s","--source", action="store_true", dest="fetchsource",
        default=False, help="Force the fetching of the source file (default:"
        " False)")
    parser.add_option("-f","--force", action="store_true", dest="force",
        default=False, help="Force download of translations files.")
    parser.add_option("--skip", action="store_true", dest="skip_errors",
        default=False, help="Don't stop on errors. Useful when pushing many"
        " files concurrently.")
    parser.add_option("--disable-overwrite", action="store_false",
        dest="overwrite", default=True,
        help="By default transifex will fetch new translations files and"\
            " replace existing ones. Use this flag if you want to disable"\
            " this feature")
    parser.add_option("--minimum-perc", action="store", type="int",
        dest="minimum_perc", default=0,
        help="Specify the minimum acceptable percentage of a translation "
             "in order to download it.")

    (options, args) = parser.parse_args(argv)

    if options.fetchall and options.languages:
        parser.error("You can't user a language filter along with the"\
            " -a|--all option")

    if options.languages:
        languages = options.languages.split(',')
    else:
        languages = []

    if options.resources:
        resources = options.resources.split(',')
    else:
        resources = []

    skip = options.skip_errors
    minimum_perc = options.minimum_perc or None

    try:
        _go_to_dir(path_to_tx)
    except UnInitializedError, e:
        utils.ERRMSG(e)
        return

    # instantiate the project.Project
    prj = project.Project(path_to_tx)
    prj.pull(
        languages=languages, resources=resources, overwrite=options.overwrite,
        fetchall=options.fetchall, fetchsource=options.fetchsource,
        force=options.force, skip=skip, minimum_perc=minimum_perc
    )

    utils.MSG("Done.")


def _set_source_file(path_to_tx, resource, lang, path_to_file):
    """Reusable method to set source file."""

    proj, res = resource.split('.')
    if not proj or not res:
        raise Exception("\"%s.%s\" is not a valid resource identifier. It should"
            " be in the following format project_slug.resource_slug." %
            (proj, res))

    if not lang:
        raise Exception("You haven't specified a source language.")

    try:
        _go_to_dir(path_to_tx)
    except UnInitializedError, e:
        utils.ERRMSG(e)
        return

    if not os.path.exists(path_to_file):
        raise Exception("tx: File ( %s ) does not exist." %
            os.path.join(path_to_tx, path_to_file))

    # instantiate the project.Project
    prj = project.Project(path_to_tx)
    root_dir = os.path.abspath(path_to_tx)

    if root_dir not in os.path.normpath(os.path.abspath(path_to_file)):
        raise Exception("File must be under the project root directory.")

    utils.MSG("Setting source file for resource %s.%s ( %s -> %s )." % (
        proj, res, lang, path_to_file))

    path_to_file = relpath(path_to_file, root_dir)

    prj = project.Project(path_to_tx)

    # FIXME: Check also if the path to source file already exists.
    try:
        try:
            prj.config.get("%s.%s" % (proj, res), "source_file")
        except ConfigParser.NoSectionError:
            prj.config.add_section("%s.%s" % (proj, res))
        except ConfigParser.NoOptionError:
            pass
    finally:
        prj.config.set("%s.%s" % (proj, res), "source_file",
           path_to_file)
        prj.config.set("%s.%s" % (proj, res), "source_lang",
            lang)

    prj.save()


def _set_translation(path_to_tx, resource, lang, path_to_file):
    """Reusable method to set translation file."""

    proj, res = resource.split('.')
    if not project or not resource:
        raise Exception("\"%s\" is not a valid resource identifier. It should"
            " be in the following format project_slug.resource_slug." %
            resource)

    try:
        _go_to_dir(path_to_tx)
    except UnInitializedError, e:
        utils.ERRMSG(e)
        return

    # Warn the user if the file doesn't exist
    if not os.path.exists(path_to_file):
        utils.MSG("Warning: File '%s' doesn't exist." % path_to_file)

    # instantiate the project.Project
    prj = project.Project(path_to_tx)
    root_dir = os.path.abspath(path_to_tx)

    if root_dir not in os.path.normpath(os.path.abspath(path_to_file)):
        raise Exception("File must be under the project root directory.")

    if lang ==  prj.config.get("%s.%s" % (proj, res), "source_lang"):
        raise Exception("tx: You cannot set translation file for the source language."
            " Source languages contain the strings which will be translated!")

    utils.MSG("Updating translations for resource %s ( %s -> %s )." % (resource,
        lang, path_to_file))
    path_to_file = relpath(path_to_file, root_dir)
    prj.config.set("%s.%s" % (proj, res), "trans.%s" % lang,
        path_to_file)

    prj.save()


def cmd_status(argv, path_to_tx):
    "Print status of current project"

    usage="usage: %prog [tx_options] status [options]"
    description="Prints the status of the current project by reading the"\
        " data in the configuration file."
    parser = OptionParser(usage=usage,description=description)
    parser.add_option("-r","--resource", action="store", dest="resources",
        default=[], help="Specify resources")

    (options, args) = parser.parse_args(argv)
    if options.resources:
        resources = options.resources.split(',')
    else:
        resources = []

    prj = project.Project(path_to_tx)
    resources = prj.get_chosen_resources(resources)
    resources_num = len(resources)
    for id, res in enumerate(resources):
        p, r = res.split('.')
        utils.MSG("%s -> %s (%s of %s)" % (p, r, id+1, resources_num))
        utils.MSG("Translation Files:")
        slang = prj.get_resource_option(res, 'source_lang')
        sfile = prj.get_resource_option(res, 'source_file') or "N/A"
        lang_map = prj.get_resource_lang_mapping(res)
        utils.MSG(" - %s: %s (%s)" % (utils.color_text(slang, "RED"),
            sfile, utils.color_text("source", "YELLOW")))
        files = prj.get_resource_files(res)
        fkeys = files.keys()
        fkeys.sort()
        for lang in fkeys:
            local_lang = lang
            if lang in lang_map.values():
                local_lang = lang_map.flip[lang]
            utils.MSG(" - %s: %s" % (utils.color_text(local_lang, "RED"),
                files[lang]))

        utils.MSG("")


def cmd_help(argv, path_to_tx):
    "List all available commands"

    usage="usage: %prog help command"
    description="Lists all available commands in the transifex command"\
        " client. If a command is specified, the help page of the specific"\
        " command is displayed instead."

    parser = OptionParser(usage=usage, description=description)

    (options, args) = parser.parse_args(argv)

    if len(args) > 1:
        parser.error("Multiple arguments received. Exiting...")

    # Get all commands
    fns = utils.discover_commands()

    # Print help for specific command
    if len(args) == 1:
        try:
            fns[argv[0]](['--help'], path_to_tx)
        except KeyError:
            utils.ERRMSG("Command %s not found" % argv[0])
    # or print summary of all commands

    # the code below will only be executed if the KeyError exception is thrown
    # becuase in all other cases the function called with --help will exit
    # instead of return here
    keys = fns.keys()
    keys.sort()

    utils.MSG("Transifex command line client.\n")
    utils.MSG("Available commands are:")
    for key in keys:
        utils.MSG("  %-15s\t%s" % (key, fns[key].func_doc))

    utils.MSG("\nFor more information run %s command --help" % sys.argv[0])


def cmd_delete(argv, path_to_tx):
    "Delete an accessible resource or translation in a remote server."

    class EpilogParser(OptionParser):
       def format_epilog(self, formatter):
           return self.epilog

    usage="usage: %prog [tx_options] delete OPTION [OPTIONS]"
    description="This command deletes either a resource (if no language has been specified)"
    " or specific translations for a resource in the remote server."
    epilog="\nExamples:\n"\
        " To delete a translation:\n  $ tx delete -r project.resource -l <lang_code>\n\n"\
        " To delete a resource:\n  $ tx delete -r project.resource\n"
    parser = EpilogParser(usage=usage, description=description, epilog=epilog)
    parser.add_option(
        "-r", "--resource", action="store", dest="resources", default=None,
        help="Specify the resource you want to delete (defaults to all)"
    )
    parser.add_option("-l","--language", action="store", dest="languages",
        default=None, help="Specify the translation you want to delete")
    parser.add_option(
        "--skip", action="store_true", dest="skip_errors", default=False,
        help="Don't stop on errors."
    )

    (options, args) = parser.parse_args(argv)

    if options.languages:
        languages = options.languages.split(',')
    else:
        languages = []

    if options.resources:
        resources = options.resources.split(',')
    else:
        resources = []

    skip = options.skip_errors

    prj = project.Project(path_to_tx)
    prj.delete(resources, languages, skip)
    utils.MSG("Done.")


def _go_to_dir(path):
    """Change the current working directory to the directory specified as
    argument.

    Args:
        path: The path to chdor to.
    Raises:
        UnInitializedError, in case the directory has not been initialized.
    """
    if path is None:
        raise UnInitializedError(
            "Directory has not been initialzied. "
            "Did you forget to run 'tx init' first?"
        )
    os.chdir(path)
