This module requires the Python library
[`satcfdi`](https://pypi.org/project/satcfdi/) to communicate
with the SAT web services. Install it in the same Python environment as
Odoo before using SAT connection features.

Install it with pip (**satcfdi >= 26.7.2**, which restores Python 3.10
support and the retention download API):

```
pip install "satcfdi>=26.7.2"
```

`satcfdi` is declared in the module manifest `external_dependencies`.
OCA CI and Runboat also pin it in the repository root
`test-requirements.txt` (`satcfdi>=26.7.2`), together with compatible
`urllib3` and `requests` pins.
