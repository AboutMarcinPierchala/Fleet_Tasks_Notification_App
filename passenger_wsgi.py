# passenger_wsgi.py
import sys, os
sys.path.append(os.getcwd())
from app import app as application