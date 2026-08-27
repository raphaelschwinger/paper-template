# `ieee-conference` — IEEE conference paper

`\documentclass[conference]{IEEEtran}`. Nothing is vendored: IEEEtran ships with
TeX Live and with Overleaf. Official templates and the current class version:
<https://www.ieee.org/conferences/publishing/templates>

**For camera-ready, vendor the exact `IEEEtran.cls` and `IEEEtran.bst` the venue
publishes** into the document directory and add them to `assets:` in
`template.yml` — publishers do check the version, and PDF eXpress will reject a
mismatch.

## Bibliography

Uses `IEEEtranN.bst`, the natbib-compatible IEEEtran style, so that `\citep` and
`\citet` behave the same here as under the arXiv templates. Stock `IEEEtran.bst`
renders `\citet` as `(author?)`.

If a venue mandates stock `IEEEtran.bst`, change `\bibliographystyle` in
`main.tex` (in this template source, not in a document) and restrict the prose to
`\cite`.

## Page limits

Workshop and conference limits count figures, tables and references. `make
wordcount PAPER=<doc>` gives a rough length; the page count in the built PDF is
what actually matters.
