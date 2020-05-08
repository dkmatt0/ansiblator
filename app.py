#!/usr/bin/env python3

import os
import shutil
import sys


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
  print("Vous devez d'abord installer ansible.")
  exit(1)

# Test de tous les prérequis :
# - le fichier main.yaml existe et est accessible en lecture
# - le dossier inventory existe est n'est pas vide
playbook_file = yml_or_yaml('main')
if not playbook_file:
  print("Aucun fichier main.yml ou main.yaml n'a été trouvé.", file=sys.stderr)
  exit(1)
elif not os.access(playbook_file, os.R_OK):
  print("Le fichier {} ne peut pas être lu.".format(playbook_file), file=sys.stderr)
  exit(1)
elif not (os.path.isdir('inventory') and os.access('inventory', os.R_OK) and os.access('inventory', os.X_OK) and len(os.listdir('inventory'))>=1):
  exit(1)


