import cmd
import sys
import os
import gkeepapi
from termcolor import colored
import yaml
from keepcli.version import __version__

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
options_current = ['show', 'color']


def print_list(List):
    times_unchecked = [item.timestamps.created for item in List.unchecked]
    unchecked = [x for _, x in sorted(zip(times_unchecked, List.unchecked), key=lambda pair: pair[0])]
    times_checked = [item.timestamps.created for item in List.checked]
    checked = [x for _, x in sorted(zip(times_checked, List.checked), key=lambda pair: pair[0])]
    for i in unchecked:
        print(colored(i, "red"))
    for i in checked:
        print(colored(i, "green"))


def get_color(entry):
    try:
        return colored(entry.title, colors[entry.color.name.lower()])
    except KeyError:
        return colored(entry.title, "white")




class GKeep(cmd.Cmd):

    def __init__(self, auth_file):
        super().__init__()
        print('Logging in...')
        self.prompt = 'GK ~> '
        self.keep = gkeepapi.Keep()
        with open(auth_file, 'r') as auth:
            conn = yaml.load(auth)
        self.connect = self.keep.login(conn['user'], conn['passwd'])
        self.current = None
        self.do_refresh(None)
        self.complete_ul = self.complete_useList

    def emptyline(self):
        pass


    def do_version(self, arg):
        print('Current version: {}'.format(__version__))

    def do_shortcuts(self, arg):
        """
        ul: useList --> select a list
        ai: addItem --> add item to a current List
        cs: current show --> shows current List/Note
        """
        self.do_help('shortcuts')


    def do_refresh(self, arg):
        """Sync and Refresh content"""
        print('Syncing...')
        self.keep.sync()
        self.entries = self.keep.all()
        self.titles = []
        self.lists = []
        self.notes = []
        for n in self.entries:
            if not n.trashed:
                self.titles.append(n.title)
                if n.type.name == 'List':
                    self.lists.append(n.title)
                if n.type.name == 'Note':
                    self.notes.append(n.title)


    def do_cs(self, arg):
        self.do_current('show')

    def do_ai(self, arg):
        self.do_addItem(arg)

    def do_ul(self, arg):
        self.do_useList(arg)

    def do_exit(self, arg):
        """Exit the program"""
        return True

    def do_connect(self, arg):
        """ I'm connected ? """
        print(colored(self.connect, "green"))

    def do_entries(self, arg):
        """ Show  """

        line = "".join(arg.split())
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
        for n in self.entries:
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
                data = {'title': colored(n.title, colors[n.color.name.lower()]), 'status': status,
                        'type': n.type.name}
            except KeyError:
                data = {'title': colored(n.title, 'white'), 'status': status,
                        'type': n.type.name}
            if display:
                print('{title: <30} {status: <10}  [ {type} ]'.format(**data))
        print()

    def complete_entries(self, text, line, start_index, end_index):
        if text:
            return [option for option in options_entries if option.startswith(text)]
        else:
            return options_entries

    def do_show(self, arg):
        """ Print content os List/Note """
        if arg == '':
            self.do_help('show')
            return
        for n in self.entries:
            if arg == n.title:
                print()
                try:
                    title = colored('============{:=<30}'.format(' '+n.title+' '), colors[n.color.name.lower()])
                except:
                    title = colored('============{:=<30}'.format(' '+n.title+' '), "white")
                print(title)
                print()
                print(n.text) if n.type.name == 'Note' else print_list(n)
                try:
                    bottom = colored('============{:=<30}'.format(''), colors[n.color.name.lower()])
                except:
                    bottom = colored('============{:=<30}'.format(''), "white")
                print(bottom)

                print()

    def complete_show(self, text, line, start_index, end_index):
        if text:
            return [option for option in self.titles if option.startswith(text)]
        else:
            return self.titles

    def do_delete(self, arg):
        for n in self.entries:
            if arg == n.title:
                print()
                #TODO: ask before deletion
                print('{} Deleted'.format(n.title))
                n.delete()
                self.do_refresh(None)

    def complete_delete(self, text, line, start_index, end_index):
        if text:
            return [option for option in self.titles if option.startswith(text)]
        else:
            return self.titles



    def do_current(self, arg):
        if self.current is None:
            print('Not Note or List is selected, use the command: useList or useNote')
            return
        print('Current entry: {}'.format(get_color(self.current)))
        if 'show' in arg:
            self.do_show(self.current.title)
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
        for n in self.entries:
            if arg == n.title:
                print()
                #TODO: ask before deletion
                print('Current List set to: {}'.format(n.title))
                self.current = n
                self.current_checked = [i.text for i in n.checked]
                self.current_unchecked = [i.text for i in n.unchecked]

    def complete_useList(self, text, line, start_index, end_index):
        if text:
            return [option for option in self.lists if option.startswith(text)]
        else:
            return self.lists

    def do_useNote(self, arg):
        for n in self.entries:
            if arg == n.title:
                print()
                print('Current Note set to: {}'.format(n.title))
                self.current = n

    def complete_useNote(self, text, line, start_index, end_index):
        if text:
            return [option for option in self.notes if option.startswith(text)]
        else:
            return self.notes

    def do_addText(self, arg):
        if self.current is None:
            print('Not Note or List is selected, use the command: useList or useNote')
            return
        if self.current.type.name == 'Note':
            self.current.text += '\n'+arg
            self.do_refresh(None)
        else:
            print('{} is not a Note'.format(self.current.title))


    def do_checkItem(self, arg):
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


    def do_uncheckItem(self, arg):
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
            return [option for option in self.current_checked if option.startswith(text)]
        else:
            return self.current_checked

    def do_addItem(self, arg):
        if self.current is None:
            print('Not Note or List is selected, use the command: useList or useNote')
            return
        if self.current.type.name == 'List':
            self.current.add(arg.lstrip())
            self.do_refresh(None)
            self.do_useList(self.current.title)
        else:
            print('{} is not a List'.format(self.current.title))


    def do_clear(self, line):
        """
        Clear screen. There is a shortcut by typing . on the interpreter
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

def cli():
    print('Starting...')
    kcli_path = os.path.join(os.environ["HOME"], ".keepcli/")
    if not os.path.exists(kcli_path):
        os.makedirs(kcli_path)
    auth_file = os.path.join(kcli_path, "auth.yaml")
    conf_file = os.path.join(kcli_path, "config.yaml")
    GKeep(auth_file=auth_file).cmdloop()

if __name__ == '__main__':
    cli()
