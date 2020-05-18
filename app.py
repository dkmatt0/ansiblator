#!/usr/bin/env python3

import cmd
import logging
import os
import readline
import shutil
import sys
import subprocess
import sys
import textwrap


# Activation de système de log
logging.basicConfig(
  filename=None,
  format='[%(asctime)s] %(levelname)s: %(message)s',
  datefmt='%Y-%m-%d %H:%M:%S',
  level=logging.DEBUG
)

def yml_or_yaml(filename):
  '''Test si un fichier porte l'extension .yml ou .yaml et renvoi son nom complet.
  Renvoi None si le fichier n'est pas trouvé.

  Arguments :
  filename -- le nom d'un fichier sans l'extension
  '''
  if os.path.isfile(filename+'.yml'): return filename+'.yml'
  if os.path.isfile(filename+'.yaml'): return filename+'.yaml'
  return None

# Test si ansible est installé
if not shutil.which('ansible-playbook'):
  logging.critical("Vous devez d'abord installer ansible.")
  exit(1)

# Test de tous les prérequis :
# - le fichier main.yaml existe et est accessible en lecture
# - le dossier inventory existe et n'est pas vide
playbook_file = yml_or_yaml('main')
if not playbook_file:
  logging.critical("Aucun fichier main.yml ou main.yaml n'a été trouvé.")
  exit(1)
elif not os.access(playbook_file, os.R_OK):
  logging.critical("Le fichier {} ne peut pas être lu.".format(playbook_file))
  exit(1)
elif not (os.path.isdir('inventory') and os.access('inventory', os.R_OK) and os.access('inventory', os.X_OK) and len(os.listdir('inventory'))>=1):
  logging.critical("Le dossier inventory n'existe pas.")
  exit(1)

# Chargement des rôles et collections avec le fichier setup_env.sh s'il existe
# Sinon, chargement des rôles et collections à partir du requirements.yaml
run_setup_env_nok = 1
run_requirements_nok = 1

if os.path.isfile('setup_env.sh') and os.access('setup_env.sh', os.R_OK):
  logging.debug("Lancement de setup_env.sh.")
  run_setup_env_nok = subprocess.run(['sh', 'setup_env.sh']).returncode
  logging.debug("setup_env.sh a été lancé et la valeur de sortie obtenu est {}".format(run_setup_env_nok))
else:
  logging.debug("Le fichier setup_env.sh n'existe pas ou n'est pas lisible.")

if run_setup_env_nok:
  if not shutil.which('ansible-galaxy'):
    logging.critical('ansible-galaxy ne semble pas présent')
    exit(1)
  requirements_file = yml_or_yaml('requirements')
  if requirements_file and os.access(requirements_file, os.R_OK):
    requirements_cmd = ['ansible-galaxy', 'install', '-p', './roles', '-r', requirements_file, '-f']
    logging.debug("Lancement du chargement des roles et collections avec la commande {}".format(' '.join(requirements_cmd)))
    run_requirements_nok = subprocess.run(requirements_cmd).returncode
    logging.debug("ansible-galaxy a été lancé et la valeur de sortie obtenu est {}".format(run_requirements_nok))
    if run_requirements_nok:
      logging.critical("Le chargement des rôles et collections depuis le fichier requirements a rencontré une erreur.")
      exit(1)
  else:
    logging.warning("Le fichier requirements.yaml (ou .yml) n'existe pas ou n'est pas lisible.")

