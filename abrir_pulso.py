import os
import runpy
import threading
import webbrowser
from pathlib import Path
os.chdir(Path(__file__).resolve().parent)
os.environ['HOST'] = '127.0.0.1'
os.environ['PORT'] = '8000'
threading.Timer(2, lambda: webbrowser.open('http://localhost:8000')).start()
print('Pulso iniciado. Mantenha esta janela aberta enquanto usa o programa.')
runpy.run_path('app.py', run_name='__main__')
