# Contribution guidelines

Following the contribution guidelines saves everyone time, requires less back
and forth during the review process, and helps to ensures a consistent codebase.
I use PyCharm for all of my programming, and these are what I use for my settings, adapt to your editor of choice.

## A few general rules first:

- Open any pull request against the `master` branch
- Keep code to 80 characters or less.
- Comment your code
- Pull request description should clearly show what the change is including output if relevant.
- Squash commits before opening a pull request.
- Test and then test again! Make sure it works with the latest changes in `master`.
- Spaces instead of Tabs
- 4 spaces for first indent and each from then on.
- Spaces around Assignment `(=, +=, …)`, Equality `(==, !=)`, Relational `(<, >, <=, >=)`, Bitwise `(*, |,^)`, Additive  `(+, -)`, Multiplicative `(*, @, /, %)`, Shift `(<<, >>, >>>)` and Power operators `(**)`.
- Spaces after:

```python
,
:
#
```

- Spaces before:

```python
\
#
```

- Align multiline method call arguments and method declaration parameters
- New line after a colon
- Align multiline import statements
- Align multiline collections and comprehensions
- Place `}` on a new line after a dictionary assignment
- 1 line between declarations and code
- 1 line after top level `imports`
- 1 line around `class`
- 1 line around `method`
- 2 lines around top-level `classes` and `functions`
- 1 line before and after `if` statements
- 1 line before and after `for` loops
- 1 line before and after `while` loops
- Run isort on `import` statements, including `from imports`.
- Keep `from imports` within their own group:

```python
import bar
import foo

from baz import foo
from foobar import morefoo
```

- Join `from imports` with the same source
- Align dictionaries on colons:

```python
x = max(
    1,
    2,
    3)

{
    “green”       : 42,
    "eggs and ham": -0.0e0
}
```

- Add a linefeed at the end of the file

## Documentation for Read The Docs

If you wish to update some of our [documentation](http://iocage.readthedocs.org), you only need to submit a PR for the files you change in iocage/doc/source. They will automatically be updated when the changes are merged.