# Définition de la classe servant au shell interactif
class Ansiblator(cmd.Cmd):
  '''Défini les commandes et options du shell interactif'''
  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.intro = "\nBienvenue sur ansiblator !\n"
    self.prompt = "# "
    self.aliases = {
      'l'   : self.do_list,
      'a'   : self.do_add,
      'e'   : self.do_eadd,
      'g'   : self.do_gadd,
      'ge'  : self.do_geadd,
      'r'   : self.do_rm,
      'er'  : self.do_erm,
      'gr'  : self.do_grm,
      'ger' : self.do_germ,
      't'   : self.do_tag,
      'st'  : self.do_skiptag,
      'go'  : self.do_deploy,
      'exit': self.do_quit,
      'q'   : self.do_quit
    }

  def emptyline(self):
    '''Action à lancer lors de la validation d'une ligne vide'''
    pass

  def default(self, line):
    '''Action à lancer lorsque la commande lancé est inconnu'''
    cmd, arg, line = self.parseline(line)
    if cmd in self.aliases:
      self.aliases[cmd](arg)
    elif cmd == 'EOF':
      return True
    else:
      print("Commande \"{}\" inconnu.".format(line))
      print("Utilisez la commande \"help\" pour obtenir la liste des commandes disponibles.")

  def do_help(self, arg):
    '''Affiche l'aide
    Usage : help, ? [commande]'''
    if arg != '':
      args = arg.split()
      if arg and args[0] in self.aliases:
        arg = self.aliases[args[0]].__name__[3:]
      super().do_help(arg)
    else:
      print("list, l                          Liste les serveurs, groupe et variable")
      print("add, a <serveur>                 Ajoute un serveur à la selection")
      print("eadd, e <regex serveur>          Ajoute un ou plusieurs serveurs à la selection selon une regex")
      print("gadd, g <groupe>                 Ajoute les serveurs d'un groupe à la selection")
      print("geadd, ge <regex groupe>         Ajoute les serveurs d'un groupe à la selection selon une regex")
      print("rm, r <serveur>                  Supprime un serveur de la selection")
      print("erm, er <regex serveur>          Supprime un ou plusieurs serveurs de la selection selon une regex")
      print("grm, gr <groupe>                 Supprime les serveurs d'un groupe de la selection")
      print("germ, ger <regex groupe>         Supprime les serveurs d'un groupe de la selection selon une regex")
      print("tag, t <tag> [<tag>...]          Applique un ou plusieurs tags lors du lancement du playbook")
      print("skiptag, st <tag> [<tag>...]     Ignore un ou plusieurs tags lors du lancement du playbook")
      print("deploy, go                       Déploie sur le ou les serveurs selectionnés")
      print("quit, exit, q                    Quitte le shell (et le programme)")

  def do_list(self, arg):
    '''Liste les serveurs, groupes et variables
    Usage : list, l'''
    pass

  def do_add(self, arg):
    '''Ajoute un serveur à la selection
    Usage : add, a <serveur>'''
    pass

  def do_eadd(self, arg):
    '''Ajoute un ou plusieurs serveurs à la selection selon une regex
    Usage : eadd, e <regex serveur>'''
    pass

  def do_gadd(self, arg):
    '''Ajoute les serveurs d'un groupe à la selection
    Usage : gadd, g <groupe>'''
    pass

  def do_geadd(self, arg):
    '''Ajoute les serveurs d'un groupe à la selection selon une regex
    Usage : geadd, ge <regex groupe>'''
    pass

  def do_rm(self, arg):
    '''Supprime un serveur de la selection
    Usage : rm, r <serveur>'''
    pass

  def do_erm(self, arg):
    '''Supprime un ou plusieurs serveurs de la selection selon une regex
    Usage : erm, er <regex serveur>'''
    pass

  def do_grm(self, arg):
    '''Supprime les serveurs d'un groupe de la selection
    Usage : grm, gr <groupe>'''
    pass

  def do_germ(self, arg):
    '''Supprime les serveurs d'un groupe de la selection selon une regex
    Usage : germ, ger <regex groupe>'''
    pass

  def do_tag(self, arg):
    '''Applique un ou plusieurs tags lors du lancement du playbook
    Usage : tag, t <tag> [<tag>...]'''
    pass

  def do_skiptag(self, arg):
    '''Ignore un ou plusieurs tags lors du lancement du playbook
    Usage : skiptag, st <tag> [<tag>...]'''
    pass

  def do_deploy(self, arg):
    '''Déploie sur le ou les serveurs selectionnés
    Usage : deploy, go'''
    pass

  def do_quit(self, arg):
    '''Quitte le shell (et le programme)
    Usage : quit, exit, q'''
    return True

# Appel la classe qui lance le shell interactif (et donc le programme)
Ansiblator().cmdloop()
