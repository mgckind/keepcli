import cmd
import sys
import os
import getpass
import pickle
import argparse
import gkeepapi
import yaml
import keepcli.kcliparser as kcliparser
from keepcli.version import __version__

try:
    input = raw_input
except NameError:
    pass


def without_color(line, color, mode=0):
    """This function does nothing to the input line.
    Just a ancillary function when there is not output color"""
    return line


try:
    from termcolor import colored as with_color

    def colored(line, color, mode=1):
        if mode == 1:
            return with_color(line, color)
        else:
            return line
except ImportError:
    colored = without_color

colors = {
    'gray': 'grey',
    'red': 'red',
    'green': 'green',
    'yellow': 'yellow',
    'darkblue': 'blue',
    'purple': 'magenta',
    'blue': 'cyan',
    'white': 'white'}

colorsGK = {
    'red': gkeepapi.node.ColorValue.Red,
    'green': gkeepapi.node.ColorValue.Green,
    'gray': gkeepapi.node.ColorValue.Gray,
    'white': gkeepapi.node.ColorValue.White,
    'yellow': gkeepapi.node.ColorValue.Yellow,
}

options_entries = ['all', 'notes', 'lists']
options_commands = ['note', 'list']
options_current = ['show', 'color', 'pin', 'unpin']
options_config = ['set']
true_options = ['true', 'yes', '1', 'y', 't']


def print_list(List, mode, only_unchecked=False):
    """
    Prints out checked followed by unchecked items from a list sorted by time of creation

    Parameters
    ----------
    List : gkeepapi.node.List
           The input list class
    mode : int
           mode to be used by colored to whether (mode=1) or not mode=0) use termcolor
    """
    try:
        times_unchecked = [item.timestamps.created for item in List.unchecked]
    except:
        print('List printing is not supported without sync, please sync your data')
        return

    unchecked = [x for _, x in
                 sorted(zip(times_unchecked, List.unchecked), key=lambda pair: pair[0])]
    times_checked = [item.timestamps.created for item in List.checked]
    checked = [x for _, x in sorted(zip(times_checked, List.checked), key=lambda pair: pair[0])]
    print('Unchecked items: {} out of {}'.format(len(unchecked), len(checked)+len(unchecked)))
    for i in unchecked:
        print(colored(i, "red", mode))
    if only_unchecked:
        return
    for i in checked:
        print(colored(i, "green", mode))


def get_color(entry, mode, color_only=False):
    """
    Get the color conversion from gkeeppii colors to termcolor colors

    Parameters
    ----------
    entry : gkeepapi.node
        The Note class
    mode : int
        Whether to use colors (mode = 1) or not (mode = 0)
    color_only : bool, optional
        If True it just returns the colot to be used, if False it returns the colord title

    Returns
    -------
    str
        Color string or a colored title depending on the value for color_only
    """
    try:
        color = colors[entry.color.name.lower()]
    except KeyError:
        color = "white"
    if color_only:
        return color
    else:
        return colored(entry.title, color, mode)


