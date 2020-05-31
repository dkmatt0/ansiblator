#!/usr/bin/env python3

import cmd
import json
import logging
import os
import re
import readline
import shutil
import subprocess
import sys
import textwrap
from functools import wraps


# Activation de système de log
logging.basicConfig(
  filename=None, format="[%(asctime)s] %(levelname)s: %(message)s", datefmt="%Y-%m-%d %H:%M:%S", level=logging.DEBUG
)


def yml_or_yaml(filename):
  """Test si un fichier porte l'extension .yml ou .yaml et renvoi son nom complet.
  Renvoi None si le fichier n'est pas trouvé.

  Arguments :
  filename -- le nom d'un fichier sans l'extension
  """
  if os.path.isfile(filename + ".yml"):
    return filename + ".yml"
  if os.path.isfile(filename + ".yaml"):
    return filename + ".yaml"
  return None


def sortedn(l):
  """Trie une liste de chaîne de caractères en tenant compte des nombre

  Exemple :
    sorted(["a34", "a3", "a52", "a6", "a5"])  => ['a3', 'a34', 'a5', 'a52', 'a6']
    sortedn(["a34", "a3", "a52", "a6", "a5"]) => ['a3', 'a5', 'a6', 'a34', 'a52']

  Arguments :
  l -- Liste à trier
  """
  l = list(l)
  for i, x in enumerate(l):
    z = []
    for y in re.split("(\d+)", x):
      if re.match("^(\d+)$", y):
        y = int(y)
      z.append(y)
    l[i] = z
  l.sort()
  for i, x in enumerate(l):
    l[i] = "".join([str(y) for y in x])
  return l


# Test si ansible est installé
if not shutil.which("ansible-playbook"):
  logging.critical("'ansible-playbook' est absent. Vous devez d'abord installer ansible.")
  exit(1)
elif not shutil.which("ansible-inventory"):
  logging.critical("'ansible-inventory' est absent. Vous devez d'abord installer ansible.")
  exit(1)

# Test de tous les prérequis :
# - le fichier main.yaml existe et est accessible en lecture
# - le dossier inventory existe et n'est pas vide
playbook_file = yml_or_yaml("main")
if not playbook_file:
  logging.critical("Aucun fichier main.yml ou main.yaml n'a été trouvé.")
  exit(1)
elif not os.access(playbook_file, os.R_OK):
  logging.critical("Le fichier {} ne peut pas être lu.".format(playbook_file))
  exit(1)
elif not (
  os.path.isdir("inventory")
  and os.access("inventory", os.R_OK)
  and os.access("inventory", os.X_OK)
  and len(os.listdir("inventory")) >= 1
):
  logging.critical("Le dossier inventory n'existe pas.")
  exit(1)

# Chargement des rôles et collections avec le fichier setup_env.sh s'il existe
# Sinon, chargement des rôles et collections à partir du requirements.yaml
run_setup_env_nok = 1
run_requirements_nok = 1

if os.path.isfile("setup_env.sh") and os.access("setup_env.sh", os.R_OK):
  logging.debug("Lancement de setup_env.sh.")
  run_setup_env_nok = subprocess.run(["sh", "setup_env.sh"]).returncode
  logging.debug("setup_env.sh a été lancé et la valeur de sortie obtenu est {}".format(run_setup_env_nok))
else:
  logging.debug("Le fichier setup_env.sh n'existe pas ou n'est pas lisible.")

if run_setup_env_nok:
  if not shutil.which("ansible-galaxy"):
    logging.critical("ansible-galaxy ne semble pas présent")
    exit(1)
  requirements_file = yml_or_yaml("requirements")
  if requirements_file and os.access(requirements_file, os.R_OK):
    requirements_cmd = ["ansible-galaxy", "install", "-p", "./roles", "-r", requirements_file, "-f"]
    logging.debug(
      "Lancement du chargement des roles et collections avec la commande {}".format(" ".join(requirements_cmd))
      )
    run_requirements_nok = subprocess.run(requirements_cmd).returncode
    logging.debug("ansible-galaxy a été lancé et la valeur de sortie obtenu est {}".format(run_requirements_nok))
    if run_requirements_nok:
      logging.critical("Le chargement des rôles et collections depuis le fichier requirements a rencontré une erreur.")
      exit(1)
  else:
    logging.warning("Le fichier requirements.yaml (ou .yml) n'existe pas ou n'est pas lisible.")

