BeeRef — Notes For Developers
=============================

BeeRef is written in Python and PyQt6.


Developing
----------

Clone the repository and install beeref and its dependencies using `uv <https://docs.astral.sh/uv/>`_::

  git clone https://github.com/rbreu/beeref.git
  cd beeref
  uv sync --extra dev

Run the app::

  uv run beeref

Run unittests::

  uv run pytest --cov .

This will also generate a coverage report:  ``htmlcov/index.html``.

Run linting with::

  uv run ruff check .

Beeref files are sqlite databases, so they can be inspected with any sqlite browser.

For debugging options, run::

  uv run beeref --help


Building the app
----------------

To build the app, run::

  pyinstaller BeeRef.spec

You will find the generated executable in the folder ``dist``.