class GKeep(cmd.Cmd):
    """ The main cmd class"""
    def __init__(self, auth_file, conf_file, offline=False):
        # super().__init__()
        cmd.Cmd.__init__(self)
        self.offline = offline
        self.auth_file = auth_file
        self.conf_file = conf_file
        self.current = None
        self.update_config()
        self.kcli_path = os.path.dirname(self.auth_file)
        if self.offline:
            self.autosync = False
        self.prompt = 'keepcli [] ~> '
        self.keep = gkeepapi.Keep()
        if not self.offline:
            try:
                with open(auth_file, 'r') as auth:
                    conn = yaml.load(auth)
            except FileNotFoundError:
                conn = {}
                print('\nAuth file {} not found, will create one... '
                      '(Google App password is strongly recommended)\n'.format(auth_file))
                conn['user'] = input('Enter username : ')
                conn['passwd'] = getpass.getpass(prompt='Enter password : ')
            print('\nLogging {} in...\n'.format(colored(conn['user'], 'green', self.termcolor)))
            try:
                self.connect = self.keep.login(conn['user'], conn['passwd'])
                with open(auth_file, 'w') as auth:
                    yaml.dump(conn, auth, default_flow_style=False)
                self.username = conn['user']
            except (gkeepapi.exception.LoginException, ValueError) as e:
                if e.__class__.__name__ == 'ValueError':
                    print("\n Can't login and sync from empty content, please create a note online")
                else:
                    print('\nUser/Password not valid (auth file : {})\n'.format(auth_file))
                sys.exit(1)
            self.do_refresh(None, force_sync=True)
        else:
            print(colored('\nRunning Offline\n', "red", self.termcolor))
        self.complete_ul = self.complete_useList
        self.complete_un = self.complete_useNote
        self.do_useNote(self.conf['current'])
        self.do_useList(self.conf['current'])
        self.doc_header = colored(
                          ' *Other Commands*', "cyan", self.termcolor) + ' (type help <command>):'
        self.keep_header = colored(
                          ' *Keep Commands*', "cyan", self.termcolor) + ' (type help <command>):'

    def update_config(self):
        """ Update config parameters into current session"""
        with open(self.conf_file, 'r') as confile:
            self.conf = yaml.load(confile)
        self.termcolor = 1 if self.conf['termcolor'] else 0
        self.autosync = True if self.conf['autosync'] else False

    def do_help(self, arg):
        """
        List available commands with "help" or detailed help with "help cmd".

        Usage:
            ~> help <command>
        """
        if arg:
            try:
                func = getattr(self, 'help_' + arg)
            except AttributeError:
                try:
                    doc = getattr(self, 'do_' + arg).__doc__
                    if doc:
                        doc = str(doc)
                        if doc.find('KEEP:') > -1:
                            doc = doc.replace('KEEP:', '')
                        self.stdout.write("%s\n" % str(doc))
                        return
                except AttributeError:
                    pass
                self.stdout.write("%s\n" % str(self.nohelp % (arg,)))
                return
            func()
        else:
            # self.stdout.write(str(self.intro) + "\n")
            names = self.get_names()
            cmds_doc = []
            cmds_undoc = []
            cmds_keep = []
            help = {}
            for name in names:
                if name[:5] == 'help_':
                    help[name[5:]] = 1
            names.sort()
            # There can be duplicates if routines overridden
            prevname = ''
            for name in names:
                if name[:3] == 'do_':
                    if name == prevname:
                        continue
                    prevname = name
                    cmd = name[3:]
                    if cmd in help:
                        cmds_doc.append(cmd)
                        del help[cmd]
                    elif getattr(self, name).__doc__:
                        doc = getattr(self, name).__doc__
                        if 'KEEP:' in doc:
                            cmds_keep.append(cmd)
                        else:
                            cmds_doc.append(cmd)
                    else:
                        cmds_undoc.append(cmd)
            self.stdout.write("%s\n" % str(self.doc_leader))
            self.print_topics(self.keep_header, cmds_keep, 80)
            self.print_topics(self.doc_header, cmds_doc, 80)
            # self.print_topics('Misc', list(help.keys()), 80)
            print()

    def print_topics(self, header, cmds, maxcol):
        if header is not None:
            if cmds:
                self.stdout.write("%s\n" % str(header))
                if self.ruler:
                    self.stdout.write("%s\n" % str(self.ruler * maxcol))
                self.columnize(cmds, maxcol - 1)
                self.stdout.write("\n")

    def emptyline(self):
        """Do nothing when there is no input """
        pass

    def do_version(self, arg):
        """
        Print current keepcli version

        Usage:
            ~> version
        """
        print('\nCurrent version: {}'.format(__version__))

    def do_shortcuts(self, arg):
        """
        Undocumented shortcuts used in keepcli.

        ul: useList              --> select a list
        un: useNote              --> select a note
        ai: addItem              --> add item to a current List
        ai: addText              --> add text to a current Note
        cs: current show         --> shows current List/Note
        el: entries list --show  --> show all unchecked items from all active lists
        """
        self.do_help('shortcuts')

    def do_refresh(self, arg, force_sync=False):
        """
        Sync and Refresh content from Google Keep

        Usage:
            ~> refresh
        """
        sync = True if self.autosync else False
        if force_sync:
            sync = True
        if not self.offline:
            if sync:
                print('Syncing...')
                self.keep.sync()
        else:
            print(colored('Cannot sync while offline', 'red', self.termcolor))
        self.entries = self.keep.all()
        self.titles = []
        self.lists = []
        self.notes = []
        self.lists_obj = []
        self.notes_obj = []
        for n in self.entries:
            if not n.trashed:
                self.titles.append(n.title)
                if n.type.name == 'List':
                    self.lists.append(n.title)
                    self.lists_obj.append(n)
                if n.type.name == 'Note':
                    self.notes.append(n.title)
                    self.notes_obj.append(n)

    def do_sync(self, arg):
        """
        Sync data with the server, it needs online access

        Usage:
            ~> sync
        """
        self.do_refresh(None, force_sync=True)

    def do_whoami(self, arg):
        """
        Print information about user

        Usage:
            ~> whoami
        """
        print()
        allitem = sum([len(n.items) for n in self.lists_obj])
        uncheck = sum([len(n.unchecked) for n in self.lists_obj])
        print('User         : {}'.format(self.username))
        print('Entries      : {} Notes and {} Lists'.format(len(self.notes), len(self.lists)))
        print('Uncheck Items: {} out of {}'.format(uncheck, allitem))
        print()

    def do_cs(self, arg):
        self.do_current('show')

    def do_ai(self, arg):
        self.do_addItem(arg)

    def do_at(self, arg):
        self.do_addText(arg)

    def do_ul(self, arg):
        self.do_useList(arg)

    def do_un(self, arg):
        self.do_useNote(arg)

    def do_el(self, arg):
        self.do_entries('lists --show')

    def do_exit(self, arg):
        """
        Exit the program
        """
        with open(self.conf_file, 'w') as conf:
            yaml.dump(self.conf, conf, default_flow_style=False)
        return True

    def do_config(self, arg):
        """
        Print and set configuration options

        Usage:
            ~> config                       : shows current configuration
            ~> config set <key>=<value>     : sets <key> to <value> and updates config file
        Ex:
            ~> config set termcolor=true    : sets termcolor to true
        """
        line = "".join(arg.split())
        if arg == '':
            print('Current configuration:\n')
            for item in self.conf.items():
                print('{} : {}'.format(*item))
                print()
        if 'set' in line:
            action = line[line.startswith('set') and len('set'):].lstrip()
            action = "".join(action.split())
            if '=' in action:
                key, value = action.split('=')
            elif ':' in action:
                key, value = action.split(':')
            else:
                print('format key = value')
                return
            value_b = True if value.lower() in true_options else False
            if key in self.conf:
                self.conf[key] = value_b
                with open(self.conf_file, 'w') as conf:
                    yaml.dump(self.conf, conf, default_flow_style=False)
                self.update_config()
            else:
                print('{} is not a valid configuration option'.format(key))

    def complete_config(self, text, line, start_index, end_index):
        if text:
            return [option for option in options_config if option.startswith(text)]
        else:
            return options_config

    def do_entries(self, arg):
        """
        KEEP:Shows  all lists and notes for the user

        Usage:
            ~> entries all   : Included archived and deleted items
            ~> entries lists : Shows only lists
            ~> entries notes : Shows only notes

        Optional Arguments:
            --show           : Shows all unchecked items for all Active lists

        Ex:
            ~> entries lists --show

        Note:
            Use shortcut el to replace entries lists --show
            ~> el
        """
        line = "".join(arg.split())
        show = True if '--show' in line else False
        active = True
        notes = False
        lists = False
        if 'all' in line:
            active = False
        elif 'notes' in line:
            notes = True
        elif 'lists' in line:
            lists = True
        print()
        try:
            _ = self.entries
        except AttributeError:
            if self.offline:
                print('In offline mode, you need to load data first, use the load command')
                print()
                return
        pinned = []
        unpinned = []
        for n in self.entries:
            pinned.append(n) if n.pinned else unpinned.append(n)

        if len(pinned) > 0:
            print('* Pinned entries *: \n')
        for n in pinned:
            display = True
            if n.trashed:
                status = 'Deleted'
                if active or notes or lists:
                    display = False
            else:
                status = 'Active'
                if notes and n.type.name == 'List':
                    display = False
                if lists and n.type.name == 'Note':
                    display = False
            data = {'title': get_color(n, self.termcolor), 'status': status, 'type': n.type.name}
            if display:
                print('- {title: <30} {status: <10}  [ {type} ]'.format(**data))
            if show and lists and n.type.name == 'List':
                self.do_clear(None)
                print_list(n, self.termcolor, only_unchecked=True)
                print()
        print()
        if len(unpinned) > 0:
            print('* Unpinned entries *: \n')
        for n in unpinned:
            display = True
            if n.trashed:
                status = 'Deleted'
                if active or notes or lists:
                    display = False
            else:
                status = 'Active'
                if notes and n.type.name == 'List':
                    display = False
                if lists and n.type.name == 'Note':
                    display = False
            try:
                data = {'title': colored(n.title, colors[n.color.name.lower()], self.termcolor), 'status': status,
                        'type': n.type.name}
            except KeyError:
                data = {'title': colored(n.title, 'white', self.termcolor), 'status': status,
                        'type': n.type.name}
            if display:
                print('- {title: <30} {status: <10}  [ {type} ]'.format(**data))
            if show and lists and n.type.name == 'List':
                self.do_clear(None)
                print_list(n, self.termcolor, only_unchecked=True)
                print()
        print()

    def complete_entries(self, text, line, start_index, end_index):
        if text:
            return [option for option in options_entries if option.startswith(text)]
        else:
            return options_entries

    def do_show(self, arg):
        """
        KEEP:Print content os List/Note

        Usage:
            ~> show <name of list/note>
        """
        if arg == '' and self.current is None:
            self.do_help('show')
            return
        if arg == '' and self.current is not None:
            arg = self.current.title
        for n in self.entries:
            if arg == n.title:
                print()
                title = colored('============{:=<30}'.format(' '+n.title+' '),
                                get_color(n, self.termcolor, True), self.termcolor)
                print(title)
                print()
                print(n.text) if n.type.name == 'Note' else print_list(n, self.termcolor)
                bottom = colored('============{:=<30}'.format(' '+n.title+' '),
                                 get_color(n, self.termcolor, True), self.termcolor)
                print(bottom)

                print()

    def complete_show(self, text, line, start_index, end_index):
        if text:
            return [option for option in self.titles if option.startswith(text)]
        else:
            return self.titles

    def do_delete(self, arg):
        """
        KEEP:Delete entry based on its name. Works for lists and notes

        Usage:
            ~> delete <name of list/note>
        """
        for n in self.entries:
            if arg == n.title:
                print()
                question = 'Are you sure you want to delete {} ?. '.format(n.title)
                question += 'This is irreversible [spell out yes]: '
                question = colored(question, 'red', self.termcolor)
                if (input(question).lower() in ['yes']):
                    print('{} Deleted'.format(n.title))
                    n.delete()
                    self.do_refresh(None)
                print()

    def complete_delete(self, text, line, start_index, end_index):
        if text:
            return [option for option in self.titles if option.startswith(text)]
        else:
            return self.titles

    def do_current(self, arg):
        """
        KEEP:Show current list or note being used

        Usage:
            ~> current                : Prints current note/list
            ~> current show           : Prints content of current note/list
            ~> current color <color>  : Change color card of entry
            ~> current pin            : Pin current note/list
            ~> current unpin          : Unpin current note/list

        Note:
            Use shortcut cs to current show
            ~> cs
        """
        if self.current is None:
            print('Not Note or List is selected, use the command: useList or useNote')
            return
        print('Current entry: {}'.format(get_color(self.current, self.termcolor)))
        if 'show' in arg:
            self.do_show(self.current.title)
        if 'pin' in arg:
            self.current.pinned = True
            self.do_refresh(None)
        if 'unpin' in arg:
            self.current.pinned = False
            self.do_refresh(None)
        if 'color' in arg:
            color = arg[arg.startswith('color') and len('color'):].lstrip()
            try:
                self.current.color = colorsGK[color]
                self.do_refresh(None)
            except:
                print('Color {} do not exist'.format(color))

    def complete_current(self, text, line, start_index, end_index):
        if 'color' in line:
            if text:
                return [option for option in list(colorsGK.keys()) if option.startswith(text)]
            else:
                return list(colorsGK.keys())
        else:
            if text:
                return [option for option in options_current if option.startswith(text)]
            else:
                return options_current

    def do_create(self, arg):
        """
        KEEP:Create a note or a list

        Usage:
            ~> create note <title>
            ~> create list <title>
        """
        line = arg
        if line.startswith('note'):
            title = line[line.startswith('note') and len('note'):].lstrip()
            print('create note: {}'.format(title))
            self.keep.createNote(title)
            self.do_refresh(None)
        if line.startswith('list'):
            title = line[line.startswith('list') and len('list'):].lstrip()
            print('create list: {}'.format(title))
            self.keep.createList(title)
            self.do_refresh(None)

    def complete_create(self, text, line, start_index, end_index):
        if text:
            return [option for option in options_commands if option.startswith(text)]
        else:
            return options_commands

    def do_useList(self, arg):
        """
        KEEP:Select a list to use, so items can be added, checked or unchecked

        Usage:
            ~> useList <title>

        Note:
            Use shortcut ul to select current list
            ~> ul <title>
        """
        for n in self.entries:
            if arg == n.title and arg in self.lists:
                print()
                print('Current List set to: {}'.format(n.title))
                self.current = n
                self.conf['current'] = n.title
                self.prompt = 'keepcli [{}] ~> '.format(n.title[:15] + (n.title[15:] and '...'))
                self.current_checked = [i.text for i in n.checked]
                self.current_unchecked = [i.text for i in n.unchecked]
                self.current_all_items = self.current_checked + self.current_unchecked

    def complete_useList(self, text, line, start_index, end_index):
        if text:
            return [option for option in self.lists if option.startswith(text)]
        else:
            return self.lists

    def do_useNote(self, arg):
        """
        KEEP:Select a note to use, so text can be append to current text

        Usage:
            ~> useNote <title>

        Note:
            Use shortcut un to select current note
            ~> un <title>
        """
        for n in self.entries:
            if arg == n.title and arg in self.notes:
                print()
                print('Current Note set to: {}'.format(n.title))
                self.prompt = 'keepcli [{}] ~> '.format(n.title[:15] + (n.title[15:] and '...'))
                self.current = n
                self.conf['current'] = n.title

    def complete_useNote(self, text, line, start_index, end_index):
        if text:
            return [option for option in self.notes if option.startswith(text)]
        else:
            return self.notes

    def do_addText(self, arg):
        """
        KEEP:Add text to the current note

        Usage:
            ~> addText <This is my example text>
        """
        if self.current is None:
            print('Not Note or List is selected, use the command: useList or useNote')
            return
        if self.current.type.name == 'Note':
            self.current.text += '\n'+arg
            self.do_refresh(None)
        else:
            print('{} is not a Note'.format(self.current.title))

    def do_checkItem(self, arg):
        """
        KEEP:Mark an item as completed in a current list

        Usage:
            ~> checkItem <item in current list>
        """
        if self.current is None:
            print('Not Note or List is selected, use the command: useList or useNote')
            return
        if self.current.type.name == 'List':
            for item in self.current.items:
                if arg == item.text:
                    item.checked = True
            self.do_refresh(None)
            self.do_useList(self.current.title)
        else:
            print('{} is not a List'.format(self.current.title))

    def complete_checkItem(self, text, line, start_index, end_index):
        if text:
            temp = line[line.startswith('checkItem') and len('checkItem'):].lstrip()
            temp2 = temp.split()[-1]
            return [temp2 + option[option.startswith(temp) and len(temp):]
                    for option in self.current_unchecked if option.startswith(temp)]
        else:
            temp = line[line.startswith('checkItem') and len('checkItem'):].lstrip()
            if temp == '':
                return self.current_unchecked
            else:
                options = [option[len(temp):]
                           for option in self.current_unchecked if option.startswith(temp)]
                return options

    def do_deleteItem(self, arg):
        """
        KEEP:Delete an item from a list (checked or unchecked)

        Usage:
            ~> deleteItem <item in current list>
        """
        if self.current is None:
            print(colored('Not Note or List is selected, use the command: useList or useNote',
                          'red', self.termcolor))
            return
        if self.current.type.name == 'List':
            for item in self.current.items:
                if arg == item.text:
                    question = 'Are you sure you want to delete {} ?. '.format(arg)
                    question += 'This is irreversible [spell out yes]: '
                    question = colored(question, 'red', self.termcolor)
                    if (input(question).lower() in ['yes']):
                        item.delete()
            self.do_refresh(None)
            self.do_useList(self.current.title)
        else:
            print('{} is not a List'.format(self.current.title))

    def complete_deleteItem(self, text, line, start_index, end_index):
        if text:
            temp = line[line.startswith('deleteItem') and len('deleteItem'):].lstrip()
            temp2 = temp.split()[-1]
            return [temp2 + option[option.startswith(temp) and len(temp):]
                    for option in self.current_all_items if option.startswith(temp)]
        else:
            temp = line[line.startswith('deleteItem') and len('deleteItem'):].lstrip()
            if temp == '':
                return self.current_all_items
            else:
                options = [option[len(temp):]
                           for option in self.current_all_items if option.startswith(temp)]
                return options

    def do_uncheckItem(self, arg):
        """
        KEEP:Mark an item as unchecked in a current list

        Usage:
            ~> uncheckItem <item in current list>
        """
        if self.current is None:
            print('Not Note or List is selected, use the command: useList or useNote')
            return
        if self.current.type.name == 'List':
            for item in self.current.items:
                if arg == item.text:
                    item.checked = False
            self.do_refresh(None)
            self.do_useList(self.current.title)
        else:
            print('{} is not a List'.format(self.current.title))

    def complete_uncheckItem(self, text, line, start_index, end_index):
        if text:
            temp = line[line.startswith('uncheckItem') and len('uncheckItem'):].lstrip()
            temp2 = temp.split()[-1]
            return [temp2 + option[option.startswith(temp) and len(temp):]
                    for option in self.current_checked if option.startswith(temp)]
        else:
            temp = line[line.startswith('uncheckItem') and len('uncheckItem'):].lstrip()
            if temp == '':
                return self.current_checked
            else:
                options = [option[len(temp):]
                           for option in self.current_checked if option.startswith(temp)]
                return options

    def do_addItem(self, arg):
        """
        KEEP: Add a new item to current lists

        Usage:
            ~> addItem <item>

        Ex:
            ~> addItem get milk

        Note:
            You can also use the shortcut ai:
            ~> ai <item>
        """
        if self.current is None:
            print('Not Note or List is selected, use the command: useList or useNote')
            return
        if self.current.type.name == 'List':
            self.current.add(arg.lstrip())
            self.do_refresh(None)
            if self.autosync:
                self.do_useList(self.current.title)
        else:
            print('{} is not a List'.format(self.current.title))

    def do_moveItem(self, arg):
        """
        KEEP:Move items from current list to another

        Usage:
            ~> moveItem <item> --list <destination_list>
        """
        destination = None
        done = False
        if self.current is None:
            print('Not Note or List is selected, use the command: useList or useNote')
            return
        move_args = argparse.ArgumentParser(prog='', usage='', add_help=False)
        move_args.add_argument('item', action='store', default=None, nargs='+')
        move_args.add_argument('--list', help='Name of the destination list',
                               action='store', default=None)

        try:
            args = move_args.parse_args(arg.split())
        except:
            self.do_help('moveItem')
            return
        if args.list is None:
            print('You need to specify a list to move the item to with --list option')
            return
        else:
            new_arg = arg[:arg.index('--list')].rstrip()
            for n in self.entries:
                if args.list == n.title:
                    destination = n
            if destination is None:
                print('List {} does not exist'.format(args.list))
                self.do_entries('lists')
                return
        if self.current.type.name == 'List':
            for item in self.current.items:
                if new_arg == item.text:
                    destination.add(item.text)
                    item.delete()
                    done = True
                    break
            if not done:
                print('Item {} does not exist in list {}'.format(new_arg, self.current.title))
                return
            self.do_refresh(None)
            self.do_useList(self.current.title)
        else:
            print('{} is not a List'.format(self.current.title))

    def complete_moveItem(self, text, line, start_index, end_index):
        if text:
            temp = line[line.startswith('moveItem') and len('moveItem'):].lstrip()
            temp2 = temp.split()[-1]
            return [temp2 + option[option.startswith(temp) and len(temp):]
                    for option in self.current_unchecked if option.startswith(temp)]
        else:
            temp = line[line.startswith('moveItem') and len('moveItem'):].lstrip()
            if temp == '':
                return self.current_unchecked
            else:
                options = [option[len(temp):]
                           for option in self.current_unchecked if option.startswith(temp)]
                return options

    def do_dump(self, arg):
        """
        Pickle entries and current status for offline use

        Usage:
            ~> dump
        """
        pickle.dump(self.keep, open(os.path.join(self.kcli_path, self.username+'.kci'), 'wb'))

    def do_load(self, arg):
        """
        Load entries from a previously saved pickle. For offline use

        Usage:
            ~> load
        """
        with open(self.auth_file, 'r') as auth:
            conn = yaml.load(auth)
        self.username = conn['user']
        self.keep = pickle.load(open(os.path.join(self.kcli_path, self.username+'.kci'), 'rb'))
        self.do_refresh(None)

    def do_clear(self, line):
        """
        Clears the screen.

        Usage:
            ~> clean
        """
        sys.stdout.flush()
        if line is None:
            return
        try:
            tmp = os.system('clear')
        except:
            try:
                tmp = os.system('cls')
            except:
                pass


