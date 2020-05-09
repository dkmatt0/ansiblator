#!/usr/bin/env python3

import logging
import os
import shutil
import sys


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


