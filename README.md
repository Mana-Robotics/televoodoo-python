### Installing Televoodoo into a venv

From the repo root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
pip install -r requirements.txt
pip install -e .
```

Now `televoodoo` is importable in the venv and a console entry `televoodoo` is available.