def write_conf(conf_file):
    defaults = {
                'termcolor': True,
                'autosync': True,
                'current': '',
               }
    if not os.path.exists(conf_file):
        with open(conf_file, 'w') as conf:
            yaml.dump(defaults, conf, default_flow_style=False)
    else:
        with open(conf_file, 'r') as conf:
            current = yaml.load(conf)
            for k in defaults.keys():
                if current.get(k) is None:
                    current[k] = defaults[k]
        with open(conf_file, 'w') as conf:
            yaml.dump(current, conf, default_flow_style=False)


def cli():
    """ Main command line interface function"""
    online = True if os.system("ping -c 1 " + 'google.com' + '> /dev/null 2>&1') is 0 else False
    if not online:
        print('You are offline, use the --offline option (and load your previously dumped data)')
        return
    kcli_path = os.path.join(os.environ["HOME"], ".keepcli/")
    if not os.path.exists(kcli_path):
        os.makedirs(kcli_path)
    try:
        auth_file = os.environ["KEEPCLI_AUTH"]
    except KeyError:
        auth_file = os.path.join(kcli_path, "auth.yaml")
    conf_file = os.path.join(kcli_path, "config.yaml")
    write_conf(conf_file)
    args = kcliparser.get_args()
    offline = True if args.offline else False
    print('\nWelcome to keepcli, use help or ? to list possible commands.\n\n')
    GKeep(auth_file=auth_file, conf_file=conf_file, offline=offline).cmdloop()


if __name__ == '__main__':
    cli()
