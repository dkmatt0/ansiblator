#!/usr/bin/env python3

import cmd
import json
import logging
import os
import readline
import sh
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
    """Renvoi dans un dictionnaire l'ensemble des serveurs présent dans le fichier 'inventory_path' ainsi que les variable
    et groupe dont chaque serveur fait parti.

    Arguments :
    inventory_path -- fichier d'inventaire ansible à analyser
    """
    ansible_inventory = sh.Command("ansible-inventory")
    json_inventory = json.loads(ansible_inventory("-i", inventory_path, "--list").stdout)

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
        for group in json_inventory[name]["children"]:
          if group in groups:
            groups[group].append(name)
          else:
            groups[group] = [name]
      elif "hostvars" in json_inventory[name]:
        hostvars = json_inventory[name]["hostvars"]
    groups = {k: self.search_all(v, groups, set([k])) for (k, v) in groups.items()}
    servers = {}
    for host in hosts:
      servers[host] = {"vars": hostvars.get(host, set()), "groups": groups.get(host, set())}
    return servers

  def list_inventory(self):
    inventory_file = {}
    for f in os.listdir("inventory"):
      f_fullpath = os.sep.join(("inventory", f))
      if os.path.isfile(f_fullpath) and os.access(f_fullpath, os.R_OK):
        parsed_inventory_file = self.parse_inventory_file(f_fullpath)

        if len(parsed_inventory_file) > 0:
          inventory_file[f] = parsed_inventory_file
    return inventory_file

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
      if not self.config["inventory"]:
        print("Vous devez d'abord sélectionner un fichier d'inventaire avec la commande 'inventory'.")
      else:
        func(self, *args, **kwargs)

    return wrapper

  def need_server(func):
    """Décorateur permettant de vérifier si au moins un serveur à été choisi avant lancement de la commande"""
    @wraps(func)
    def wrapper(self, *args, **kwargs):
      if not self.config["servers"]:
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
    Usage : add <serveur>
    Alias : a"""
    pass

  @need_server
  def do_deploy(self, arg):
    """Déploie sur le ou les serveurs selectionnés
    Usage : deploy
    Alias : go"""
    pass

  @need_inventory
  def do_eadd(self, arg):
    """Ajoute un ou plusieurs serveurs à la selection selon une regex
    Usage : eadd <regex serveur>
    Alias : e"""
    pass

  @need_inventory
  def do_egadd(self, arg):
    """Ajoute les serveurs d'un groupe à la selection selon une regex
    Usage : egadd <regex groupe>
    Alias : ge"""
    pass

  @need_server
  def do_egrm(self, arg):
    """Supprime les serveurs d'un groupe de la selection selon une regex
    Usage : egrm <regex groupe>
    Alias : egr"""
    pass

  @need_server
  def do_erm(self, arg):
    """Supprime un ou plusieurs serveurs de la selection selon une regex
    Usage : erm <regex serveur>
    Alias : er"""
    pass

  @need_inventory
  def do_gadd(self, arg):
    """Ajoute les serveurs d'un groupe à la selection
    Usage : gadd <groupe>
    Alias : g"""
    pass

  @need_server
  def do_grm(self, arg):
    """Supprime les serveurs d'un groupe de la selection
    Usage : grm <groupe>
    Alias : gr"""
    pass

  def do_help(self, arg):
    """Affiche l'aide
    Usage : help [commande]
    Alias : ?"""
    if arg != "":
      args = arg.split()
      if arg and args[0] in self.aliases:
        arg = self.aliases[args[0]].__name__[3:]
      super().do_help(arg)
    else:
      print(self.all_help)

  def do_inventory(self, arg):
    """Affiche tout ou sélectionne l'un des fichiers d'inventaire disponible
    Usage : inventory [<nom de fichier d'inventaire>]
    Alias : inv, i"""
    if not hasattr(self, "inventory") or (hasattr(self, "inventory") and not arg):
      self.inventory = self.list_inventory()
    if arg in self.inventory:
      self.do_reset()
      self.config["inventory"] = self.inventory[arg]
    elif not arg or arg not in self.inventory:
      for inventory in self.inventory:
        print(inventory)
    else:
      self.do_help("inventory")

  @need_inventory
  def do_list(self, arg):
    """Liste les serveurs, groupes et variables
    Usage : list
    Alias : l"""
    print("list")

  def do_quit(self, arg):
    """Quitte le shell (et le programme)
    Usage : quit
    Alias : exit, q"""
    return True

  def do_reset(self, arg=None):
    """Réinitialise la sélection de serveurs, groupes et tags
    Usage : reset"""
    self.config = {"inventory": {}, "servers": [], "groups": [], "tags": []}

  @need_server
  def do_rm(self, arg):
    """Supprime un serveur de la selection
    Usage : rm <serveur>
    Alias : r"""
    pass

  @need_inventory
  def do_show(self, arg):
    """Affiche les informations lié au déploiement en cours
    Usage : show
    Alias : s"""
    pass

  @need_inventory
  def do_skiptag(self, arg):
    """Ignore un ou plusieurs tags lors du lancement du playbook
    Usage : skiptag <tag> [<tag>...]
    Alias : st"""
    pass

  @need_inventory
  def do_tag(self, arg):
    """Applique un ou plusieurs tags lors du lancement du playbook
    Usage : tag <tag> [<tag>...]
    Alias : t"""
    pass

  @need_inventory
  def do_tags(self, arg):
    """Affiche la liste des tags disponible
    Usage : tags
    Alias : lt"""
    pass


# Appel la classe qui lance le shell interactif (et donc le programme)
Ansiblator().cmdloop()
