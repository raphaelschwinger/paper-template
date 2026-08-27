# `ieee-journal` — IEEE journal / transactions paper

`\documentclass[journal]{IEEEtran}`. Nothing is vendored: IEEEtran ships with TeX
Live and with Overleaf. Official templates:
<https://www.ieee.org/conferences/publishing/templates>

Differences from `ieee-conference`, beyond the class option:

- affiliations go in a `\thanks` rather than `\IEEEauthorblockA`
- `\markboth` sets the running heads from `\PaperShortTitle`
- `\IEEEpeerreviewmaketitle` after the keywords, as the class expects

For camera-ready, vendor the exact `IEEEtran.cls`/`.bst` the transaction
publishes and add them to `assets:` in `template.yml`.

Uses `IEEEtranN.bst` for natbib compatibility — see the `ieee-conference`
README for why.
