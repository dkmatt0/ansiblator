#!/usr/bin/env python3

import logging
import os
import shutil
import sys
import subprocess


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

# Chargement des roles et collections avec le fichier setup_env.sh s'il existe
# Sinon, chargement des roles et collections à partir du requirements.yaml
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
      logging.critical("Le chargement des roles et collections depuis le fichier requirements a rencontré une erreur.")
      exit(1)
  else:
    logging.warning("Le fichier requirements.yaml (ou .yml) n'existe pas ou n'est pas lisible.")

