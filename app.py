#!/usr/bin/env python3

import os


def yml_or_yaml(filename):
  '''Test si un fichier porte l'extension .yml ou .yaml et renvoi son nom complet.
  Renvoi None si le fichier n'est pas trouvé.

  Arguments :
  filename -- le nom d'un fichier sans l'extension
  '''
  if os.path.isfile(filename+'.yml'): return filename+'.yml'
  if os.path.isfile(filename+'.yaml'): return filename+'.yaml'
  return None
