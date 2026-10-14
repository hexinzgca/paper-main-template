# Owning-repository command hooks

`hooks.json` stores argv arrays, not shell fragments. Commands run in the owning
submodule directory. A first argument `{python}` is replaced by the interpreter
running `scripts/manage.py`, so the seed also supports native Windows Python.

The supplied code hook runs the seed's unittest suite; the figure hook invokes
its intentionally unconfigured renderer. Modify these arrays to match the real
repositories' documented interfaces. Use `null` for an unconfigured hook.
No project environment is installed implicitly. Do not guess tests for a foreign
repository or execute untrusted submodule code with secrets.

Any nonzero code-test exit is FAIL. For the figures hook only, exit code 2 is
reserved for missing configuration/inputs (BLOCKED); other nonzero exits are FAIL.
If adopting a tool that uses code 2 for a test failure, wrap or adapt that interface
explicitly rather than misclassifying its result. Rendering success must produce
real, inspected outputs; it does not automatically update assets or provenance.
