# Contributing to TAS_DNA

Use the [public index](TAS_DNA.md) to choose a destination and the [curation contract](docs/curation/README.md) to preserve provenance.

For a proposed intake or change, include:

- Purpose and concrete resulting behavior.
- Source URL, immutable revision, original path, authorship, and applicable license or publication permission.
- Destination and relationship: original, snapshot, derivative, mirror, or superseding revision.
- Content status and verification status, with unknowns explicit.
- Validation commands, inputs, expected results, actual results, and limitations.
- Updates to the index, artifact register, and claim manifest where affected.

For Python runtime changes, install the development requirements and run the checks appropriate to the affected boundary:

```sh
python -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-dev.txt
pytest -q
```

Documentation changes require checking links and status statements; they do not demonstrate runtime guarantees. Do not report tests as run merely because commands are documented.

Use small reviewed pull requests. Preserve originals during migration. Follow the existing [security guidance](SECURITY.md) for security findings. Review per-file and source license notices before redistribution; this guide does not grant a new license.

For an integrity finding, supply the input, initial state, authority snapshot, expected verdict, observed verdict, revision, and reproduction steps. Include receipt verification results where available. Redact secrets and personal information.
