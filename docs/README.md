This is the code for building the documentation with Sphinx.

Developer notes:

There are a few nuances to getting this setup working right. I wanted to create nicer docs and use some
more advanced capabilities like automatically generating docs content from the source code & docstrings,
but I also didn't want to spend a lot of effort learning new RST/Sphinx syntax, as most of the content is simple.

Therefore, the docs are written mostly as Markdown files which the [MyST-Parser](https://myst-parser.readthedocs.io/en/latest/) extension
converts at build time. I dislike the raw Sphinx style for docstrings and use Numpy style instead. There's also an extension for adding the .nojekyll file to make Github Pages render the docs without extra processing.

The current steps for publishing docs are:
1. Checkout the main branch and then create `git checkout -b gh-pages`.
2. Install sphinx and myst-parser.
3. `cd docs; .\make html`
4. Check the sphinx build worked and open locally in a browser to view.
5. `mv build/html/* .` (GH pages renders the docs folder only.)
6. Add and commit the docs folder to git, push to remote. Do not push the built output to other branches.

In the future this could be automated in CI.