# Définition de la classe servant au shell interactif
class Ansiblator(cmd.Cmd):
  """Défini les commandes et options du shell interactif"""

  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.intro = "\nBienvenue sur ansiblator !\n"
    self.prompt = "# "
    list_do_docstring = self.parse_do_docstring()
    self.aliases = self.create_alias_from_docstring(list_do_docstring)
    self.all_help = self.generate_help_all_cmd(list_do_docstring)
    self.do_reset()
    self.do_reload()

  def parse_do_docstring(self):
    """Renvoi un tableau à partir des docstring des fonctions"""
    list_do_func = [a[3:] for a in self.get_names() if a.startswith("do_")]
    list_do_docstring = []
    for do_func in sorted(list_do_func):
      if not getattr(self, "do_" + do_func).__doc__:
        continue
      lines = getattr(self, "do_" + do_func).__doc__.splitlines()
      description = lines[0].strip()
      usage = ""
      alias = ""
      for l in lines:
        if l.lstrip()[:5].lower() == "usage":
          usage = "".join(l.split(":")[1:]).strip()
        elif l.lstrip()[:5].lower() == "alias":
          alias = [x.strip() for x in "".join(l.split(":")[1:]).split(",")]
      list_do_docstring.append({"cmd": do_func, "description": description, "usage": usage, "alias": alias})
    return list_do_docstring

  def create_alias_from_docstring(self, parsed_docstring):
    """Crée les alias des commandes à partir des docstring des fonctions"""
    aliases = {}
    for doc in parsed_docstring:
      if len(doc["alias"]) > 0:
        for a in doc["alias"]:
          aliases.update({a: getattr(self, "do_" + doc["cmd"])})
    return aliases

  def generate_help_all_cmd(self, parsed_docstring):
    """Renvoi le texte utilisé par l'aide pour toutes les commandes"""
    max_n_chars = 0
    printed_help = []
    output = ""
    for do_docstring in parsed_docstring:
      usage_without_cmd = " ".join(do_docstring["usage"].split(" ")[1:])
      left = do_docstring["cmd"]
      left += ", " + ", ".join(do_docstring["alias"]) if len(do_docstring["alias"]) > 0 else ""
      left += " " + usage_without_cmd if usage_without_cmd else ""

      n_chars = len(left)
      if n_chars > max_n_chars:
        max_n_chars = n_chars

      printed_help.append((left, do_docstring["description"], n_chars))

    for h in printed_help:
      output += h[0]
      output += (max_n_chars - h[2] + 2) * " "
      output += h[1]
      output += "\n"

    return output

  def search_all(self, items, list_all_items, data=None):
    """Renvoi récursivement pour chaque éléments de la liste 'items' présent dans 'list_all_items', les valeurs
    correspondante à 'items'.

    Arguments :
    items -- liste des élements à chercher dans 'list_all_items'.
    list_all_items -- dictionnaire dont la valeur est un set contenant les dépendances de la clé.
    data -- set contenant permettant le passage de la liste des dépendances durant la récursivité.
    """
    if data is None:
      data = set()
    if not isinstance(items, list):
      items = list(items)
    for item in items:
      data.add(item)
      if item in list_all_items:
        data.update(self.search_all(list_all_items[item], list_all_items, data))
    return data

  def parse_inventory_file(self, inventory_path):
    """Renvoi dans un dictionnaire l'ensemble des serveurs présent dans le fichier 'inventory_path' avec les variables et
    groupes dont chaque serveur fait parti ainsi que l'ensembles des groupes disponibles avec les groupes dont ils dépendent.

    Arguments :
    inventory_path -- fichier d'inventaire ansible à analyser
    """
    json_inventory = json.loads(
      subprocess.run(
        ("ansible-inventory", "-i", inventory_path, "--list"),
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        universal_newlines=True,
      ).stdout
    )
    hosts = {}
    groups = {}
    hostvars = {}
    for name in json_inventory:
      if "hosts" in json_inventory[name]:
        for host in json_inventory[name]["hosts"]:
          if host in hosts:
            hosts[host].append(name)
          else:
            hosts[host] = [name]
      elif "children" in json_inventory[name]:
        if name not in groups:
          groups[name] = []
        for group in json_inventory[name]["children"]:
          if group in groups:
            groups[group].append(name)
          else:
            groups[group] = [name]
      elif "hostvars" in json_inventory[name]:
        hostvars = json_inventory[name]["hostvars"]
    groups_all = {k: self.search_all(v, groups, set([k])) for (k, v) in groups.items()}
    servers = {}
    for host in hosts:
      hostgroups = set()
      for hostgroup in hosts[host]:
        hostgroups.update(groups_all.get(hostgroup, set()))
      servers[host] = {"vars": hostvars.get(host, set()), "groups": hostgroups}
    return (servers, groups)

  # def list_inventory(self):
  #   """Liste les différents fichiers d'inventaire et leurs contenu."""
  #   files, servers, groups = [], {}, {}
  #   for f in os.listdir("inventory"):
  #     f_fullpath = os.sep.join(("inventory", f))
  #     if os.path.isfile(f_fullpath) and os.access(f_fullpath, os.R_OK):
  #       server, group = self.parse_inventory_file(f_fullpath)
  #       if len(server) > 0:
  #         tags = set()
  #         ansible_playbook = sh.Command("ansible-playbook")
  #         playbook_main = yml_or_yaml("main")
  #         tags_text = str(ansible_playbook("-i", f_fullpath, "--list-tags", playbook_main))
  #         for regex_tags in re.finditer("TASK TAGS: \[([\w\-, ]+)\]", tags_text):
  #           tags.update(regex_tags.group(1).split(", "))
  #         tags = sorted([[int(y) if re.match("^(\d+)$", y) else y for y in re.split("(\d+)", x)] for x in tags])
  #         tags = ["".join([str(y) for y in x]) for x in tags]
  #         servers[f], groups[f] = server, group
  #         files.append(f)
  #   return files, servers[f], groups[f]

  def emptyline(self):
    """Action à lancer lors de la validation d'une ligne vide"""
    pass

  def default(self, line):
    """Action à lancer lorsque la commande lancé est inconnu"""
    cmd, arg, line = self.parseline(line)
    if cmd in self.aliases:
      self.aliases[cmd](arg)
    elif cmd == "EOF":
      return True
    else:
      print('Commande "{}" inconnu.'.format(line))
      print('Utilisez la commande "help" pour obtenir la liste des commandes disponibles.')

  ## Définition des décorateurs pour les commandes
  def need_inventory(func):
    """Décorateur permettant de vérifier si un fichier d'inventaire à été choisi avant lancement de la commande"""

    @wraps(func)
    def wrapper(self, *args, **kwargs):
      if not self.selected["file"] or self.selected["file"] not in self.available["files"]:
        print("Vous devez d'abord sélectionner un fichier d'inventaire avec la commande 'inventory'.")
      else:
        func(self, *args, **kwargs)

    return wrapper

  def need_server(func):
    """Décorateur permettant de vérifier si au moins un serveur à été choisi avant lancement de la commande"""

    @wraps(func)
    def wrapper(self, *args, **kwargs):
      if not self.selected["servers"] and not self.selected["groups"]:
        print("Aucun serveurs ou groupes de serveurs n'est sélectionné.")
        print(
          "Utilisez la commande 'help' voir la liste des commandes permettant l'ajout de serveurs ou de groupes de serveurs."
        )
      else:
        func(self, *args, **kwargs)

    return wrapper

  ## Définition des commandes du shell interactif (par ordre alphabétique)
  @need_inventory
  def do_add(self, arg):
    """Ajoute un serveur à la selection
    Usage : add <serveur> [<serveur>...]
    Alias : a"""
    args = sorted(arg.split(" "))
    for a in args:
      if a in self.available["servers"][self.selected["file"]]:
        self.selected["servers"].add(a)
        print("{} ajouté.".format(a))
      else:
        print("{} n'a pas été trouvé.".format(a))

  @need_server
  def do_deploy(self, arg):
    """Déploie sur le ou les serveurs selectionnés
    Usage : deploy
    Alias : go"""
    self.do_show()

    cmd = "ansible-playbook --inventory " + self.available["files"][self.selected["file"]]
    if self.selected["servers"] or self.selected["groups"]:
      cmd += " --limit {}".format(",".join(self.selected["servers"] | self.selected["groups"]))
    if self.selected["tags"]:
      cmd += " --tags {}".format(",".join(self.selected["tags"]))
    if self.selected["skiptags"]:
      cmd += " --skip-tags {}".format(",".join(self.selected["skiptags"]))
    playbook_file = yml_or_yaml("main")
    cmd += " " + playbook_file
    print("Commande : " + cmd)
    print()
    user_answer = input("Êtes-vous sûr ? (oui/NON) : ").strip().lower()
    if (len(user_answer)==3 and user_answer in('yes', 'oui')) or (len(user_answer)==1 and user_answer in('y', 'o')):
      subprocess.run(cmd.split(" "))
    else:
      print("Déploiement annulé !")

  @need_inventory
  def do_eadd(self, arg):
    """Ajoute un ou plusieurs serveurs à la selection selon une regex
    Usage : eadd <regex serveur>
    Alias : e"""
    args = sorted(arg.split(" "))
    no_action = True
    for a in args:
      for server in self.available["servers"][self.selected["file"]]:
        if re.search(a, server):
          self.selected["servers"].add(server)
          print("{} ajouté.".format(server))
          no_action = False
    if no_action:
      print("Aucun serveur n'a pas été ajouté.")

  @need_inventory
  def do_egadd(self, arg):
    """Ajoute les serveurs d'un groupe à la selection selon une regex
    Usage : egadd <regex groupe>
    Alias : eg"""
    args = sorted(arg.split(" "))
    no_action = True
    for a in args:
      for group in self.available["groups"][self.selected["file"]]:
        if re.search(a, group):
          self.selected["groups"].add(group)
          print("{} ajouté.".format(group))
          no_action = False
    if no_action:
      print("Aucun groupe n'a pas été ajouté.")

  @need_server
  def do_egremove(self, arg):
    """Supprime les serveurs d'un groupe de la selection selon une regex
    Usage : egremove <regex groupe>
    Alias : egrm, egr"""
    args = sorted(arg.split(" "))
    no_action = True
    for a in args:
      for group in self.available["groups"][self.selected["file"]]:
        if re.search(a, group):
          self.selected["groups"].remove(group)
          print("{} supprimé.".format(group))
          no_action = False
    if no_action:
      print("Aucun groupe n'a pas été supprimé.")

  @need_server
  def do_eremove(self, arg):
    """Supprime un ou plusieurs serveurs de la selection selon une regex
    Usage : eremove <regex serveur>
    Alias : erm, er"""
    args = sorted(arg.split(" "))
    no_action = True
    for a in args:
      for server in self.available["servers"][self.selected["file"]]:
        if re.search(a, server):
          self.selected["servers"].remove(server)
          print("{} supprimé.".format(server))
          no_action = False
    if no_action:
      print("Aucun serveur n'a pas été supprimé.")

  @need_inventory
  def do_gadd(self, arg):
    """Ajoute les serveurs d'un groupe à la selection
    Usage : gadd <groupe>
    Alias : g"""
    args = sorted(arg.split(" "))
    for a in args:
      if a in self.available["groups"][self.selected["file"]]:
        print(self.selected["groups"])
        self.selected["groups"].add(a)
        print("{} ajouté.".format(a))
      else:
        print("{} n'a pas été trouvé.".format(a))

  @need_server
  def do_gremove(self, arg):
    """Supprime les serveurs d'un groupe de la selection
    Usage : gremove <groupe>
    Alias : grm, gr"""
    args = sorted(arg.split(" "))
    for a in args:
      if a in self.selected["groups"]:
        self.selected["groups"].remove(a)
        print("{} supprimé.".format(a))
      else:
        print("{} n'a pas été trouvé.".format(a))

  def do_help(self, arg):
    """Affiche l'aide
    Usage : help [commande]
    Alias : ?"""
    if arg:
      args = arg.split()
      if arg and args[0] in self.aliases:
        arg = self.aliases[args[0]].__name__[3:]
      super().do_help(arg)
    else:
      print(self.all_help)

  def do_inventory(self, arg=""):
    """Affiche tout ou sélectionne l'un des fichiers d'inventaire disponible
    Usage : inventory [<nom de fichier d'inventaire>]
    Alias : inv, i"""
    if arg in self.available["files"]:
      # self.do_reset()
      self.selected["file"] = arg
    elif not arg:
      for inventory in sorted(self.available["files"]):
        print(inventory)
    else:
      print("'{}' n'a pas été trouvé. Voici les choix valides possibles :".format(arg))
      self.do_inventory()

  @need_inventory
  def do_list(self, arg):
    """Liste les serveurs, groupes et variables
    Usage : list
    Alias : l"""
    for host in self.available["servers"][self.selected["file"]]:
      if "env" in self.available["servers"][self.selected["file"]][host]["vars"]:
        env = self.available["servers"][self.selected["file"]][host]["vars"]["env"]
      else:
        env = ""
      groups = ", ".join(sorted(self.available["servers"][self.selected["file"]][host]["groups"]))
      print(host, "|", env, "|", groups)

  def do_quit(self, arg):
    """Quitte le shell (et le programme)
    Usage : quit
    Alias : exit, q"""
    return True

  def do_reload(self, arg=""):
    """Charge ou recharge les serveurs, groupes et tags disponibles
    Usage : reload
    """
    self.available = {"files": {}, "servers": {}, "groups": {}, "tags": {}}

    for f in os.listdir("inventory"):
      f_fullpath = os.sep.join(("inventory", f))
      if os.path.isfile(f_fullpath) and os.access(f_fullpath, os.R_OK):
        servers, groups = self.parse_inventory_file(f_fullpath)
        if len(servers) > 0:
          tags = set()
          playbook_main = yml_or_yaml("main")
          tags_text = subprocess.run(
            ("ansible-playbook", "-i", f_fullpath, "--list-tags", playbook_main),
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            universal_newlines=True,
          ).stdout
          for regex_tags in re.finditer("TASK TAGS: \[([\w\-, ]+)\]", tags_text):
            tags.update(regex_tags.group(1).split(", "))
          self.available["files"][f] = f_fullpath
          self.available["servers"][f] = servers
          self.available["groups"][f] = groups
          self.available["tags"][f] = tags

  @need_server
  def do_remove(self, arg):
    """Supprime un serveur de la selection
    Usage : remove <serveur>
    Alias : rm, r"""
    args = sorted(arg.split(" "))
    for a in args:
      if a in self.selected["servers"]:
        self.selected["servers"].remove(a)
        print("{} supprimé.".format(a))
      else:
        print("{} n'a pas été trouvé.".format(a))

  def do_reset(self, arg=None):
    """Réinitialise la sélection de serveurs, groupes et tags
    Usage : reset"""
    self.selected = {"file": "", "servers": set(), "groups": set(), "tags": set(), "skiptags": set()}

  @need_inventory
  def do_show(self, arg=""):
    """Affiche les informations lié au déploiement en cours
    Usage : show
    Alias : s"""
    servers_from_groups = {}
    for group in self.selected["groups"]:
      for host in self.available["servers"][self.selected["file"]]:
        if group in self.available["servers"][self.selected["file"]][host]["groups"]:
          if host in servers_from_groups:
            servers_from_groups[host].append(group)
          else:
            servers_from_groups[host] = [group]
    n_servers = len(self.selected["servers"])
    n_servers_from_groups = len(servers_from_groups)
    n_tags = len(self.selected["tags"])
    n_skiptags = len(self.selected["skiptags"])
    print("Serveurs : ", end="")
    if n_servers > 0:
      print("")
      for s in sortedn(self.selected["servers"]):
        if s not in servers_from_groups:
          print("  {}".format(s))
    else:
      print("❌")
    print("Serveurs depuis groupes : ", end="")
    if n_servers_from_groups > 0:
      print("")
      for s in servers_from_groups:
        print("  {} (depuis {})".format(s, ", ".join(sortedn(servers_from_groups[s]))))
    else:
      print("❌")
    print("Tags : ", end="")
    if n_tags > 0:
      print(", ".join(sortedn(self.selected["tags"])))
    else:
      print("❌")
    print("Skiptags : ", end="")
    if n_skiptags > 0:
      print(", ".join(sortedn(self.selected["skiptags"])))
    else:
      print("❌")

  @need_inventory
  def do_skiptag(self, arg):
    """Ignore un ou plusieurs tags lors du lancement du playbook
    Usage : skiptags [<tag> [<tag>...]]
    Alias : skiptag, st"""
    if not arg:
      for tag in sortedn(self.available["tags"][self.selected["file"]]):
        if tag in self.selected["skiptags"]:
          print(f"{tag} *")
        else:
          print(f"{tag}")
    else:
      args = sortedn(arg.split(" "))
      for a in args:
        if a in self.available["tags"][self.selected["file"]]:
          if a in self.selected["tags"]:
            self.selected["tags"].remove(a)
          self.selected["skiptags"].add(a)
          print("{} ajouté.".format(a))
        else:
          print("{} n'a pas été trouvé.".format(a))

  @need_inventory
  def do_tags(self, arg):
    """Affiche la liste des tags ou applique un ou plusieurs tags lors du lancement du playbook
    Usage : tags [<tag> [<tag>...]]
    Alias : tag, t"""
    if not arg:
      for tag in sortedn(self.available["tags"][self.selected["file"]]):
        if tag in self.selected["tags"]:
          print(f"{tag} *")
        else:
          print(f"{tag}")
    else:
      args = sortedn(arg.split(" "))
      for a in args:
        if a in self.available["tags"][self.selected["file"]]:
          if a in self.selected["skiptags"]:
            self.selected["skiptags"].remove(a)
          self.selected["tags"].add(a)
          print("{} ajouté.".format(a))
        else:
          print("{} n'a pas été trouvé.".format(a))

  def do_debug(self, arg):
    arg = arg.strip()
    if arg and hasattr(self, arg):
      print(getattr(self, arg))
    else:
      print("error!")


# Appel la classe qui lance le shell interactif (et donc le programme)
Ansiblator().cmdloop()
